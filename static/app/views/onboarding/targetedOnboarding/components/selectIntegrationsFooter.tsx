import {Fragment} from 'react';
import styled from '@emotion/styled';
import {motion} from 'framer-motion';

import Button from 'sentry/components/button';
import ButtonBar from 'sentry/components/buttonBar';
import {t, tn} from 'sentry/locale';
import PluginIcon from 'sentry/plugins/components/pluginIcon';
import space from 'sentry/styles/space';
import {Organization} from 'sentry/types';
import testableTransition from 'sentry/utils/testableTransition';

import GenericFooter from './genericFooter';

type Props = {
  clearIntegrationSelections: () => void;
  genSkipOnboardingLink: () => React.ReactNode;
  integrationsSelected: string[];
  onComplete: () => void;
  organization: Organization;
};

export default function CreateProjectsFooter({
  integrationsSelected,
  onComplete,
  genSkipOnboardingLink,
  clearIntegrationSelections,
}: Props) {
  const renderIntegration = (integrationKey: string) => {
    return (
      <SelectedIntegrationIcon key={integrationKey} pluginId={integrationKey} size={23} />
    );
  };

  return (
    <GenericFooter>
      {genSkipOnboardingLink()}
      <SelectionWrapper>
        {integrationsSelected.length ? (
          <Fragment>
            <div>{integrationsSelected.map(renderIntegration)}</div>
            <IntegrationSelected>
              {tn(
                '%s integration selected',
                '%s integrations selected',
                integrationsSelected.length
              )}
            </IntegrationSelected>
          </Fragment>
        ) : null}
      </SelectionWrapper>
      <motion.div
        transition={testableTransition()}
        variants={{
          initial: {y: 30, opacity: 0},
          animate: {y: 0, opacity: 1},
          exit: {opacity: 0},
        }}
      >
        <SelectIntegrationsButtonBar gap={2}>
          <Button
            onClick={() => {
              clearIntegrationSelections();
              onComplete();
            }}
          >
            {t('Skip for now')}
          </Button>
          <Button
            priority="primary"
            onClick={() => onComplete()}
            disabled={integrationsSelected.length === 0}
          >
            {tn('Choose Integration', 'Choose Integrations', integrationsSelected.length)}
          </Button>
        </SelectIntegrationsButtonBar>
      </motion.div>
    </GenericFooter>
  );
}

const SelectionWrapper = styled(motion.div)`
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  margin-right: ${space(4)};
`;

SelectionWrapper.defaultProps = {
  transition: testableTransition({
    duration: 1.8,
  }),
};

const SelectedIntegrationIcon = styled(PluginIcon)`
  margin-right: ${space(1)};
`;

const IntegrationSelected = styled('div')`
  margin-top: ${space(1)};
`;

const SelectIntegrationsButtonBar = styled(ButtonBar)`
  margin: ${space(2)} ${space(4)};
`;
