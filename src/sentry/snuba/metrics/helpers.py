__all__ = (
    "ALLOWED_GROUPBY_COLUMNS",
    "AVAILABLE_OPERATIONS",
    "FIELD_REGEX",
    "MAX_POINTS",
    "METRIC_TYPE_TO_ENTITY",
    "MetricMeta",
    "MetricMetaWithTagKeys",
    "MetricOperation",
    "MetricType",
    "MetricUnit",
    "OPERATIONS",
    "OP_TO_SNUBA_FUNCTION",
    "QueryDefinition",
    "SnubaQueryBuilder",
    "SnubaResultConverter",
    "TAG_REGEX",
    "TS_COL_GROUP",
    "TS_COL_QUERY",
    "Tag",
    "TagValue",
    "TimeRange",
    "get_date_range",
    "get_intervals",
    "parse_field",
    "parse_query",
    "resolve_tags",
)

import math
import re
from abc import ABC
from collections import OrderedDict
from functools import cached_property
from operator import itemgetter
from datetime import datetime, timedelta
from functools import cached_property
from typing import (
    Any,
    Collection,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    TypedDict,
    Union,
)

from snuba_sdk import Column, Condition, Entity, Function, Granularity, Limit, Offset, Op, Query
from snuba_sdk.conditions import BooleanCondition
from snuba_sdk.orderby import Direction, OrderBy

from sentry.api.utils import InvalidParams, get_date_range_from_params
from sentry.exceptions import InvalidSearchQuery
from sentry.models import Project
from sentry.search.events.builder import UnresolvedQuery
from sentry.sentry_metrics import indexer
from sentry.sentry_metrics.utils import (
    resolve_tag_key,
    resolve_weak,
    reverse_resolve,
    reverse_resolve_weak,
)
from sentry.snuba.dataset import Dataset, EntityKey
from sentry.snuba.sessions_v2 import (  # TODO: unite metrics and sessions_v2
    ONE_DAY,
    AllowedResolution,
    InvalidField,
    finite_or_none,
)
from sentry.utils.dates import parse_stats_period, to_datetime, to_timestamp
from sentry.utils.snuba import parse_snuba_datetime, raw_snql_query

FIELD_REGEX = re.compile(r"^(\w+)\(((\w|\.|_)+)\)$")
TAG_REGEX = re.compile(r"^(\w|\.|_)+$")

_OPERATIONS_PERCENTILES = (
    "p50",
    "p75",
    "p90",
    "p95",
    "p99",
)

OPERATIONS = (
    "avg",
    "count_unique",
    "count",
    "max",
    "sum",
) + _OPERATIONS_PERCENTILES

#: Max number of data points per time series:
MAX_POINTS = 10000


TS_COL_QUERY = "timestamp"
TS_COL_GROUP = "bucketed_time"


class DerivedMetricParseException(Exception):
    ...


def parse_field(field: str) -> Tuple[Optional[str], str]:
    if field in DERIVED_METRICS:
        return None, field
    matches = FIELD_REGEX.match(field)
    try:
        if matches is None:
            raise TypeError
        operation = matches[1]
        metric_name = matches[2]
    except (IndexError, TypeError):
        raise InvalidField(f"Failed to parse '{field}'. Must be something like 'sum(my_metric)'.")
    else:
        if operation not in OPERATIONS:

            raise InvalidField(
                f"Invalid operation '{operation}'. Must be one of {', '.join(OPERATIONS)}"
            )

        return operation, metric_name


def resolve_tags(input_: Any) -> Any:
    """Translate tags in snuba condition

    This assumes that all strings are either tag names or tag values, so do not
    pass Column("metric_id") or Column("project_id") into this function.

    """
    if isinstance(input_, list):
        return [resolve_tags(item) for item in input_]
    if isinstance(input_, Function):
        if input_.function == "ifNull":
            # This was wrapped automatically by QueryBuilder, remove wrapper
            return resolve_tags(input_.parameters[0])
        return Function(
            function=input_.function,
            parameters=input_.parameters and [resolve_tags(item) for item in input_.parameters],
        )
    if isinstance(input_, Condition):
        return Condition(lhs=resolve_tags(input_.lhs), op=input_.op, rhs=resolve_tags(input_.rhs))
    if isinstance(input_, BooleanCondition):
        return input_.__class__(conditions=[resolve_tags(item) for item in input_.conditions])
    if isinstance(input_, Column):
        # HACK: Some tags already take the form "tags[...]" in discover, take that into account:
        if input_.subscriptable == "tags":
            name = input_.key
        else:
            name = input_.name
        return Column(name=resolve_tag_key(name))
    if isinstance(input_, str):
        return resolve_weak(input_)

    return input_


