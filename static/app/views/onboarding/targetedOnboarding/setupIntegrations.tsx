import * as React from 'react';
import {browserHistory} from 'react-router';
import {css} from '@emotion/react';
import styled from '@emotion/styled';
import {motion} from 'framer-motion';
import * as qs from 'query-string';

import Alert, {alertStyles} from 'sentry/components/alert';
import AsyncComponent from 'sentry/components/asyncComponent';
import ExternalLink from 'sentry/components/links/externalLink';
import LoadingError from 'sentry/components/loadingError';
import {PlatformKey} from 'sentry/data/platformCategories';
import platforms from 'sentry/data/platforms';
import {t, tct} from 'sentry/locale';
import space from 'sentry/styles/space';
import {Integration, IntegrationProvider, ObjectStatus, Project} from 'sentry/types';
import trackAdvancedAnalyticsEvent from 'sentry/utils/analytics/trackAdvancedAnalyticsEvent';
import getDynamicText from 'sentry/utils/getDynamicText';
import {Theme} from 'sentry/utils/theme';
import useApi from 'sentry/utils/useApi';
import withProjects from 'sentry/utils/withProjects';

import FirstEventFooter from './components/firstEventFooter';
import FullIntroduction from './components/fullIntroduction';
import TargetedOnboardingSidebar from './components/sidebar';
import {StepProps} from './types';
import {usePersistedOnboardingState} from './utils';

type Props = {
  search: string;
} & StepProps &
  AsyncComponent['props'];

type State = {
  configurations: Integration[] | null;
  information: {providers: IntegrationProvider[]} | null;
} & AsyncComponent['state'];

class SetupIntegrations extends AsyncComponent<Props, State> {
  getEndpoints(): ReturnType<AsyncComponent['getEndpoints']> {
    const {slug} = this.props.organization;
    return [
      ['information', `/organizations/${slug}/config/integrations/`],
      ['configurations', `/organizations/${slug}/integrations/?includeConfig=0`],
    ];
  }
  renderBody() {
    const {configurations, information} = this.state;
    // should never happen but we need to make TS happy
    if (!configurations || !information) {
      return this.renderLoading();
    }
    return (
      <SetupIntegrationsCore
        {...this.props}
        configurations={configurations}
        providers={information.providers}
      />
    );
  }
}

type CoreProps = {
  configurations: Integration[];
  providers: IntegrationProvider[];
} & Props;

// make a functional compoonent child here so we can utilize usePersistedOnboardingState
function SetupIntegrationsCore(props: CoreProps) {
  const clientState = usePersistedOnboardingState()[0];
  return <div>Integrations</div>;
}

export default SetupIntegrations;
