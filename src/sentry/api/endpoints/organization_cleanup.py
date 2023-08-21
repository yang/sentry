from __future__ import annotations

from datetime import datetime, timedelta

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from sentry.api.bases.organization import OrganizationEndpoint
from sentry.models.project import Project
from sentry.models.team import Team
from sentry.models.user import User

AGE_90_DAYS = datetime.now() - timedelta(days=90)


class OrganizationCleanupEndpoint(OrganizationEndpoint):
    def get(self, request: Request, organization):
        """
        Retrieve stale objects for an Organization
        ````````````````````````

        Return the projects, teams, or users in an individual organization that can be cleaned up.

        :pparam string organization_slug: the slug of the organization the
                                          team should be created for.

        :qparam category: the category of objects to cleanup.  Valid values
                            are 'projects', 'teams', and 'users'.
        :auth: required
        """
        category = request.GET.get("category")
        if not category:
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data={"details": "Category is required"}
            )

        if category not in ("projects", "teams", "users"):
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data={"details": "Invalid category"}
            )

        return Response(status=status.HTTP_200_OK, data={"details": "Not implemented"})

    def get_users_to_delete(self, users: list[User]) -> list[User]:
        """
        Returns a list of users that can be cleaned up.

        Users can be cleaned up if they have not logged in for 1 year.

        """
        return []

    def get_teams_to_delete(self, teams: list[Team]) -> list[Team]:
        """
        Returns a list of teams that can be cleaned up.

        Teams can be cleaned up if they are older than 90 days and
            - have no projects
            - have no members
        """
        return []

    def get_projects_to_delete(self, projects: list[Project]) -> list[Project]:
        """
        Returns a list of projects that can be cleaned up.

        Projects can be cleaned up if they are older than 90 days and
            - have never received an event
            - have no events in the past 90 days
        """
        return []