def parse_query(query_string: str) -> Sequence[Condition]:
    """Parse given filter query into a list of snuba conditions"""
    # HACK: Parse a sessions query, validate / transform afterwards.
    # We will want to write our own grammar + interpreter for this later.
    try:
        query_builder = UnresolvedQuery(
            Dataset.Sessions,
            params={
                "project_id": 0,
            },
        )
        where, _ = query_builder.resolve_conditions(query_string, use_aggregate_conditions=True)
    except InvalidSearchQuery as e:
        raise InvalidParams(f"Failed to parse query: {e}")

    return where


class QueryDefinition:
    """
    This is the definition of the query the user wants to execute.
    This is constructed out of the request params, and also contains a list of
    `fields` and `groupby` definitions as [`ColumnDefinition`] objects.

    Adapted from [`sentry.snuba.sessions_v2`].

    """

    def __init__(self, query_params, paginator_kwargs: Optional[Dict] = None):
        paginator_kwargs = paginator_kwargs or {}

        self.query = query_params.get("query", "")
        self.parsed_query = parse_query(self.query) if self.query else None
        raw_fields = query_params.getlist("field", [])
        self.groupby = query_params.getlist("groupBy", [])

        if len(raw_fields) == 0:
            raise InvalidField('Request is missing a "field"')

        self.fields = {key: parse_field(key) for key in raw_fields}

        self.orderby = self._parse_orderby(query_params)
        self.limit = self._parse_limit(query_params, paginator_kwargs)
        self.offset = self._parse_offset(query_params, paginator_kwargs)

        start, end, rollup = get_date_range(query_params)
        self.rollup = rollup
        self.start = start
        self.end = end

    def _parse_orderby(self, query_params):
        orderby = query_params.getlist("orderBy", [])
        if not orderby:
            return None
        elif len(orderby) > 1:
            raise InvalidParams("Only one 'orderBy' is supported")

        orderby = orderby[0]
        direction = Direction.ASC
        if orderby[0] == "-":
            orderby = orderby[1:]
            direction = Direction.DESC
        try:
            op, metric_name = self.fields[orderby]
        except KeyError:
            # orderBy one of the group by fields may be supported in the future
            raise InvalidParams("'orderBy' must be one of the provided 'fields'")

        return (op, metric_name), direction

    def _parse_limit(self, query_params, paginator_kwargs):
        if self.orderby:
            return paginator_kwargs.get("limit")
        else:
            per_page = query_params.get("per_page")
            if per_page is not None:
                # If order by is not None, it means we will have a `series` query which cannot be
                # paginated, and passing a `per_page` url param to paginate the results is not
                # possible
                raise InvalidParams("'per_page' is only supported in combination with 'orderBy'")
            return None

    def _parse_offset(self, query_params, paginator_kwargs):
        if self.orderby:
            return paginator_kwargs.get("offset")
        else:
            cursor = query_params.get("cursor")
            if cursor is not None:
                # If order by is not None, it means we will have a `series` query which cannot be
                # paginated, and passing a `per_page` url param to paginate the results is not
                # possible
                raise InvalidParams("'cursor' is only supported in combination with 'orderBy'")
            return None


class TimeRange(Protocol):
    start: datetime
    end: datetime
    rollup: int


def get_intervals(query: TimeRange):
    start = query.start
    end = query.end
    delta = timedelta(seconds=query.rollup)
    while start < end:
        yield start
        start += delta


def get_date_range(params: Mapping) -> Tuple[datetime, datetime, int]:
    """Get start, end, rollup for the given parameters.

    Apply a similar logic as `sessions_v2.get_constrained_date_range`,
    but with fewer constraints. More constraints may be added in the future.

    Note that this function returns a right-exclusive date range [start, end),
    contrary to the one used in sessions_v2.

    """
    interval = parse_stats_period(params.get("interval", "1h"))
    interval = int(3600 if interval is None else interval.total_seconds())

    # hard code min. allowed resolution to 10 seconds
    allowed_resolution = AllowedResolution.ten_seconds

    smallest_interval, interval_str = allowed_resolution.value
    if interval % smallest_interval != 0 or interval < smallest_interval:
        raise InvalidParams(
            f"The interval has to be a multiple of the minimum interval of {interval_str}."
        )

    if ONE_DAY % interval != 0:
        raise InvalidParams("The interval should divide one day without a remainder.")

    start, end = get_date_range_from_params(params)

    date_range = end - start

    date_range = timedelta(seconds=int(interval * math.ceil(date_range.total_seconds() / interval)))

    if date_range.total_seconds() / interval > MAX_POINTS:
        raise InvalidParams(
            "Your interval and date range would create too many results. "
            "Use a larger interval, or a smaller date range."
        )

    end_ts = int(interval * math.ceil(to_timestamp(end) / interval))
    end = to_datetime(end_ts)
    start = end - date_range

    # NOTE: The sessions_v2 implementation cuts the `end` time to now + 1 minute
    # if `end` is in the future. This allows for better real time results when
    # caching is enabled on the snuba queries. Removed here for simplicity,
    # but we might want to reconsider once caching becomes an issue for metrics.

    return start, end, interval


