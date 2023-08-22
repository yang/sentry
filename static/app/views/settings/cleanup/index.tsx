import {Fragment} from 'react';
import type {RouteComponentProps} from 'react-router';
import styled from '@emotion/styled';
import capitalize from 'lodash/capitalize';

import {addErrorMessage, addSuccessMessage} from 'sentry/actionCreators/indicator';
import {removeProject} from 'sentry/actionCreators/projects';
import {removeTeam} from 'sentry/actionCreators/teams';
import {hasEveryAccess} from 'sentry/components/acl/access';
import {Button} from 'sentry/components/button';
import Confirm from 'sentry/components/confirm';
import IdBadge from 'sentry/components/idBadge';
import ProjectBadge from 'sentry/components/idBadge/projectBadge';
import Link from 'sentry/components/links/link';
import LoadingError from 'sentry/components/loadingError';
import {removePageFiltersStorage} from 'sentry/components/organizations/pageFilters/persistence';
import PanelAlert from 'sentry/components/panels/panelAlert';
import PanelTable from 'sentry/components/panels/panelTable';
import {TabList} from 'sentry/components/tabs';
import TimeSince from 'sentry/components/timeSince';
import {t, tn} from 'sentry/locale';
import {space} from 'sentry/styles/space';
import type {Member, Project, Team, TeamWithProjects} from 'sentry/types';
import {handleXhrErrorResponse} from 'sentry/utils/handleXhrErrorResponse';
import {useApiQuery} from 'sentry/utils/queryClient';
import useApi from 'sentry/utils/useApi';
import useOrganization from 'sentry/utils/useOrganization';
import SettingsPageHeader from 'sentry/views/settings/components/settingsPageHeader';
import TextBlock from 'sentry/views/settings/components/text/textBlock';

interface OrganizationCleanupProps extends RouteComponentProps<{orgId: string}, {}> {}

type CleanupCategory = 'projects' | 'teams' | 'members';
const cleanupCategories: CleanupCategory[] = ['projects', 'teams', 'members'];
const cleanupCategoryDescriptions: Record<CleanupCategory, string> = {
  projects: t('Projects that have not received any events in the last 90 days.'),
  teams: t('Teams that have no members or no projects.'),
  members: t('Members that have not been active in 1 year.'),
};

const categoryHeaders: Record<CleanupCategory, string[]> = {
  projects: [t('Project'), ''],
  teams: [t('Team'), t('# of projects'), ''],
  members: [t('User'), t('Last Seen'), ''],
};

