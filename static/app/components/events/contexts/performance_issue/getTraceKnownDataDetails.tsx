import Button from 'sentry/components/button';
import {t} from 'sentry/locale';
import {Organization} from 'sentry/types';
import {Event} from 'sentry/types/event';
import {generateEventSlug} from 'sentry/utils/discover/urls';
import {getTransactionDetailsUrl} from 'sentry/utils/performance/urls';
import {transactionSummaryRouteWithQuery} from 'sentry/views/performance/transactionSummary/utils';

import {TraceKnownData, TraceKnownDataType} from './types';

type Output = {
  subject: string;
  value: React.ReactNode;
  actionButton?: React.ReactNode;
};

function getUserKnownDataDetails(
  data: TraceKnownData,
  type: string,
  event: Event,
  organization: Organization
): Output | undefined {
  switch (type) {
    case 'caught_on_span': {
      const span_id = data.caught_on_span || '';
      const transaction_id = data.caught_on_transaction || '';

      if (!span_id || !transaction_id) {
        return undefined;
      }

      if (!organization.features.includes('discover-basic')) {
        return {
          subject: t('Span Id (first caught)'),
          value: span_id,
        };
      }

      const eventSlug = generateEventSlug({
        id: transaction_id,
        project: 'internal', // TODO: Fix later
      });

      const target = getTransactionDetailsUrl(
        organization.slug,
        eventSlug,
        undefined,
        undefined,
        span_id
      );

      return {
        subject: t('Span Id (first caught)'),
        value: span_id,
        actionButton: (
          <Button size="xsmall" to={target}>
            {t('Go to Span')}
          </Button>
        ),
      };
    }

    case TraceKnownDataType.TRANSACTION_NAME: {
      const eventTag = event?.tags.find(tag => {
        return tag.key === 'transaction';
      });

      if (!eventTag || typeof eventTag.value !== 'string') {
        return undefined;
      }
      const transactionName = eventTag.value;

      const to = transactionSummaryRouteWithQuery({
        orgSlug: organization.slug,
        transaction: transactionName,
        projectID: event.projectID,
        query: {},
      });

      if (!organization.features.includes('performance-view')) {
        return {
          subject: t('Transaction'),
          value: transactionName,
        };
      }

      return {
        subject: t('Transaction'),
        value: transactionName,
        actionButton: (
          <Button size="xsmall" to={to}>
            {t('View Summary')}
          </Button>
        ),
      };
    }

    default:
      return undefined;
  }
}

export default getUserKnownDataDetails;