#: The type of metric, which determines the snuba entity to query
MetricType = Literal["counter", "set", "distribution"]

#: A function that can be applied to a metric
MetricOperation = Literal["avg", "count", "max", "min", "p50", "p75", "p90", "p95", "p99"]

MetricUnit = Literal["seconds"]


METRIC_TYPE_TO_ENTITY: Mapping[MetricType, EntityKey] = {
    "counter": EntityKey.MetricsCounters,
    "set": EntityKey.MetricsSets,
    "distribution": EntityKey.MetricsDistributions,
}


class MetricMeta(TypedDict):
    name: str
    type: MetricType
    operations: Collection[MetricOperation]
    unit: Optional[MetricUnit]


class Tag(TypedDict):
    key: str  # Called key here to be consistent with JS type


class TagValue(TypedDict):
    key: str
    value: str


class MetricMetaWithTagKeys(MetricMeta):
    tags: Sequence[Tag]


# Map requested op name to the corresponding Snuba function
OP_TO_SNUBA_FUNCTION = {
    "metrics_counters": {"sum": "sumIf"},
    "metrics_distributions": {
        "avg": "avgIf",
        "count": "countIf",
        "max": "maxIf",
        "min": "minIf",
        # TODO: Would be nice to use `quantile(0.50)` (singular) here, but snuba responds with an error
        "p50": "quantilesIf(0.50)",
        "p75": "quantilesIf(0.75)",
        "p90": "quantilesIf(0.90)",
        "p95": "quantilesIf(0.95)",
        "p99": "quantilesIf(0.99)",
    },
    "metrics_sets": {"count_unique": "uniqIf"},
}

AVAILABLE_OPERATIONS = {
    type_: sorted(mapping.keys()) for type_, mapping in OP_TO_SNUBA_FUNCTION.items()
}
OPERATIONS_TO_ENTITY = {
    op: entity for entity, operations in AVAILABLE_OPERATIONS.items() for op in operations
}
ALLOWED_GROUPBY_COLUMNS = ("project_id",)


