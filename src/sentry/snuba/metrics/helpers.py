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
from collections import OrderedDict
from datetime import datetime, timedelta
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
from sentry.utils.snuba import parse_snuba_datetime

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
_OP_TO_SNUBA_FUNCTION = {
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
    type_: sorted(mapping.keys()) for type_, mapping in _OP_TO_SNUBA_FUNCTION.items()
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

    def _build_where_for_entity(self, query_definition: QueryDefinition, entity):
        # Necessary to avoid metric naming collisions across different entities
        entity_specific_where = []
        metric_ids_set = set()
        for _, name in query_definition.fields.values():
            if name not in DERIVED_METRICS:
                metric_ids_set.add(resolve_weak(name))
            else:
                metric_ids_set |= DerivedMetricResolver.gen_metric_ids(name, entity=entity)
        entity_specific_where += [
            Condition(
                Column("metric_id"),
                Op.IN,
                list(metric_ids_set),
            ),
        ]
        return entity_specific_where

    def _build_groupby(self, query_definition: QueryDefinition) -> List[Column]:
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
        (op, name), direction = query_definition.orderby

        return [OrderBy(Column(f"{op}__{name}"), direction)]

    def _build_queries(self, query_definition):
        queries_by_entity = OrderedDict()
        for op, metric_name in query_definition.fields.values():
            if metric_name not in DERIVED_METRICS:
                entity = OPERATIONS_TO_ENTITY[op]
            else:
                entity = DERIVED_METRICS[metric_name].entity
                if not entity:
                    continue

            if entity not in self._implemented_datasets:
                raise NotImplementedError(f"Dataset not yet implemented: {entity}")

            queries_by_entity.setdefault(entity, []).append((op, metric_name))

        where = self._build_where(query_definition)
        groupby = self._build_groupby(query_definition)

        return {
            entity: self._build_queries_for_entity(query_definition, entity, fields, where, groupby)
            for entity, fields in queries_by_entity.items()
        }

    @staticmethod
    def _build_select(entity, fields):
        snql = []
        for op, name in fields:
            if name in DERIVED_METRICS:
                snql += DerivedMetricResolver.gen_select_snql(name, entity)
            else:
                snuba_function = _OP_TO_SNUBA_FUNCTION[entity][op]
                snql += [
                    Function(
                        snuba_function,
                        [
                            Column("value"),
                            Function(
                                "equals",
                                [
                                    Column("metric_id"),
                                    resolve_weak(name)
                                ]
                            )
                        ],
                        alias=f"{op}__{name}"
                    )
                ]
        return snql

    def _build_queries_for_entity(self, query_definition, entity, fields, where, groupby):
        totals_query = Query(
            dataset=Dataset.Metrics.value,
            match=Entity(entity),
            groupby=groupby,
            select=list(self._build_select(entity, fields)),
            where=where + self._build_where_for_entity(query_definition, entity),
            limit=Limit(query_definition.limit or MAX_POINTS),
            offset=Offset(query_definition.offset or 0),
            granularity=Granularity(query_definition.rollup),
            orderby=self._build_orderby(query_definition, entity),
        )

        if totals_query.orderby is None:
            series_query = totals_query.set_groupby(
                (totals_query.groupby or []) + [Column(TS_COL_GROUP)]
            )
        else:
            series_query = None

        return {
            "totals": totals_query,
            "series": series_query,
        }

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
_UNIT_TO_TYPE = {
    "sessions": "count",
    "percentage": "percentage"
}


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
                self._post_op_fields += (
                    DerivedMetricResolver.generate_bottom_up_derived_metrics_dependencies(metric)
                )

        self._timestamp_index = {timestamp: index for index, timestamp in enumerate(intervals)}

    def _parse_tag(self, tag_string: str) -> str:
        tag_key = int(tag_string.replace("tags[", "").replace("]", ""))
        return reverse_resolve(tag_key)

    def _extract_data(self, entity, data, groups):
        tags = tuple(
            (key, data[key])
            for key in sorted(data.keys())
            if (key.startswith("tags[") or key in ALLOWED_GROUPBY_COLUMNS)
        )

        tag_data = groups.setdefault(
            tags,
            {
                "totals": {},
                "series": {}
            },
        )

        timestamp = data.pop(TS_COL_GROUP, None)
        if timestamp is not None:
            timestamp = parse_snuba_datetime(timestamp)

        for op, metric_name in self._query_definition.fields.values():

            try:
                if op:
                    query_key = f"{op}__{metric_name}"
                    value = data[query_key]
                    if op in _OPERATIONS_PERCENTILES:
                        value = value[0]
                    key = f"{op}({metric_name})"
                else:
                    op = None
                    key = metric_name
                    value = data[key]
            except KeyError:
                continue

            if metric_name in DERIVED_METRICS:
                default_zero = \
                    _DEFAULT_AGGREGATES[_UNIT_TO_TYPE[DERIVED_METRICS[metric_name].unit]]
            else:
                default_zero = _DEFAULT_AGGREGATES[op]

            if timestamp is None:
                tag_data["totals"][key] = finite_or_none(value)

            if timestamp is not None or finite_or_none(value) == default_zero:
                try:
                    # ToDo handle the case when derived metric is just an alias like `sum(alias)`
                    if key in DERIVED_METRICS:
                        empty_values = len(self._intervals) * [
                            _DEFAULT_AGGREGATES[_UNIT_TO_TYPE[DERIVED_METRICS[key].unit]]
                        ]
                    else:
                        empty_values = len(self._intervals) * [_DEFAULT_AGGREGATES[op]]
                except KeyError:
                    empty_values = len(self._intervals) * [None]
                series = tag_data.setdefault("series", {}).setdefault(key, empty_values)

                if timestamp is not None:
                    series_index = self._timestamp_index[timestamp]
                    series[series_index] = finite_or_none(value)

    def translate_results(self):
        groups = {}

        for entity, subresults in self._results.items():

            totals = subresults["totals"]["data"]
            print("Before totals ", totals)
            for data in totals:
                self._extract_data(entity, data, groups)

            print("Before series ", totals)

            if "series" in subresults:
                series = subresults["series"]["data"]
                for data in series:
                    self._extract_data(entity, data, groups)
        print(" data is ", groups)

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

        print(self._post_op_fields)
        print("Groupsss ", groups)
        # ToDo check what happens if there is a groupBy
        # if len(groups) == 1 and not groups[0].get("totals", {}):
        #     groups = []

        for group in groups:
            totals = group["totals"]

            for post_op_field in self._post_op_fields:
                print("Trying ", post_op_field)
                print(totals)
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

        print("$" * 90)
        print(groups)
        print("$" * 90)

        return groups


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
                    Function(
                        "in",
                        [
                            Column("metric_id"),
                            list(metric_ids)
                        ]
                    )

                ]
            )

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
        if derived_metric_1.result_type == entity:
            arg1_snql = derived_metric_1.snql(metric_ids=metric_ids, entity=entity)

    arg2_snql = arg2
    if arg2 in DERIVED_METRICS:
        derived_metric_2 = DERIVED_METRICS[arg2]
        if derived_metric_2.result_type == entity:
            arg2_snql = derived_metric_2.snql(metric_ids=metric_ids, entity=entity)

    # Sanity Check
    print(arg1_snql, arg2_snql)
    for arg_snql in [arg1_snql, arg2_snql]:
        if isinstance(arg_snql, str) and arg_snql in DERIVED_METRICS:
            raise Exception("Something went wrong!")

    return Function(
        "multiply",
        [
            100,
            Function("minus", [1, Function("divide", [arg1_snql, arg2_snql])]),
        ],
        alias or "percentage",
    )


