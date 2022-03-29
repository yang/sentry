import * as React from 'react';
import styled from '@emotion/styled';

import AsyncComponent from 'sentry/components/asyncComponent';
import Button from 'sentry/components/button';
import {IconClose} from 'sentry/icons';
import {t} from 'sentry/locale';
import PluginIcon from 'sentry/plugins/components/pluginIcon';
import space from 'sentry/styles/space';
import {IntegrationProvider, Organization} from 'sentry/types';
import {POPULARITY_WEIGHT} from 'sentry/views/organizationIntegrations/constants';

type Props = AsyncComponent['props'] & {
  addIntegration: (key: string) => void;
  integrationsSelected: string[];
  organization: Organization;
  removeIntegration: (key: string) => void;
  source: string;
};

type State = AsyncComponent['state'] & {
  integrations: {providers: IntegrationProvider[]} | null;
};

const getPopularity = (integration: IntegrationProvider) =>
  POPULARITY_WEIGHT[integration.slug] ?? 1;
const sortByPopularity = (a: IntegrationProvider, b: IntegrationProvider) =>
  getPopularity(b) - getPopularity(a);

const sortByName = (a: IntegrationProvider, b: IntegrationProvider) =>
  a.slug.localeCompare(b.slug);

class MultiIntegrationPlatformPicker extends AsyncComponent<Props, State> {
  getEndpoints(): ReturnType<AsyncComponent['getEndpoints']> {
    const {organization} = this.props;
    return [['integrations', `/organizations/${organization.slug}/config/integrations/`]];
  }

  get integrations() {
    // don't show self-hosted integrations since they aren't applicable to most orgs
    return (this.state.integrations?.providers || [])
      .filter(i => i.slug !== 'github_enterprise' && !i.slug.includes('server'))
      .sort(sortByName)
      .sort(sortByPopularity);
  }

  render() {
    const {addIntegration, removeIntegration, integrationsSelected} = this.props;
    return (
      <React.Fragment>
        <IntegrationList>
          {this.integrations.map(integration => (
            <IntegrationCard
              data-test-id={`integration-${integration.slug}`}
              key={integration.slug}
              integration={integration}
              selected={integrationsSelected.includes(integration.slug)}
              onClear={(e: React.MouseEvent) => {
                removeIntegration(integration.slug);
                e.stopPropagation();
              }}
              onClick={() => {
                // do nothing if already selected
                if (integrationsSelected.includes(integration.slug)) {
                  return;
                }
                addIntegration(integration.slug);
              }}
            />
          ))}
        </IntegrationList>
      </React.Fragment>
    );
  }
}

export default MultiIntegrationPlatformPicker;

const IntegrationList = styled('div')`
  display: grid;
  gap: ${space(1)};
  grid-template-columns: repeat(4, 1fr);
  margin-bottom: ${space(2)};
`;

const ClearButton = styled(Button)`
  position: absolute;
  top: -6px;
  right: -6px;
  min-height: 0;
  height: 22px;
  width: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: ${p => p.theme.background};
  color: ${p => p.theme.textColor};
`;

ClearButton.defaultProps = {
  icon: <IconClose isCircled size="xs" />,
  borderless: true,
  size: 'xsmall',
};

const IntegrationCard = styled(
  ({
    integration,
    selected,
    onClear,
    ...props
  }: {
    integration: IntegrationProvider;
    onClear: (e: React.MouseEvent) => void;
    onClick: () => void;
    selected: boolean;
  }) => (
    <div {...props}>
      <IntegrationIcon pluginId={integration.slug} size={64} />

      <h3>{integration.name}</h3>
      {selected && <ClearButton onClick={onClear} aria-label={t('Clear')} />}
    </div>
  )
)`
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0 0 14px;
  border-radius: 4px;
  cursor: pointer;
  background: ${p => p.selected && p.theme.alert.info.backgroundLight};

  &:hover {
    background: ${p => p.theme.alert.muted.backgroundLight};
  }

  h3 {
    flex-grow: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    color: ${p => (p.selected ? p.theme.textColor : p.theme.subText)};
    text-align: center;
    font-size: ${p => p.theme.fontSizeExtraSmall};
    text-transform: uppercase;
    margin: 0;
    padding: 0 ${space(0.5)};
    line-height: 1.2;
  }
`;

const IntegrationIcon = styled(PluginIcon)`
  margin: ${space(2)};
`;