class SnubaQueryBuilder:

    #: Datasets actually implemented in snuba:
    _implemented_datasets = {
        "metrics_counters",
        "metrics_distributions",
        "metrics_sets",
    }

    def __init__(self, projects: Sequence[Project], query_definition: QueryDefinition):
        self._projects = projects
        self._queries = self._build_queries(query_definition)

    def _build_where(
        self, query_definition: QueryDefinition
    ) -> List[Union[BooleanCondition, Condition]]:
        assert self._projects
        org_id = self._projects[0].organization_id

        where: List[Union[BooleanCondition, Condition]] = [
            Condition(Column("org_id"), Op.EQ, org_id),
            Condition(Column("project_id"), Op.IN, [p.id for p in self._projects]),
            Condition(Column(TS_COL_QUERY), Op.GTE, query_definition.start),
            Condition(Column(TS_COL_QUERY), Op.LT, query_definition.end),
        ]
        filter_ = resolve_tags(query_definition.parsed_query)
        if filter_:
            where.extend(filter_)

        return where

    def _build_groupby(self, query_definition: QueryDefinition) -> List[Column]:
        # ToDo ensure we cannot add any other cols than tags and groupBy as columns
        return [
            Column(resolve_tag_key(field))
            if field not in ALLOWED_GROUPBY_COLUMNS
            else Column(field)
            for field in query_definition.groupby
        ]

    def _build_orderby(
        self, query_definition: QueryDefinition, entity: str
    ) -> Optional[List[OrderBy]]:
        if query_definition.orderby is None:
            return None
        (op, metric_name), direction = query_definition.orderby
        metric_field_obj = metric_object_factory(op, metric_name)
        return metric_field_obj.generate_orderby_clause(
            entity=entity, projects=self._projects, direction=direction
        )

    @staticmethod
    def _build_totals_and_series_queries(
        entity, select, where, groupby, orderby, limit, offset, rollup, intervals_len
    ):
        totals_query = Query(
            dataset=Dataset.Metrics.value,
            match=Entity(entity),
            groupby=groupby,
            select=select,
            where=where,
            limit=Limit(limit or MAX_POINTS),
            offset=Offset(offset or 0),
            granularity=Granularity(rollup),
            orderby=orderby,
        )
        series_query = totals_query.set_groupby(
            (totals_query.groupby or []) + [Column(TS_COL_GROUP)]
        )

        # In a series query, we also need to factor in the len of the intervals array
        series_limit = MAX_POINTS
        if limit:
            series_limit = limit * intervals_len
        series_query = series_query.set_limit(series_limit)

        return {"totals": totals_query, "series": series_query}

    def _build_queries(self, query_definition):
        metric_name_to_obj_dict = {}

        queries_by_entity = OrderedDict()
        for op, metric_name in query_definition.fields.values():
            metric_field_obj = metric_object_factory(op, metric_name)
            entity = metric_field_obj.get_entity(projects=self._projects)

            # If entity is returned as None, it means we ran into an instance of
            # CompositeEntityDerivedMetric
            if not entity:
                continue

            if entity not in self._implemented_datasets:
                raise NotImplementedError(f"Dataset not yet implemented: {entity}")

            metric_name_to_obj_dict[(op, metric_name)] = metric_field_obj

            queries_by_entity.setdefault(entity, []).append((op, metric_name))

        where = self._build_where(query_definition)
        groupby = self._build_groupby(query_definition)

        queries_dict = {}
        for entity, fields in queries_by_entity.items():
            select = []
            metric_ids_set = set()
            for op, name in fields:
                metric_field_obj = metric_name_to_obj_dict[(op, name)]
                select += metric_field_obj.generate_select_statements(
                    entity=entity, projects=self._projects
                )
                metric_ids_set |= metric_field_obj.generate_metric_ids(entity)

            where_for_entity = [
                Condition(
                    Column("metric_id"),
                    Op.IN,
                    list(metric_ids_set),
                ),
            ]
            orderby = self._build_orderby(query_definition, entity)

            queries_dict[entity] = self._build_totals_and_series_queries(
                entity=entity,
                select=select,
                where=where + where_for_entity,
                groupby=groupby,
                orderby=orderby,
                limit=query_definition.limit,
                offset=query_definition.offset,
                rollup=query_definition.rollup,
                intervals_len=len(list(get_intervals(query_definition))),
            )

        return queries_dict

    def get_snuba_queries(self):
        return self._queries


_DEFAULT_AGGREGATES = {
    "avg": None,
    "count_unique": 0,
    "count": 0,
    "max": None,
    "p50": None,
    "p75": None,
    "p90": None,
    "p95": None,
    "p99": None,
    "sum": 0,
    "percentage": None,
}

# ToDo add here
_UNIT_TO_TYPE = {"sessions": "count", "percentage": "percentage"}


def combine_dictionary_of_list_values(main_dict, other_dict):
    for key, value in other_dict.items():
        if key in main_dict:
            main_dict[key] += value
            main_dict[key] = list(set(main_dict[key]))
        else:
            main_dict[key] = value
    return main_dict


