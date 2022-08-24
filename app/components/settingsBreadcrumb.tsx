import styled from '@emotion/styled';
import capitalize from 'lodash/capitalize';

import Link from 'sentry/components/links/link';
import Crumb from 'sentry/views/settings/components/settingsBreadcrumb/crumb';
import Divider from 'sentry/views/settings/components/settingsBreadcrumb/divider';
import OrganizationCrumb from 'sentry/views/settings/components/settingsBreadcrumb/organizationCrumb';
import ProjectCrumb from 'sentry/views/settings/components/settingsBreadcrumb/projectCrumb';
import TeamCrumb from 'sentry/views/settings/components/settingsBreadcrumb/teamCrumb';

const MENUS = {
  Organization: OrganizationCrumb,
  Project: ProjectCrumb,
  Team: TeamCrumb,
} as const;

type Props = {
  url: string;
  className?: string;
};

function SettingsBreadcrumb({className, url}: Props) {
  console.log({url});
  const {pathname} = new URL(url);
  const splitPath = pathname.split('/').filter(item => !!item);

  return (
    <Breadcrumbs className={className}>
      {splitPath.map((item, i) => {
        const pathTitle = capitalize(item.replaceAll('-', ' '));
        const isLast = i === splitPath.length - 1;
        const createMenu = MENUS[pathTitle];
        const Menu = typeof createMenu === 'function' && createMenu;
        const hasMenu = !!Menu;
        const thisPath = '/' + splitPath.slice(0, i + 1).join('/');
        console.log({pathTitle, isLast, thisPath, hasMenu});

        const CrumbItem = hasMenu
          ? Menu
          : () => (
              <Crumb>
                <CrumbLink to={thisPath}>{pathTitle} </CrumbLink>
                <Divider isLast={isLast} />
              </Crumb>
            );

        return <CrumbItem key={`${thisPath}`} isLast={isLast} />;
      })}
    </Breadcrumbs>
  );
}

export default SettingsBreadcrumb;

const CrumbLink = styled(Link)`
  display: block;

  &.focus-visible {
    outline: none;
    box-shadow: ${p => p.theme.blue300} 0 2px 0;
  }

  color: ${p => p.theme.subText};
  &:hover {
    color: ${p => p.theme.textColor};
  }
`;

export {CrumbLink};

const Breadcrumbs = styled('div')`
  display: flex;
  align-items: center;
`;
