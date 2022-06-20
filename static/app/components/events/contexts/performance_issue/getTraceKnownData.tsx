import {getMeta} from 'sentry/components/events/meta/metaProxy';
import {KeyValueListData, Organization} from 'sentry/types';
import {Event} from 'sentry/types/event';
import {defined} from 'sentry/utils';

import getTraceKnownDataDetails from './getTraceKnownDataDetails';
import {TraceKnownData} from './types';

type TraceKnownDataKeys = Extract<keyof TraceKnownData, string>;

function getTraceKnownData(
  data: TraceKnownData,
  traceKnownDataValues: Array<string>,
  event: Event,
  organization: Organization
): KeyValueListData {
  const knownData: KeyValueListData = [];

  const dataKeys = traceKnownDataValues;

  for (const key of dataKeys) {
    const knownDataDetails = getTraceKnownDataDetails(data, key, event, organization);

    if ((knownDataDetails && !defined(knownDataDetails.value)) || !knownDataDetails) {
      continue;
    }

    knownData.push({
      key,
      ...knownDataDetails,
      meta: getMeta(data, key as TraceKnownDataKeys),
      subjectDataTestId: `trace-context-${key.toLowerCase()}-value`,
    });
  }

  return knownData;
}

export default getTraceKnownData;