export default function OrganizationCleanup({location}: OrganizationCleanupProps) {
  const organization = useOrganization();
  const api = useApi();
  const category: CleanupCategory = location.query.category ?? 'projects';

  const {
    data = {},
    isLoading,
    isError,
    refetch,
  } = useApiQuery<Record<CleanupCategory, TeamWithProjects[] | Member[] | Project[]>>(
    [`/organizations/${organization.slug}/cleanup/`, {query: {category}}],
    {
      staleTime: 0,
    }
  );
  const dataArray: any[] = data[category] ?? [];

  async function handleRemoveProject(project: Project) {
    removePageFiltersStorage(organization.slug);

    try {
      await removeProject({
        api,
        orgSlug: organization.slug,
        projectSlug: project.slug,
        origin: 'settings',
      });
      addSuccessMessage(t('%s was successfully removed', project.slug));
    } catch (err) {
      addErrorMessage(t('Error removing %s', project.slug));
      handleXhrErrorResponse('Unable to remove project', err);
    } finally {
      refetch();
    }
  }

  const isProjectAdmin = (project: Project) =>
    hasEveryAccess(['project:admin'], {organization, project});

  async function handleRemoveTeam(team: Team) {
    try {
      await removeTeam(api, {orgId: organization.slug, teamId: team.slug});
      addSuccessMessage(t('%s was successfully removed', team.slug));
    } catch (err) {
      addErrorMessage(t('Error removing %s', team.slug));
      handleXhrErrorResponse('Unable to remove project', err);
    } finally {
      refetch();
    }
  }

  const hasTeamAdmin = (team: Team) =>
    hasEveryAccess(['team:admin'], {organization, team});

  async function handleRemoveMember(member: Member) {
    try {
      await api.requestPromise(
        `/organizations/${organization.slug}/members/${member.id}/`,
        {
          method: 'DELETE',
          data: {},
        }
      );
      addSuccessMessage(t('Removed %s from %s', member.name, organization.slug));
    } catch {
      addErrorMessage(t('Error removing %s from %s', member.name, organization.slug));
    } finally {
      refetch();
    }
  }

  const canRemoveMembers = organization.access.includes('member:admin');

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
          {cleanupCategories.map(cat => (
            <TabList.Item
              key={cat}
              to={{
                pathname: location.pathname,
                query: {category: cat},
              }}
            >
              {capitalize(cat)}
            </TabList.Item>
          ))}
        </TabList>

        {isError ? (
          <LoadingError onRetry={refetch} />
        ) : (
          <StyledPanelTable
            headers={categoryHeaders[category]}
            isLoading={isLoading}
            isEmpty={dataArray.length === 0}
          >
            <PanelAlert style={{gridColumn: `1/${categoryHeaders[category].length + 1}`}}>
              {cleanupCategoryDescriptions[category]}
            </PanelAlert>
            {dataArray.map((object: any) => {
              if (category === 'projects') {
                const project = object as Project;
                return (
                  <Fragment key={project.id}>
                    <FlexCenter>
                      <ProjectBadge project={project} avatarSize={16} />
                    </FlexCenter>

                    <FlexCenterRight>
                      <Confirm
                        onConfirm={() => handleRemoveProject(project)}
                        priority="danger"
                        confirmText={t('Remove Project')}
                        disabled={!isProjectAdmin(project) || project.isInternal}
                        message={
                          <div>
                            <TextBlock>
                              <strong>
                                {t(
                                  'Removing this project is permanent and cannot be undone!'
                                )}
                              </strong>
                            </TextBlock>
                            <TextBlock>
                              {t('This will also remove all associated event data.')}
                            </TextBlock>
                          </div>
                        }
                      >
                        <div>
                          <Button
                            disabled={!isProjectAdmin(project) || project.isInternal}
                            size="sm"
                          >
                            {t('Remove Project')}
                          </Button>
                        </div>
                      </Confirm>
                    </FlexCenterRight>
                  </Fragment>
                );
              }
              if (category === 'teams') {
                const team = object as TeamWithProjects;
                return (
                  <Fragment key={team.id}>
                    <FlexCenter>
                      <Link
                        data-test-id="team-link"
                        to={`/settings/${organization.slug}/teams/${team.slug}/`}
                      >
                        <IdBadge
                          team={team}
                          avatarSize={32}
                          description={tn('%s Member', '%s Members', team.memberCount)}
                        />
                      </Link>
                    </FlexCenter>
                    <FlexCenter>
                      {team.projects.length === 0
                        ? t('No Projects')
                        : tn('%s project', '%s projects', team.projects.length)}
                    </FlexCenter>
                    <FlexCenterRight>
                      <Confirm
                        disabled={!hasTeamAdmin(team)}
                        onConfirm={() => handleRemoveTeam(team)}
                        priority="danger"
                        message={t(
                          'Are you sure you want to remove the team %s?',
                          `#${team.slug}`
                        )}
                      >
                        <Button size="sm">{t('Remove Team')}</Button>
                      </Confirm>
                    </FlexCenterRight>
                  </Fragment>
                );
              }
              if (category === 'members') {
                const member = object as Member;
                const isIdpProvisioned = member.flags['idp:provisioned'];
                const canRemoveMember = canRemoveMembers && !isIdpProvisioned;
                return (
                  <Fragment key={member.id}>
                    <FlexCenter>
                      <IdBadge user={member.user!} avatarSize={32} />
                    </FlexCenter>
                    <FlexCenter>
                      <TimeSince date={member.user!.lastActive} />
                    </FlexCenter>
                    <FlexCenterRight>
                      {!canRemoveMember && (
                        <Button
                          disabled
                          size="sm"
                          title={
                            isIdpProvisioned
                              ? t(
                                  "This user is managed through your organization's identity provider."
                                )
                              : t('You do not have access to remove members')
                          }
                        >
                          {t('Remove')}
                        </Button>
                      )}
                      {canRemoveMember && (
                        <Confirm
                          message={t(
                            'Are you sure you want to remove %s from %s?',
                            member.name,
                            organization.slug
                          )}
                          onConfirm={() => handleRemoveMember(member)}
                        >
                          <Button size="sm">{t('Remove')}</Button>
                        </Confirm>
                      )}
                    </FlexCenterRight>
                  </Fragment>
                );
              }

              return null;
            })}
          </StyledPanelTable>
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

const StyledPanelTable = styled(PanelTable)``;

const FlexCenter = styled('div')`
  ${p => p.theme.overflowEllipsis}
  display: flex;
  align-items: center;
  line-height: 1.6;
`;

const FlexCenterRight = styled(FlexCenter)`
  justify-content: flex-end;
`;