class SnubaResultConverter:
    """Interpret a Snuba result and convert it to API format"""

    def __init__(
        self,
        organization_id: int,
        query_definition: QueryDefinition,
        intervals: List[datetime],
        results,
    ):
        self._organization_id = organization_id
        self._query_definition = query_definition
        self._intervals = intervals
        self._results = results
        self._post_op_fields = []

        for op, metric in query_definition.fields.values():
            if metric in DERIVED_METRICS:
                # ToDo merge trees so we don't have to evaluate everyone
                derived_metric = DERIVED_METRICS[metric]
                self._post_op_fields += derived_metric.generate_metrics_dependency_tree()

        self._timestamp_index = {timestamp: index for index, timestamp in enumerate(intervals)}

    def _parse_tag(self, tag_string: str) -> str:
        tag_key = int(tag_string.replace("tags[", "").replace("]", ""))
        return reverse_resolve(tag_key)

    def _extract_data(self, data, groups):
        tags = tuple(
            (key, data[key])
            for key in sorted(data.keys())
            if (key.startswith("tags[") or key in ALLOWED_GROUPBY_COLUMNS)
        )

        tag_data = groups.setdefault(
            tags,
            {"totals": {}, "series": {}},
        )

        bucketed_time = data.pop(TS_COL_GROUP, None)
        if bucketed_time is not None:
            bucketed_time = parse_snuba_datetime(bucketed_time)

        for op, metric_name in self._query_definition.fields.values():
            try:
                if op:
                    key = f"{op}({metric_name})"
                    value = data[key]
                    if op in _OPERATIONS_PERCENTILES:
                        value = value[0]
                else:
                    op = None
                    key = metric_name
                    value = data[key]
                cleaned_value = finite_or_none(value)
            except KeyError:
                continue

            if bucketed_time is None:
                tag_data["totals"][key] = cleaned_value

            if metric_name in DERIVED_METRICS:
                try:
                    default_null_value = _DEFAULT_AGGREGATES[
                        _UNIT_TO_TYPE[DERIVED_METRICS[metric_name].unit]
                    ]
                except KeyError:
                    default_null_value = None
            else:
                default_null_value = _DEFAULT_AGGREGATES[op]

            if bucketed_time is not None or cleaned_value == default_null_value:
                empty_values = len(self._intervals) * [default_null_value]
                series = tag_data["series"].setdefault(key, empty_values)

                if bucketed_time is not None:
                    series_index = self._timestamp_index[bucketed_time]
                    series[series_index] = cleaned_value

    def translate_results(self):
        groups = {}

        for entity, subresults in self._results.items():

            totals = subresults["totals"]["data"]
            print("Before totals ", totals)
            for data in totals:
                self._extract_data(data, groups)

            print("Before series ", totals)

            if "series" in subresults:
                series = subresults["series"]["data"]
                for data in series:
                    self._extract_data(data, groups)

        print("data is ", groups)

        groups = [
            dict(
                by=dict(
                    (self._parse_tag(key), reverse_resolve_weak(value))
                    if key not in ALLOWED_GROUPBY_COLUMNS
                    else (key, value)
                    for key, value in tags
                ),
                **data,
            )
            for tags, data in groups.items()
        ]

        for group in groups:
            totals = group["totals"]

            for post_op_field in self._post_op_fields:
                if post_op_field in totals:
                    print("Skipping ", post_op_field)
                    continue
                compute_func_args = []
                derived_metric = DERIVED_METRICS[post_op_field]
                for arg in derived_metric.metrics:
                    if arg in totals:
                        compute_func_args.append(totals[arg])
                if compute_func_args:
                    totals[post_op_field] = derived_metric.compute_func(*compute_func_args)

        return groups


_GRANULARITY = 24 * 60 * 60


def _get_data(
    *,
    entity_key: EntityKey,
    select: List[Column],
    where: List[Condition],
    groupby: List[Column],
    projects,
    org_id,
    referrer: str,
) -> Mapping[str, Any]:
    # Round timestamp to minute to get cache efficiency:
    now = datetime.now().replace(second=0, microsecond=0)

    query = Query(
        dataset=Dataset.Metrics.value,
        match=Entity(entity_key.value),
        select=select,
        groupby=groupby,
        where=[
            Condition(Column("org_id"), Op.EQ, org_id),
            Condition(Column("project_id"), Op.IN, [p.id for p in projects]),
            Condition(Column(TS_COL_QUERY), Op.GTE, now - timedelta(hours=24)),
            Condition(Column(TS_COL_QUERY), Op.LT, now),
        ]
        + where,
        granularity=Granularity(_GRANULARITY),
    )
    result = raw_snql_query(query, referrer, use_cache=True)
    return result["data"]


def _get_single_metric_info(projects: Sequence[Project], metric_name: str) -> MetricMetaWithTagKeys:
    assert projects

    metric_id = indexer.resolve(metric_name)

    if metric_id is None:
        raise InvalidParams

    for metric_type in ("counter", "set", "distribution"):
        # TODO: What if metric_id exists for multiple types / units?
        entity_key = METRIC_TYPE_TO_ENTITY[metric_type]
        data = _get_data(
            entity_key=entity_key,
            select=[Column("metric_id"), Column("tags.key")],
            where=[Condition(Column("metric_id"), Op.EQ, metric_id)],
            groupby=[Column("metric_id"), Column("tags.key")],
            referrer="snuba.metrics.meta.get_single_metric",
            projects=projects,
            org_id=projects[0].organization_id,
        )
        if data:
            tag_ids = {tag_id for row in data for tag_id in row["tags.key"]}
            return {
                "name": metric_name,
                "type": metric_type,
                "operations": AVAILABLE_OPERATIONS[entity_key.value],
                "tags": sorted(
                    ({"key": reverse_resolve(tag_id)} for tag_id in tag_ids),
                    key=itemgetter("key"),
                ),
                "unit": None,
            }

    raise InvalidParams


