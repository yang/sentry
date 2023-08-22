from sentry.testutils.cases import APITestCase
from sentry.testutils.silo import region_silo_test


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

    def test_invalid_category(self):
        response = self.get_error_response(self.organization.slug, category="invalid")
        assert response.status_code == 400
        assert response.data["detail"] == "Invalid category"

    def test_no_category(self):
        response = self.get_error_response(self.organization.slug)
        assert response.status_code == 400
        assert response.data["detail"] == "Category is required"
