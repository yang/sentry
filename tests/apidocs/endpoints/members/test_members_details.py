from django.test.client import RequestFactory
from django.urls import reverse

from tests.apidocs.util import APIDocsTestCase


class OrganizationMemberDetailsDocs(APIDocsTestCase):
    def setUp(self):
        self.login_as(user=self.user)
        self.member = self.create_member(user=self.create_user(), organization=self.organization)
        self.project = self.create_project(teams=[self.team])

        self.url = reverse(
            "sentry-api-0-organization-member-details",
            kwargs={"organization_slug": self.organization.slug, "member_id": self.member.id},
        )

    def test_put(self):
        data = {"role": "admin", "teams": [self.team.slug]}
        response = self.client.put(self.url, data)
        request = RequestFactory().put(self.url, data)

        self.validate_schema(request, response)
