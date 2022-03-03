import * as React from 'react';
import {css} from '@emotion/react';
import styled from '@emotion/styled';

import {ModalRenderProps} from 'sentry/actionCreators/modal';
import Button from 'sentry/components/button';
import ButtonBar from 'sentry/components/buttonBar';
import RadioGroup from 'sentry/components/forms/controls/radioGroup';
import Link from 'sentry/components/links/link';
import {t, tct} from 'sentry/locale';
import space from 'sentry/styles/space';
import {Organization, Project} from 'sentry/types';
import EventView from 'sentry/utils/discover/eventView';

type Props = {
  eventView: EventView;
  organization: Organization;
  project: Project;
} & ModalRenderProps;

const SamplingModal = (props: Props) => {
  const {Header, Body, Footer, organization, project} = props;
  const choices = [
    ['always', 'Automatically switch to sampled data when required'],
    ['never', 'Always show sampled data'],
  ];
  const [choice, setChoice] = React.useState(choices[0]);

  return (
    <React.Fragment>
      <Header closeButton>
        <h4>{t('Sampling Settings')}</h4>
      </Header>
      <Body>
        <Instruction>
          {tct(
            "The visualizations shown are based on your data without any filters or sampling. This does not contribute to your quota usage but transaction details are limited. If you'd like to improve accuracy, we recommend [transactions:adding more transactions to your quota]. or modifying your data set through [projectSettings: Filters & Sampling in settings].",
            {
              transactions: <Link to="" />,
              projectSettings: (
                <Link
                  to={`/settings/${organization.slug}/projects/${project?.slug}/performance/`}
                />
              ),
            }
          )}
        </Instruction>
        <Instruction>
          <RadioGroup
            style={{flex: 1}}
            choices={choices}
            value={choice[0]}
            label=""
            onChange={setChoice}
          />
        </Instruction>
      </Body>
      <Footer>
        <ButtonBar gap={1}>
          <Button priority="default" onClick={() => {}} data-test-id="reset-all">
            {t('Read the docs')}
          </Button>
          <Button
            aria-label={t('Apply')}
            priority="primary"
            onClick={() => {}}
            data-test-id="apply-threshold"
          >
            {t('Apply')}
          </Button>
        </ButtonBar>
      </Footer>
    </React.Fragment>
  );
};

const Instruction = styled('div')`
  margin-bottom: ${space(4)};
`;

export default SamplingModal;

export const modalCss = css`
  width: 100%;
  max-width: 650px;
  margin: 70px auto;
`;
