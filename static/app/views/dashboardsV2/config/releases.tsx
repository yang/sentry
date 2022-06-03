import {MetricsApiResponse, SessionApiResponse} from 'sentry/types';

import {transformSessionsResponseToSeries} from '../widgetCard/transformSessionsResponseToSeries';
import {transformSessionsResponseToTable} from '../widgetCard/transformSessionsResponseToTable';

import DatasetConfig from './base';

export const ReleasesConfig: DatasetConfig<
  SessionApiResponse | MetricsApiResponse,
  SessionApiResponse | MetricsApiResponse
> = {
  transformSeries: transformSessionsResponseToSeries,
  transformTable: transformSessionsResponseToTable,
};
