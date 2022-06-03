import {Series} from 'sentry/types/echarts';
import {TableData} from 'sentry/utils/discover/discoverQuery';

import {WidgetQuery} from '../types';

export default interface DatasetConfig<SeriesResponse, TableResponse> {
  /**
   * Transforms timeseries API results into series data that is
   * ingestable by echarts for timeseries visualizations.
   */
  // TODO: Replace widgetQuery arg with queryAlias, see the
  // transformEventsSeriesData in ./errorsAndTransactions.tsx for
  // details.
  transformSeries?: (
    data: SeriesResponse,
    widgetQuery: WidgetQuery,
    requestedStatusMetrics?: string[],
    injectedFields?: string[]
  ) => Series[];
  /**
   * Transforms table API results into format that is used by
   * table and big number components
   */
  transformTable?: (
    data: TableResponse,
    shouldUseEvents?: boolean,
    requestedStatusMetrics?: string[],
    injectedFields?: string[]
  ) => TableData;
}