class DerivedMetric:
    def __init__(
        self,
        name: str,
        metrics: List[str],
        unit: str,
        entity: Optional[str],
        result_type: Optional[str] = None,
        snql: Optional[Function] = None,
        compute_func: Any = lambda *args: args,
        is_private: bool = False,
    ):
        self.name = name
        self.metrics = metrics
        self.snql = snql
        self.entity = entity
        self.result_type = result_type
        self.compute_func = compute_func
        self.unit = unit


class SingularEntityDerivedMetric(DerivedMetric):
    ...


class CompositeEntityDerivedMetric(DerivedMetric):
    ...


DERIVED_METRICS = {
    derived_metric.name: derived_metric
    for derived_metric in [
        DerivedMetric(
            # sum(sentry.sessions.session{status:crashed})
            name="init_sessions",
            metrics=["sentry.sessions.session"],
            entity="metrics_counters",
            unit="sessions",
            result_type="numeric",
            snql=lambda *_, entity, metric_ids, alias=None: _init_sessions(metric_ids, alias),
            is_private=True,
        ),
        DerivedMetric(
            # sum(sentry.sessions.session{status:crashed})
            name="crashed_sessions",
            metrics=["sentry.sessions.session"],
            entity="metrics_counters",
            unit="sessions",
            result_type="numeric",
            snql=lambda *_, entity, metric_ids, alias=None: _crashed_sessions(
                metric_ids, alias=alias),
            is_private=True,
        ),
        DerivedMetric(
            # sum(sentry.sessions.session{status:crashed})/sum(sentry.sessions.session{status:init})
            name="crash_free_percentage",
            metrics=["crashed_sessions", "init_sessions"],
            entity="metrics_counters",
            result_type="numeric",
            unit="percentage",
            snql=lambda *args, entity, metric_ids, alias=None: _percentage_in_snql(
                *args, entity, metric_ids, alias="crash_free_percentage"
            ),
        ),
        DerivedMetric(
            name="errored_preaggr",
            metrics=["sentry.sessions.session"],
            entity="metrics_counters",
            result_type="numeric",
            unit="sessions",
            snql=lambda *_, entity, metric_ids, alias=None: _errored_preaggr_sessions(
                metric_ids, alias=alias),
        ),
        DerivedMetric(
            name="sessions_errored_set",
            metrics=["sentry.sessions.session.error"],
            entity="metrics_sets",
            result_type="numeric",
            unit="sessions",
            snql=lambda *_, entity, metric_ids, alias=None: _sessions_errored_set(
                metric_ids, alias=alias),
        ),
        DerivedMetric(
            name="errored_sessions",
            metrics=["errored_preaggr", "sessions_errored_set"],
            entity=None,
            snql=None,
            result_type="numeric",
            unit="sessions",
            compute_func=lambda *args: sum([*args]),
        ),
    ]
}