def _init_sessions(metric_id, alias=None):
    return Function(
        "sumMergeIf",
        [
            Column("value"),
            Function(
                "equals",
                [
                    Function(
                        "arrayElement",
                        [
                            Column("tags.value"),
                            Function(
                                "indexOf",
                                [Column("tags.key"), resolve_weak("session.status")],
                            ),
                        ],
                        "status",
                    ),
                    resolve_weak("init"),
                ],
            ),
        ],
        alias or "init_sessions",
    )


def _crashed_sessions(metric_id, alias=None):
    return Function(
        "sumMergeIf",
        [
            Column("value"),
            Function(
                "equals",
                [
                    Function(
                        "arrayElement",
                        [
                            Column("tags.value"),
                            Function(
                                "indexOf",
                                [Column("tags.key"), resolve_weak("session.status")],
                            ),
                        ],
                        "status",
                    ),
                    resolve_weak("crashed"),
                ],
            ),
        ],
        alias or "crashed_sessions",
    )


def _errored_preaggr_sessions(metric_ids, alias=None):
    return Function(
        "sumMergeIf",
        [
            Column("value"),
            Function(
                "and",
                [
                    Function(
                        "equals",
                        [
                            Function(
                                "arrayElement",
                                [
                                    Column("tags.value"),
                                    Function(
                                        "indexOf",
                                        [Column("tags.key"), resolve_weak("session.status")],
                                    ),
                                ],
                                "status",
                            ),
                            resolve_weak("errored_preaggr"),
                        ],
                    ),
                    Function("in", [Column("metric_id"), list(metric_ids)]),
                ],
            ),
        ],
        alias or "errored_preaggr",
    )


def _sessions_errored_set(metric_ids, alias=None):
    return Function(
        "uniqCombined64MergeIf",
        [
            Column("value"),
            Function(
                "in",
                [
                    Column("metric_id"),
                    list(metric_ids),
                ],
            ),
        ],
        alias or "sessions_errored_set",
    )


def _percentage_in_snql(arg1, arg2, entity, metric_ids, alias=None):
    arg1_snql = arg1
    if arg1 in DERIVED_METRICS:
        derived_metric_1 = DERIVED_METRICS[arg1]
        if derived_metric_1.entity == entity:
            arg1_snql = derived_metric_1.snql(metric_ids=metric_ids, entity=entity)

    arg2_snql = arg2
    if arg2 in DERIVED_METRICS:
        derived_metric_2 = DERIVED_METRICS[arg2]
        if derived_metric_2.entity == entity:
            arg2_snql = derived_metric_2.snql(metric_ids=metric_ids, entity=entity)

    # Sanity Check
    for arg_snql in [arg1_snql, arg2_snql]:
        if isinstance(arg_snql, str) and arg_snql in DERIVED_METRICS:
            raise DerivedMetricParseException("Unable to get SNQL constituents translation")

    return Function(
        "multiply",
        [
            100,
            Function("minus", [1, Function("divide", [arg1_snql, arg2_snql])]),
        ],
        alias or "percentage",
    )


class DerivedMetricBaseTraverser:
    @staticmethod
    def get_entity_of_derived_metric(derived_metric_name, projects):
        raise NotImplementedError()

    @staticmethod
    def gen_select_snql(derived_metric_name, entity):
        raise NotImplementedError()

    @staticmethod
    def gen_metric_ids(derived_metric_name):
        raise NotImplementedError()

    @staticmethod
    def validate_derived_metric_dependency_tree(derived_metric_name):
        raise NotImplementedError()

    @staticmethod
    def generate_bottom_up_derived_metrics_dependencies(derived_metric_name):
        import queue

        derived_metric = DERIVED_METRICS[derived_metric_name]
        results = []
        queue = queue.Queue()
        queue.put(derived_metric)
        while not queue.empty():
            node = queue.get()
            if node.metric_name in DERIVED_METRICS:
                results.append(node.metric_name)
            for metric in node.metrics:
                if metric in DERIVED_METRICS:
                    queue.put(DERIVED_METRICS[metric])
        return list(reversed(results))


