import {
  MetricsApiResponse,
  SessionApiResponse,
} from 'sentry/types';
import {Series} from 'sentry/types/echarts';
import {EventsTableData, TableData} from 'sentry/utils/discover/discoverQuery';

import {WidgetQuery} from '../types';
import {transformSessionsResponseToSeries} from '../widgetCard/transformSessionsResponseToSeries';
import {
  flattenMultiSeriesDataWithGrouping,
  transformSeries,
} from '../widgetCard/widgetQueries';

import DatasetConfig from './base';

type SeriesWithOrdering = [order: number, series: Series];

export const ReleasesConfig: DatasetConfig<
  SessionApiResponse | MetricsApiResponse,
  TableData | EventsTableData
> = {
  transformSeries: transformSessionsResponseToSeries,
};