class DerivedMetricResolver:
    @staticmethod
    def gen_metric_ids(derived_metric_name, entity):
        if derived_metric_name not in DERIVED_METRICS:
            return set()
        derived_metric = DERIVED_METRICS[derived_metric_name]
        # Stop recursing if we get to a derived metric with a different entity type than the one
        # we started with
        if derived_metric.entity is not None and derived_metric.entity != entity:
            return set()
        ids = set()
        for metric_name in derived_metric.metrics:
            if metric_name not in DERIVED_METRICS:
                ids.add(resolve_weak(metric_name))
            else:
                ids |= DerivedMetricResolver.gen_metric_ids(metric_name, entity)
        return ids

    @staticmethod
    def gen_select_snql(derived_metric_name, entity):
        if derived_metric_name not in DERIVED_METRICS:
            return []
        derived_metric = DERIVED_METRICS[derived_metric_name]
        # Stop recursing if we get to a derived metric with a different entity type than the one
        # we started with
        if derived_metric.entity is not None and derived_metric.entity != entity:
            return []
        snql = []
        if derived_metric.snql is not None:
            snql += [
                derived_metric.snql(
                    *derived_metric.metrics,
                    metric_ids=DerivedMetricResolver.gen_metric_ids(derived_metric_name, entity),
                    entity=entity
                )
            ]
        for metric_name in derived_metric.metrics:
            snql += DerivedMetricResolver.gen_select_snql(metric_name, entity)
        return snql

    @staticmethod
    def gen_metric_names_to_aliases_mapping(derived_metric_name):
        # Function that builds a mapping from the tree on the left to a dictionary described on
        # the right
        #         A
        #       /   \
        #      /     \
        #     B       C                  => {"raw_metric1": [B, C], "raw_metric2": [C]}
        #      \     / \
        #       \   /  raw_metric2
        #   raw_metric1
        #
        # This is necessary because since we coalesce all select statements of a particular
        # entity in just one query, we need to keep track of which raw_metrics correspond to
        # which aliases returned
        # As a hypothetical example, lets say we were querying for crash_free_percentage (which
        # uses `sentry.sessions.session` of metric_id=14) and the total count of another metric
        # `sentry.random.metric` of metric_id=1. Both of these metrics lie in
        # `metrics_counters`, and so coalescing these into one query would yield an output that
        # looks like this
        # ┌─metric_id─┬─crash_free_percentage─┬─random_metric_sum─┐
        # │         1 │                   nan │                 2 │
        # │        14 │                    50 │                12 │
        # └───────────┴───────────────────────┴───────────────────┘
        # Now because of how the query will be structured with conditional aggregates, we get cols
        # that might not be relevant for specific metric ids. In this case with metric_id=1 (
        # `sentry.random.metric`), we only care about `random_metric_sum` column but the
        # `crash_free_percentage` here is irrelevant. With metric id=14 (
        # `sentry.sessions.session`) we are only concerned with `crash_free_percentage` while
        # the `random_metric_sum` is irrelevant. Hence we need a way to keep track of this,
        # and so this function generates a mapping that looks like {"sentry.random.metric": [
        # "random_metric_name"], "sentry.sessions.session": ["crash_free_percentage"]}
        # ToDo: Write the one one caveat here about crash_free_percentage
        if derived_metric_name not in DERIVED_METRICS:
            return {}
        metric_names_to_aliases = {}
        derived_metric = DERIVED_METRICS[derived_metric_name]
        for metric in derived_metric.metrics:
            if metric not in DERIVED_METRICS:
                metric_names_to_aliases.setdefault(metric, []).append(derived_metric_name)
            metric_names_to_aliases.update(
                DerivedMetricResolver.gen_metric_names_to_aliases_mapping(metric)
            )
        return metric_names_to_aliases

    @staticmethod
    def generate_bottom_up_derived_metrics_dependencies(derived_metric_name):
        import queue

        derived_metric = DERIVED_METRICS[derived_metric_name]
        results = []
        queue = queue.Queue()
        queue.put(derived_metric)
        while not queue.empty():
            node = queue.get()
            if node.name in DERIVED_METRICS:
                results.append(node.name)
            for metric in node.metrics:
                if metric in DERIVED_METRICS:
                    queue.put(DERIVED_METRICS[metric])
        return list(reversed(results))