class SingularEntityTraverser(DerivedMetricBaseTraverser):
    @staticmethod
    def get_entity_of_derived_metric(derived_metric_name, projects):
        if derived_metric_name not in DERIVED_METRICS:
            metric_type = _get_single_metric_info(projects, derived_metric_name)["type"]
            return METRIC_TYPE_TO_ENTITY[metric_type].value
        derived_metric = DERIVED_METRICS[derived_metric_name]
        for metric in derived_metric.metrics:
            return SingularEntityTraverser.get_entity_of_derived_metric(metric, projects)

    @staticmethod
    def gen_select_snql(derived_metric_name, entity):
        if derived_metric_name not in DERIVED_METRICS:
            return []
        derived_metric = DERIVED_METRICS[derived_metric_name]
        return [
            derived_metric.snql(
                *derived_metric.metrics,
                metric_ids=SingularEntityTraverser.gen_metric_ids(derived_metric_name),
                entity=entity,
            )
        ]

    @staticmethod
    def gen_metric_ids(derived_metric_name):
        if derived_metric_name not in DERIVED_METRICS:
            return set()
        derived_metric = DERIVED_METRICS[derived_metric_name]
        ids = set()
        for metric_name in derived_metric.metrics:
            if metric_name not in DERIVED_METRICS:
                ids.add(resolve_weak(metric_name))
            else:
                ids |= SingularEntityTraverser.gen_metric_ids(metric_name)
        return ids

    @staticmethod
    def validate_derived_metric_dependency_tree(derived_metric_name, projects):
        entities = SingularEntityTraverser.__get_all_entities_in_derived_metric_dependency_tree(
            derived_metric_name=derived_metric_name, projects=projects
        )
        return len(entities) == 1 and entities.pop() is not None

    @staticmethod
    def __get_all_entities_in_derived_metric_dependency_tree(derived_metric_name, projects):
        if derived_metric_name not in DERIVED_METRICS:
            return set()
        derived_metric = DERIVED_METRICS[derived_metric_name]
        entities = {derived_metric.get_entity(projects)}
        for metric_name in derived_metric.metrics:
            entities |= (
                SingularEntityTraverser.__get_all_entities_in_derived_metric_dependency_tree(
                    metric_name, projects
                )
            )
        return entities


class CompositeEntityTraverser(DerivedMetricBaseTraverser):
    @staticmethod
    def get_entity_of_derived_metric(derived_metric_name, projects):
        return None

    @staticmethod
    def gen_select_snql(derived_metric_name, entity):
        return []

    @staticmethod
    def gen_metric_ids(derived_metric_name):
        return set()

    @staticmethod
    def validate_derived_metric_dependency_tree(derived_metric_name):
        return True


def metric_object_factory(op, metric_name):
    if metric_name in DERIVED_METRICS:
        instance = DERIVED_METRICS[metric_name]
    else:
        instance = RawMetric(op, metric_name)
    return instance


class MetricsFieldBase(ABC):
    def __init__(self, op, metric_name):
        self.op = op
        self.metric_name = metric_name

    def get_entity(self, **kwargs):
        raise NotImplementedError

    def generate_metric_ids(self, *args):
        raise NotImplementedError

    def generate_select_statements(self, **kwargs):
        raise NotImplementedError

    def generate_orderby_clause(self, **kwargs):
        raise NotImplementedError


class RawMetric(MetricsFieldBase):
    def get_entity(self, **kwargs):
        return OPERATIONS_TO_ENTITY[self.op]

    def generate_metric_ids(self, entity, *args):
        return (
            {resolve_weak(self.metric_name)} if OPERATIONS_TO_ENTITY[self.op] == entity else set()
        )

    def _build_conditional_aggregate_for_metric(self, entity):
        snuba_function = OP_TO_SNUBA_FUNCTION[entity][self.op]
        return Function(
            snuba_function,
            [
                Column("value"),
                Function("equals", [Column("metric_id"), resolve_weak(self.metric_name)]),
            ],
            alias=f"{self.op}({self.metric_name})",
        )

    def generate_select_statements(self, entity, **kwargs):
        return [self._build_conditional_aggregate_for_metric(entity=entity)]

    def generate_orderby_clause(self, entity, direction, **kwargs):
        return [
            OrderBy(
                self.generate_select_statements(entity=entity)[0],
                direction,
            )
        ]

    entity = cached_property(get_entity)
<<<<<<< HEAD
=======


