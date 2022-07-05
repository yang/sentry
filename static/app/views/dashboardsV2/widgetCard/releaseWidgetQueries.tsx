import {useEffect, useRef, useState} from 'react';
import cloneDeep from 'lodash/cloneDeep';
import isEqual from 'lodash/isEqual';
import omit from 'lodash/omit';
import trimStart from 'lodash/trimStart';

import {addErrorMessage} from 'sentry/actionCreators/indicator';
import {Client} from 'sentry/api';
import {isSelectionEqual} from 'sentry/components/organizations/pageFilters/utils';
import {t} from 'sentry/locale';
import {
  MetricsApiResponse,
  Organization,
  PageFilters,
  Release,
  SessionApiResponse,
} from 'sentry/types';
import {Series} from 'sentry/types/echarts';
import {TableDataWithTitle} from 'sentry/utils/discover/discoverQuery';
import {stripDerivedMetricsPrefix} from 'sentry/utils/discover/fields';
import {TOP_N} from 'sentry/utils/discover/types';

import {ReleasesConfig} from '../datasetConfig/releases';
import {DEFAULT_TABLE_LIMIT, DisplayType, Widget, WidgetQuery} from '../types';
import {
  DERIVED_STATUS_METRICS_PATTERN,
  DerivedStatusFields,
  DISABLED_SORT,
  METRICS_EXPRESSION_TO_FIELD,
} from '../widgetBuilder/releaseWidget/fields';

import GenericWidgetQueries, {
  GenericWidgetQueriesChildrenProps,
  GenericWidgetQueriesProps,
} from './genericWidgetQueries';

type Props = {
  api: Client;
  children: (props: GenericWidgetQueriesChildrenProps) => JSX.Element;
  organization: Organization;
  selection: PageFilters;
  widget: Widget;
  cursor?: string;
  limit?: number;
  onDataFetched?: (results: {
    tableResults?: TableDataWithTitle[];
    timeseriesResults?: Series[];
  }) => void;
};

export function derivedMetricsToField(field: string): string {
  return METRICS_EXPRESSION_TO_FIELD[field] ?? field;
}

function getReleasesQuery(releases: Release[]): {
  releaseQueryString: string;
  releasesUsed: string[];
} {
  let releaseCondition = '';
  const releasesArray: string[] = [];
  releaseCondition += 'release:[' + releases[0].version;
  releasesArray.push(releases[0].version);
  for (let i = 1; i < releases.length; i++) {
    releaseCondition += ',' + releases[i].version;
    releasesArray.push(releases[i].version);
  }
  releaseCondition += ']';
  if (releases.length < 10) {
    return {releaseQueryString: releaseCondition, releasesUsed: releasesArray};
  }
  if (releases.length > 10 && releaseCondition.length > 1500) {
    return getReleasesQuery(releases.slice(0, -10));
  }
  return {releaseQueryString: releaseCondition, releasesUsed: releasesArray};
}

/**
 * Given a list of requested fields, this function returns
 * 'aggregates' which is a list of aggregate functions that
 * can be passed to either Metrics or Sessions endpoints,
 * 'derivedStatusFields' which need to be requested from the
 * Metrics endpoint and 'injectFields' which are fields not
 * requested but required to calculate the value of a derived
 * status field so will need to be stripped away in post processing.
 */
