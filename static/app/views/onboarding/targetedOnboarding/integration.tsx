import styled from '@emotion/styled';
import {motion} from 'framer-motion';

import ExternalLink from 'sentry/components/links/externalLink';
import MultiIntegrationPicker from 'sentry/components/multiIntegrationPicker';
import {t, tct} from 'sentry/locale';
import testableTransition from 'sentry/utils/testableTransition';
import StepHeading from 'sentry/views/onboarding/components/stepHeading';

import SelectIntegrationsFooter from './components/selectIntegrationsFooter';
import {StepProps} from './types';

function OnboardingIntegration(props: StepProps) {
  return (
    <Wrapper>
      <StepHeading step={props.stepIndex}>
        {t('Select all integrations you might use')}
      </StepHeading>
      <motion.div
        transition={testableTransition()}
        variants={{
          initial: {y: 30, opacity: 0},
          animate: {y: 0, opacity: 1},
          exit: {opacity: 0},
        }}
      >
        <p>
          {tct(
            `Variety is the spice of application monitoring. Sentry SDKs integrate
           with most languages and platforms your developer heart desires.
           [link:View the full list].`,
            {link: <ExternalLink href="https://docs.sentry.io/platforms/" />}
          )}
        </p>
        <SelectIntegrationsFooter {...props} />
        <MultiIntegrationPicker source="targeted-onboarding" {...props} />
      </motion.div>
    </Wrapper>
  );
}

export default OnboardingIntegration;

const Wrapper = styled('div')`
  width: 850px;
`;
