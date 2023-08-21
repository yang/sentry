import {Fragment} from 'react';
import type {RouteComponentProps} from 'react-router';
import styled from '@emotion/styled';

import ProjectBadge from 'sentry/components/idBadge/projectBadge';
import {TeamBadge} from 'sentry/components/idBadge/teamBadge';
import UserBadge from 'sentry/components/idBadge/userBadge';
import LoadingError from 'sentry/components/loadingError';
import PanelTable from 'sentry/components/panels/panelTable';
import {TabList} from 'sentry/components/tabs';
import {t} from 'sentry/locale';
import {space} from 'sentry/styles/space';
import type {Project, Team, User} from 'sentry/types';
import {useApiQuery} from 'sentry/utils/queryClient';
import useOrganization from 'sentry/utils/useOrganization';
import SettingsPageHeader from 'sentry/views/settings/components/settingsPageHeader';

interface OrganizationCleanupProps extends RouteComponentProps<{orgId: string}, {}> {}

type CleanupCategory = 'projects' | 'teams' | 'users';

export default function OrganizationCleanup({location}: OrganizationCleanupProps) {
  const organization = useOrganization();
  const category: CleanupCategory = location.query.category ?? 'projects';

  const {
    data = [],
    isLoading,
    isError,
    refetch,
  } = useApiQuery<Team[] | User[] | Project[]>(
    [`/organizations/${organization.slug}/cleanup/`, {query: {category}}],
    {
      staleTime: 0,
    }
  );

  return (
    <Fragment>
      <SettingsPageHeader title={t('Cleanup')} />
      <p>
        {t(
          'Delete unused projects, empty teams and inactive users in your organization.'
        )}
      </p>

      <Layout>
        <TabList>
          <TabList.Item
            key="projects"
            to={{
              pathname: location.pathname,
              query: {category: 'projects'},
            }}
          >
            {t('Projects')}
          </TabList.Item>
          <TabList.Item
            key="teams"
            to={{
              pathname: location.pathname,
              query: {category: 'teams'},
            }}
          >
            {t('Teams')}
          </TabList.Item>
          <TabList.Item
            key="users"
            to={{
              pathname: location.pathname,
              query: {category: 'users'},
            }}
          >
            {t('Users')}
          </TabList.Item>
        </TabList>

        {isError ? (
          <LoadingError onRetry={refetch} />
        ) : (
          <PanelTable
            headers={['Title']}
            isLoading={isLoading}
            isEmpty={data.length === 0}
          >
            {data.map((object: any) => {
              if (category === 'projects') {
                const project = object as Project;
                return (
                  <div key={project.id}>
                    <ProjectBadge project={project} avatarSize={16} />
                  </div>
                );
              }
              if (category === 'teams') {
                const team = object as Team;
                return (
                  <div key={team.id}>
                    <TeamBadge team={team} avatarSize={16} />
                  </div>
                );
              }
              if (category === 'users') {
                const user = object as User;
                return (
                  <div key={user.id}>
                    <UserBadge user={user} avatarSize={16} />
                  </div>
                );
              }

              return null;
            })}
          </PanelTable>
        )}
      </Layout>
    </Fragment>
  );
}

const Layout = styled('div')`
  display: flex;
  flex-direction: column;
  gap: ${space(2)};
`;