export function resolveDerivedStatusFields(
  fields: string[],
  orderby: string,
  useSessionAPI: boolean
): {
  aggregates: string[];
  derivedStatusFields: string[];
  injectedFields: string[];
} {
  const aggregates = fields.map(stripDerivedMetricsPrefix);
  const derivedStatusFields = aggregates.filter(agg =>
    Object.values(DerivedStatusFields).includes(agg as DerivedStatusFields)
  );

  const injectedFields: string[] = [];

  const rawOrderby = trimStart(orderby, '-');
  const unsupportedOrderby =
    DISABLED_SORT.includes(rawOrderby) || useSessionAPI || rawOrderby === 'release';

  if (rawOrderby && !!!unsupportedOrderby && !!!fields.includes(rawOrderby)) {
    if (!!!injectedFields.includes(rawOrderby)) {
      injectedFields.push(rawOrderby);
    }
  }

  if (!!!useSessionAPI) {
    return {aggregates, derivedStatusFields, injectedFields};
  }

  derivedStatusFields.forEach(field => {
    const result = field.match(DERIVED_STATUS_METRICS_PATTERN);
    if (result) {
      if (result[2] === 'user' && !!!aggregates.includes('count_unique(user)')) {
        injectedFields.push('count_unique(user)');
        aggregates.push('count_unique(user)');
      }
      if (result[2] === 'session' && !!!aggregates.includes('sum(session)')) {
        injectedFields.push('sum(session)');
        aggregates.push('sum(session)');
      }
    }
  });

  return {aggregates, derivedStatusFields, injectedFields};
}

export function requiresCustomReleaseSorting(query: WidgetQuery): boolean {
  const useMetricsAPI = !!!query.columns.includes('session.status');
  const rawOrderby = trimStart(query.orderby, '-');
  return useMetricsAPI && rawOrderby === 'release';
}

const customDidUpdateComparator = (
  prevProps: GenericWidgetQueriesProps<
    SessionApiResponse | MetricsApiResponse,
    SessionApiResponse | MetricsApiResponse
  >,
  nextProps: GenericWidgetQueriesProps<
    SessionApiResponse | MetricsApiResponse,
    SessionApiResponse | MetricsApiResponse
  >
) => {
  const {loading, limit, widget, cursor, organization, selection} = nextProps;
  const ignoredWidgetProps = ['queries', 'title', 'id', 'layout', 'tempId', 'widgetType'];
  const ignoredQueryProps = ['name', 'fields', 'aggregates', 'columns'];
  return (
    limit !== prevProps.limit ||
    organization.slug !== prevProps.organization.slug ||
    !isSelectionEqual(selection, prevProps.selection) ||
    // If the widget changed (ignore unimportant fields, + queries as they are handled lower)
    !isEqual(
      omit(widget, ignoredWidgetProps),
      omit(prevProps.widget, ignoredWidgetProps)
    ) ||
    // If the queries changed (ignore unimportant name, + fields as they are handled lower)
    !isEqual(
      widget.queries.map(q => omit(q, ignoredQueryProps)),
      prevProps.widget.queries.map(q => omit(q, ignoredQueryProps))
    ) ||
    // If the fields changed (ignore falsy/empty fields -> they can happen after clicking on Add Overlay)
    !isEqual(
      widget.queries.flatMap(q => q.fields?.filter(field => !!field)),
      prevProps.widget.queries.flatMap(q => q.fields?.filter(field => !!field))
    ) ||
    !isEqual(
      widget.queries.flatMap(q => q.aggregates.filter(aggregate => !!aggregate)),
      prevProps.widget.queries.flatMap(q => q.aggregates.filter(aggregate => !!aggregate))
    ) ||
    !isEqual(
      widget.queries.flatMap(q => q.columns.filter(column => !!column)),
      prevProps.widget.queries.flatMap(q => q.columns.filter(column => !!column))
    ) ||
    loading !== prevProps.loading ||
    cursor !== prevProps.cursor
  );
};

