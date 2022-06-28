import {useCallback, useEffect, useState} from 'react';

import ErrorBoundary from 'sentry/components/errorBoundary';
import KeyValueList from 'sentry/components/events/interfaces/keyValueList';
import SpansInterface from 'sentry/components/events/interfaces/spans';
import LoadingIndicator from 'sentry/components/loadingIndicator';
import {Organization} from 'sentry/types';
import {Event, EventTransaction} from 'sentry/types/event';
import {generateEventSlug} from 'sentry/utils/discover/urls';
import useApi from 'sentry/utils/useApi';
import useOrganization from 'sentry/utils/useOrganization';

import getUnknownData from '../getUnknownData';

import getTraceKnownData from './getTraceKnownData';
import {FocusedSpanIDMap, TraceKnownData} from './types';

const traceKnownDataValues = ['caught_on_span'];

const traceIgnoredDataValues = [];

type Props = {
  data: TraceKnownData & Record<string, any>;
  event: Event;
  organization: Organization;
};

function Trace({event, data}: Props) {
  const organization = useOrganization();
  const api = useApi();

  const [eventTransaction, setEventTransaction] = useState<EventTransaction>();
  const [status, setStatus] = useState('loading');

  const fetchEventTransaction = useCallback(() => {
    const transaction_id = data.caught_on_transaction || '';
    const eventSlug = generateEventSlug({
      id: transaction_id,
      project: 'internal', // TODO: Fix later
    });

    api.clear();
    api.request(`/organizations/${organization.slug}/events/${eventSlug}/`, {
      success: eventData => {
        setStatus('success');
        setEventTransaction(eventData);
      },
      error: () => {
        setStatus('error');
      },
    });
  }, [api, data, organization]);

  useEffect(() => {
    fetchEventTransaction();
  }, [fetchEventTransaction]);

  const traceUnknownData = getUnknownData(data, [
    ...traceKnownDataValues,
    ...traceIgnoredDataValues,
  ]);

  const focusedSpanIds: FocusedSpanIDMap = {};
  traceUnknownData.forEach(d => {
    if (d.key === 'spans') {
      const spanIds: Set<string> = d.value as Set<string>;
      spanIds.forEach(spanId => (focusedSpanIds[spanId] = new Set()));
    }
  });

  return (
    <ErrorBoundary mini>
      <KeyValueList
        data={getTraceKnownData(data, traceKnownDataValues, event, organization)}
        isSorted={false}
        raw={false}
        isContextData
      />
      <KeyValueList data={traceUnknownData} isSorted={false} raw={false} isContextData />
      {eventTransaction ? (
        <SpansInterface
          organization={organization}
          event={eventTransaction!}
          focusedSpanIds={focusedSpanIds}
        />
      ) : status === 'loading' ? (
        <LoadingIndicator />
      ) : (
        <p>Error: {status}</p>
      )}
    </ErrorBoundary>
  );
}

export default Trace;
