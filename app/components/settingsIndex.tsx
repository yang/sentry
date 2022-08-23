import {useEffect} from 'react';
import {RouteComponentProps} from 'react-router';
import {css} from '@emotion/react';
import styled from '@emotion/styled';

import ExternalLink from 'sentry/components/links/externalLink';
import Link, {LinkProps} from 'sentry/components/links/link';
import {Panel, PanelBody, PanelHeader} from 'sentry/components/panels';
import SentryDocumentTitle from 'sentry/components/sentryDocumentTitle';
import space from 'sentry/styles/space';
import {Organization} from 'sentry/types';
import {Theme} from 'sentry/utils/theme';
import SettingsLayout from './settingsLayout';

const LINKS = {
  DOCUMENTATION: 'https://docs.sentry.io/',
  DOCUMENTATION_PLATFORMS: 'https://docs.sentry.io/clients/',
  DOCUMENTATION_QUICKSTART: 'https://docs.sentry.io/platform-redirect/?next=/',
  DOCUMENTATION_CLI: 'https://docs.sentry.io/product/cli/',
  DOCUMENTATION_API: 'https://docs.sentry.io/api/',
  API: '/settings/account/api/',
  MANAGE: '/manage/',
  FORUM: 'https://forum.sentry.io/',
  GITHUB_ISSUES: 'https://github.com/getsentry/sentry/issues',
  SERVICE_STATUS: 'https://status.sentry.io/',
};

const HOME_ICON_SIZE = 56;

type SettingsIndexProps = {
  organization: Organization;
};

function SettingsIndex({organization, ...props}: SettingsIndexProps) {
  return (
    <SentryDocumentTitle
      title={organization ? `${organization.slug} Settings` : 'Settings'}
    >
      <SettingsLayout {...props}>
        <GridLayout>Stuff</GridLayout>
      </SettingsLayout>
    </SentryDocumentTitle>
  );
}

export default SettingsIndex;

const GridLayout = styled('div')`
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: ${space(2)};
`;

const GridPanel = styled(Panel)`
  margin-bottom: 0;
`;

const HomePanelHeader = styled(PanelHeader)`
  background: ${p => p.theme.background};
  font-size: ${p => p.theme.fontSizeExtraLarge};
  align-items: center;
  text-transform: unset;
  padding: ${space(4)};
`;

const HomePanelBody = styled(PanelBody)`
  padding: 30px;

  h3 {
    font-size: 14px;
  }

  ul {
    margin: 0;
    li {
      line-height: 1.6;
      /* Bullet color */
      color: ${p => p.theme.gray200};
    }
  }
`;

const HomeIconContainer = styled('div')<{color?: string}>`
  background: ${p => p.theme[p.color || 'gray300']};
  color: ${p => p.theme.white};
  width: ${HOME_ICON_SIZE}px;
  height: ${HOME_ICON_SIZE}px;
  border-radius: ${HOME_ICON_SIZE}px;
  display: flex;
  justify-content: center;
  align-items: center;
`;

const linkCss = ({theme}: {theme: Theme}) => css`
  color: ${theme.purple300};

  &:hover {
    color: ${theme.purple300};
  }
`;

const linkIconCss = css`
  overflow: hidden;
  width: 100%;
  display: grid;
  grid-template-rows: max-content max-content;
  gap: ${space(1.5)};
  align-items: center;
  justify-items: center;
  justify-content: center;
`;

const HomeLink = styled(Link)`
  ${linkCss}
`;

const ExternalHomeLink = styled(ExternalLink)`
  ${linkCss}
`;

const HomeLinkIcon = styled(HomeLink)`
  ${linkIconCss}
`;

const ExternalHomeLinkIcon = styled(ExternalLink)`
  ${linkIconCss}
`;

interface SupportLinkProps extends Omit<LinkProps, 'ref' | 'to'> {
  isSelfHosted: boolean;
  organizationSettingsUrl: string;
  icon?: boolean;
}

function SupportLink({
  isSelfHosted,
  icon,
  organizationSettingsUrl,
  ...props
}: SupportLinkProps) {
  if (isSelfHosted) {
    const SelfHostedLink = icon ? ExternalHomeLinkIcon : ExternalHomeLink;
    return <SelfHostedLink href={LINKS.FORUM} {...props} />;
  }

  const SelfHostedLink = icon ? HomeLinkIcon : HomeLink;
  return <SelfHostedLink to={`${organizationSettingsUrl}support`} {...props} />;
}

const OrganizationName = styled('div')`
  line-height: 1.1em;

  ${p => p.theme.overflowEllipsis};
`;