function ReleaseWidgetQueries({
  widget,
  selection,
  api,
  organization,
  limit,
  children,
  cursor,
  onDataFetched,
}: Props) {
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined);
  const [releases, setReleases] = useState<Release[] | undefined>(undefined);
  const [queryFetchID, setQueryFetchID] = useState<Symbol | undefined>(undefined);

  const _isMounted = useRef(false);

  const fetchReleases = async () => {
    const {environments, projects} = selection;
    const currQueryFetchID = Symbol('queryFetchID');
    setQueryFetchID(currQueryFetchID);

    try {
      const releasesData = await api.requestPromise(
        `/organizations/${organization.slug}/releases/`,
        {
          method: 'GET',
          data: {
            sort: 'date',
            project: projects,
            per_page: 50,
            environments,
          },
        }
      );
      if (_isMounted.current && currQueryFetchID === queryFetchID) {
        setReleases(releasesData);
      }
    } catch (error) {
      const message = error.responseJSON
        ? error.responseJSON.error
        : t('Error sorting by releases');

      if (_isMounted.current && currQueryFetchID === queryFetchID) {
        addErrorMessage(message);
        setErrorMessage(message);
      }
    }
  };

  useEffect(() => {
    _isMounted.current = true;
    if (requiresCustomReleaseSorting(widget.queries[0])) {
      fetchReleases();
    }

    return () => {
      _isMounted.current = false;
    };
    // eslint-disable-next-line
  }, []);

  const getLimit = () => {
    switch (widget.displayType) {
      case DisplayType.TOP_N:
        return TOP_N;
      case DisplayType.TABLE:
        return limit ?? DEFAULT_TABLE_LIMIT;
      case DisplayType.BIG_NUMBER:
        return 1;
      default:
        return limit ?? 20; // TODO(dam): Can be changed to undefined once [INGEST-1079] is resolved
    }
  };

  const transformWidget = (initialWidget: Widget): Widget => {
    const transformedWidget = cloneDeep(initialWidget);

    const isCustomReleaseSorting = requiresCustomReleaseSorting(
      transformedWidget.queries[0]
    );
    const isDescending = transformedWidget.queries[0].orderby.startsWith('-');
    const useSessionAPI = transformedWidget.queries[0].columns.includes('session.status');

    let releaseCondition = '';
    const releasesArray: string[] = [];
    if (isCustomReleaseSorting) {
      if (releases && releases.length === 1) {
        releaseCondition += `release:${releases[0].version}`;
        releasesArray.push(releases[0].version);
      }
      if (releases && releases.length > 1) {
        const {releaseQueryString, releasesUsed} = getReleasesQuery(releases);
        releaseCondition += releaseQueryString;
        releasesArray.push(...releasesUsed);

        if (!!!isDescending) {
          releasesArray.reverse();
        }
      }
    }

    if (!useSessionAPI) {
      transformedWidget.queries.forEach(query => {
        query.conditions =
          query.conditions + (releaseCondition === '' ? '' : ` ${releaseCondition}`);
      });
    }

    return transformedWidget;
  };

  const afterFetchData = (data: SessionApiResponse | MetricsApiResponse) => {
    const isDescending = widget.queries[0].orderby.startsWith('-');

    const releasesArray: string[] = [];
    if (requiresCustomReleaseSorting(widget.queries[0])) {
      if (releases && releases.length === 1) {
        releasesArray.push(releases[0].version);
      }
      if (releases && releases.length > 1) {
        const {releasesUsed} = getReleasesQuery(releases);
        releasesArray.push(...releasesUsed);

        if (!!!isDescending) {
          releasesArray.reverse();
        }
      }
    }

    if (releasesArray.length) {
      data.groups.sort(function (group1, group2) {
        const release1 = group1.by.release;
        const release2 = group2.by.release;
        return releasesArray.indexOf(release1) - releasesArray.indexOf(release2);
      });
      data.groups = data.groups.slice(0, limit);
    }
  };

  const config = ReleasesConfig;

  return (
    <GenericWidgetQueries<
      SessionApiResponse | MetricsApiResponse,
      SessionApiResponse | MetricsApiResponse
    >
      config={config}
      api={api}
      organization={organization}
      selection={selection}
      widget={transformWidget(widget)}
      cursor={cursor}
      limit={getLimit()}
      onDataFetched={onDataFetched}
      loading={
        requiresCustomReleaseSorting(widget.queries[0])
          ? releases !== undefined
          : undefined
      }
      customDidUpdateComparator={customDidUpdateComparator}
      afterFetchTableData={afterFetchData}
      afterFetchSeriesData={afterFetchData}
    >
      {({errorMessage: widgetQueriesErrorMessage, ...rest}) =>
        children({
          errorMessage: errorMessage ?? widgetQueriesErrorMessage,
          ...rest,
        })
      }
    </GenericWidgetQueries>
  );
}

export default ReleaseWidgetQueries;
