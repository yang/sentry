from datetime import datetime, timedelta

from sentry.models import Group
from sentry.testutils.cases import APITestCase

DAYS_AGO_91 = datetime.now() - timedelta(days=91)


class OrganizationCleanupTestBase(APITestCase):
    endpoint = "sentry-api-0-organization-cleanup"

    def setUp(self):
        super().setUp()
        self.login_as(self.user)


class OrganizationCleanupTest(OrganizationCleanupTestBase):
    def test_simple(self):
        # Newly created projects, teams, and users are not considered for deletion
        response = self.get_success_response(self.organization.slug, category="projects")
        assert response.data["projects"] == []

        response = self.get_success_response(self.organization.slug, category="teams")
        assert response.data["teams"] == []

    def test_projects_without_first_event(self):
        project = self.create_project(
            organization=self.organization, first_event=None, date_added=DAYS_AGO_91
        )

        response = self.get_success_response(self.organization.slug, category="projects")
        projects = response.data["projects"]
        assert len(projects) == 1
        assert projects[0]["id"] == str(project.id)
        assert projects[0]["firstEvent"] is None

    def test_projects_without_events_in_90_days(self):
        project = self.create_project(
            organization=self.organization, first_event=datetime.now(), date_added=DAYS_AGO_91
        )

        assert Group.objects.filter(project=project).count() == 0

        response = self.get_success_response(self.organization.slug, category="projects")
        projects = response.data["projects"]
        assert len(projects) == 1
        assert projects[0]["id"] == str(project.id)

    def test_skips_projects_with_events(self):
        project = self.create_project(organization=self.organization, date_added=DAYS_AGO_91)

        self.store_event(data={}, project_id=project.id)
        assert Group.objects.filter(project=project).count() == 1

        response = self.get_success_response(self.organization.slug, category="projects")
        assert response.data["projects"] == []

    def test_multiple_projects(self):
        # Project with no first event
        project_1 = self.create_project(
            organization=self.organization, first_event=None, date_added=DAYS_AGO_91
        )

        # Project with no events in 90 days
        project_2 = self.create_project(
            organization=self.organization, first_event=DAYS_AGO_91, date_added=DAYS_AGO_91
        )

        assert Group.objects.filter(project=project_2).count() == 0

        response = self.get_success_response(self.organization.slug, category="projects")
        projects = response.data["projects"]
        assert len(projects) == 2
        assert projects[0]["id"] == str(project_1.id)
        assert projects[1]["id"] == str(project_2.id)

    def test_teams_with_no_projects(self):
        team = self.create_team(organization=self.organization, date_added=DAYS_AGO_91)
        self.create_team_membership(team=team, user=self.user)

        assert len(team.member_set) == 1

        response = self.get_success_response(self.organization.slug, category="teams")
        teams = response.data["teams"]
        assert len(teams) == 1
        assert teams[0]["id"] == str(team.id)

    def test_teams_with_no_members(self):
        team = self.create_team(organization=self.organization, date_added=DAYS_AGO_91)
        assert len(team.member_set) == 0

        response = self.get_success_response(self.organization.slug, category="teams")
        teams = response.data["teams"]
        assert len(teams) == 1
        assert teams[0]["id"] == str(team.id)

    def test_skips_teams_with_members_and_projects(self):
        team = self.create_team(organization=self.organization, date_added=DAYS_AGO_91)
        self.create_team_membership(team=team, user=self.user)
        self.project.add_team(team)

        assert len(team.member_set) == 1

        response = self.get_success_response(self.organization.slug, category="teams")
        assert response.data["teams"] == []

    def test_multiple_teams(self):
        team_1 = self.create_team(organization=self.organization, date_added=DAYS_AGO_91)
        self.project.add_team(team_1)

        team_2 = self.create_team(organization=self.organization, date_added=DAYS_AGO_91)
        self.create_team_membership(team=team_2, user=self.user)

        response = self.get_success_response(self.organization.slug, category="teams")
        teams = response.data["teams"]
        assert len(teams) == 2
        assert teams[0]["id"] == str(team_1.id)
        assert teams[1]["id"] == str(team_2.id)

    def test_users_with_no_activity(self):
        user = self.create_user(last_active=DAYS_AGO_91)
        member = self.create_member(organization=self.organization, user=user)

        response = self.get_success_response(self.organization.slug, category="members")
        members = response.data["members"]
        assert len(members) == 1
        assert members[0]["id"] == str(member.id)

    def test_skips_users_with_activity(self):
        response = self.get_success_response(self.organization.slug, category="members")
        assert response.data["members"] == []

    def test_multiple_users(self):
        user_1 = self.create_user(last_active=DAYS_AGO_91)
        member_1 = self.create_member(organization=self.organization, user=user_1)

        user_2 = self.create_user(last_active=DAYS_AGO_91)
        member_2 = self.create_member(organization=self.organization, user=user_2)

        response = self.get_success_response(self.organization.slug, category="members")
        members = response.data["members"]
        assert len(members) == 2
        assert members[0]["id"] == str(member_1.id)
        assert members[1]["id"] == str(member_2.id)

    def test_invalid_category(self):
        response = self.get_error_response(self.organization.slug, category="invalid")
        assert response.status_code == 400
        assert response.data["detail"] == "Invalid category"

    def test_no_category(self):
        response = self.get_error_response(self.organization.slug)
        assert response.status_code == 400
        assert response.data["detail"] == "Category is required"
