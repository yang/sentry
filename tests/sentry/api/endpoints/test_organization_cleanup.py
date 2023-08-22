from datetime import datetime, timedelta

from sentry.models import Group
from sentry.testutils.cases import APITestCase
from sentry.testutils.silo import region_silo_test

DAYS_AGO_91 = datetime.now() - timedelta(days=91)


class OrganizationCleanupTestBase(APITestCase):
    endpoint = "sentry-api-0-organization-cleanup"

    def setUp(self):
        super().setUp()
        self.login_as(self.user)


@region_silo_test(stable=True)
class OrganizationCleanupTest(OrganizationCleanupTestBase):
    def test_simple(self):
        response = self.get_success_response(self.organization.slug, category="projects")
        assert response.data["projects"] == []

        response = self.get_success_response(self.organization.slug, category="teams")
        assert response.data["teams"] == []

    def test_projects_without_first_event(self):
        project = self.create_project(organization=self.organization, first_event=None)
        project.date_added = DAYS_AGO_91
        project.save()

        response = self.get_success_response(self.organization.slug, category="projects")
        projects = response.data["projects"]
        assert len(projects) == 1
        assert projects[0]["id"] == str(project.id)
        assert projects[0]["firstEvent"] is None

    def test_projects_without_events_in_90_days(self):
        project = self.create_project(organization=self.organization, first_event=datetime.now())
        project.date_added = DAYS_AGO_91
        project.save()

        assert Group.objects.filter(project=project).count() == 0

        response = self.get_success_response(self.organization.slug, category="projects")
        projects = response.data["projects"]
        assert len(projects) == 1
        assert projects[0]["id"] == str(project.id)

    def test_skips_projects_with_events(self):
        project = self.create_project(organization=self.organization)
        project.date_added = DAYS_AGO_91
        project.save()

        self.store_event(data={}, project_id=project.id)
        assert Group.objects.filter(project=project).count() == 1

        response = self.get_success_response(self.organization.slug, category="projects")
        assert response.data["projects"] == []

    def test_multiple_projects(self):
        # Project with no first event
        project_1 = self.create_project(organization=self.organization, first_event=None)
        project_1.date_added = DAYS_AGO_91
        project_1.save()

        # Project with no events in 90 days
        project_2 = self.create_project(organization=self.organization, first_event=DAYS_AGO_91)
        project_2.date_added = DAYS_AGO_91
        project_2.save()

        assert Group.objects.filter(project=project_2).count() == 0

        response = self.get_success_response(self.organization.slug, category="projects")
        projects = response.data["projects"]
        assert len(projects) == 2
        assert projects[0]["id"] == str(project_1.id)
        assert projects[1]["id"] == str(project_2.id)

    def test_invalid_category(self):
        response = self.get_error_response(self.organization.slug, category="invalid")
        assert response.status_code == 400
        assert response.data["detail"] == "Invalid category"

    def test_no_category(self):
        response = self.get_error_response(self.organization.slug)
        assert response.status_code == 400
        assert response.data["detail"] == "Category is required"