class DerivedMetric(MetricsFieldBase, ABC):
    traverser_cls = None

    def __init__(
        self,
        metric_name: str,
        metrics: List[str],
        unit: str,
        result_type: Optional[str] = None,
        snql: Optional[Function] = None,
        compute_func: Any = lambda *args: args,
        is_private: bool = False,
    ):
        super().__init__(op=None, metric_name=metric_name)
        self.metrics = metrics
        self.snql = snql
        self.result_type = result_type
        self.compute_func = compute_func
        self.unit = unit
        self._entity = None

    def get_entity(self, projects=None, **kwargs):
        return (
            self.traverser_cls.get_entity_of_derived_metric(self.metric_name, projects)
            if projects
            else self._entity
        )

    def generate_select_statements(self, projects, **kwargs):
        if not self.traverser_cls.validate_derived_metric_dependency_tree(
            derived_metric_name=self.metric_name, projects=projects
        ):
            raise DerivedMetricParseException(
                f"Derived Metric {self.metric_name} cannot be calculated from a single entity"
            )
        return self.traverser_cls.gen_select_snql(
            derived_metric_name=self.metric_name, entity=self.entity
        )

    def generate_metric_ids(self, *args):
        return self.traverser_cls.gen_metric_ids(derived_metric_name=self.metric_name)

    def generate_metrics_dependency_tree(self):
        return self.traverser_cls.generate_bottom_up_derived_metrics_dependencies(
            derived_metric_name=self.metric_name
        )

    def generate_orderby_clause(self, projects, direction):
        return [
            OrderBy(
                self.generate_select_statements(projects=projects)[0],
                direction,
            )
        ]

    entity = cached_property(get_entity)


class SingularEntityDerivedMetric(DerivedMetric):
    traverser_cls = SingularEntityTraverser

    def __init__(
        self,
        metric_name: str,
        metrics: List[str],
        unit: str,
        snql: Function,
        is_private: bool = False,
    ):
        super().__init__(
            metric_name=metric_name,
            metrics=metrics,
            unit=unit,
            result_type="numeric",
            snql=snql,
            compute_func=lambda *args: args,
            is_private=is_private,
        )

    def get_entity(self, projects=None, **kwargs):
        entity = super().get_entity(projects)
        if not entity:
            raise DerivedMetricParseException(
                "entity property is only available after it is set through calling `get_entity` "
                "with projects"
            )
        return entity


class CompositeEntityDerivedMetric(DerivedMetric):
    traverser_cls = CompositeEntityTraverser

    def __init__(
        self,
        metric_name: str,
        metrics: List[str],
        unit: str,
        compute_func: Any = lambda *args: args,
        is_private: bool = False,
    ):
        super().__init__(
            metric_name=metric_name,
            metrics=metrics,
            unit=unit,
            result_type="numeric",
            snql=None,
            compute_func=compute_func,
            is_private=is_private,
        )


DERIVED_METRICS = {
    derived_metric.metric_name: derived_metric
    for derived_metric in [
        SingularEntityDerivedMetric(
            metric_name="init_sessions",
            metrics=["sentry.sessions.session"],
            unit="sessions",
            snql=lambda *_, entity, metric_ids, alias=None: _init_sessions(metric_ids, alias),
        ),
        SingularEntityDerivedMetric(
            metric_name="crashed_sessions",
            metrics=["sentry.sessions.session"],
            unit="sessions",
            snql=lambda *_, entity, metric_ids, alias=None: _crashed_sessions(
                metric_ids, alias=alias
            ),
        ),
        SingularEntityDerivedMetric(
            metric_name="crash_free_percentage",
            metrics=["crashed_sessions", "init_sessions"],
            unit="percentage",
            snql=lambda *args, entity, metric_ids, alias=None: _percentage_in_snql(
                *args, entity, metric_ids, alias="crash_free_percentage"
            ),
        ),
        SingularEntityDerivedMetric(
            metric_name="errored_preaggr",
            metrics=["sentry.sessions.session"],
            unit="sessions",
            snql=lambda *_, entity, metric_ids, alias=None: _errored_preaggr_sessions(
                metric_ids, alias=alias
            ),
        ),
        SingularEntityDerivedMetric(
            metric_name="sessions_errored_set",
            metrics=["sentry.sessions.session.error"],
            unit="sessions",
            snql=lambda *_, entity, metric_ids, alias=None: _sessions_errored_set(
                metric_ids, alias=alias
            ),
        ),
        CompositeEntityDerivedMetric(
            metric_name="errored_sessions",
            metrics=["errored_preaggr", "sessions_errored_set"],
            unit="sessions",
            compute_func=lambda *args: sum([*args]),
        ),
    ]
}
>>>>>>> d916d2fcfc (.)
