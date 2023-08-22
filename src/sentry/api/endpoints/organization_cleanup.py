from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from sentry.api.bases.organization import OrganizationEndpoint
from sentry.api.serializers.base import serialize
from sentry.api.serializers.models.organization_member import OrganizationMemberSerializer
from sentry.api.serializers.models.project import ProjectSerializer
from sentry.api.serializers.models.team import TeamWithProjectsSerializer
from sentry.models import Group, Organization, Project, ProjectTeam, Team, TeamStatus, User


class OrganizationCleanupEndpoint(OrganizationEndpoint):
    def get(self, request: Request, organization):
        """
        Retrieve stale objects for an Organization
        ````````````````````````

        Return the projects, teams, or members in an individual organization that can be cleaned up.

        :pparam string organization_slug: the slug of the organization the
                                          team should be created for.

        :qparam category: the category of objects to cleanup.  Valid values
                            are 'projects', 'teams', and 'members'.
        :auth: required
        """
        category = request.GET.get("category")
        if not category:
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data={"detail": "Category is required"}
            )

        if category not in ("projects", "teams", "members"):
            return Response(status=status.HTTP_400_BAD_REQUEST, data={"detail": "Invalid category"})
        age_90_days = timezone.now() - timedelta(days=90)

        if category == "projects":
            projects = self.get_projects(request, organization)
            projects_to_delete = self.get_projects_to_delete(projects, age_90_days)

            serialized_projects = serialize(projects_to_delete, request.user, ProjectSerializer())
            return Response(serialize({"projects": serialized_projects}, request.user))

        if category == "teams":
            teams_to_delete = self.get_teams_to_delete(organization.id, age_90_days)

            serialized_teams = serialize(
                teams_to_delete, request.user, TeamWithProjectsSerializer()
            )
            return Response(serialize({"teams": serialized_teams}, request.user))

        if category == "members":
            members_to_delete = self.get_members_to_delete(organization, age_90_days)

            serialized_members = serialize(
                members_to_delete, request.user, OrganizationMemberSerializer()
            )
            return Response(serialize({"members": serialized_members}, request.user))

        return Response(status=status.HTTP_400_BAD_REQUEST, data={"details": "Not implemented"})

    def get_members_to_delete(self, organization: Organization, age_90_days) -> list[User]:
        """
        Returns a list of organization members that can be cleaned up.

        Members can be cleaned up if the corresponding user hasn't been active for 1 year.

        """
        user_ids = organization.member_set.values_list("user_id", flat=True)
        users = User.objects.filter(id__in=user_ids)

        user_ids_to_delete = {user.id for user in users if user.last_active < age_90_days}
        return list(organization.member_set.filter(user_id__in=user_ids_to_delete))

    def get_teams_to_delete(self, organization_id: int, age_90_days) -> list[Team]:
        """
        Returns a list of teams that can be cleaned up.

        Teams can be cleaned up if they are older than 90 days and they either
            - have no projects
            - have no members
        """
        teams = Team.objects.filter(
            organization_id=organization_id, status=TeamStatus.ACTIVE, date_added__lt=age_90_days
        )
        team_ids = {team.id for team in teams}
        team_ids_to_delete = {team.id for team in teams if not team.member_set.exists()}

        project_teams = set(
            ProjectTeam.objects.filter(team__in=teams).values_list("team_id", flat=True).distinct()
        )
        teams_without_projects = team_ids - project_teams
        team_ids_to_delete.update(teams_without_projects)

        return list(teams.filter(id__in=team_ids_to_delete))

    def get_projects_to_delete(self, projects: list[Project], age_90_days) -> list[Project]:
        """
        Returns a list of projects that can be cleaned up.

        Projects can be cleaned up if they are older than 90 days and
            - have never received an event
            - have no events in the past 90 days
        """
        deletable_project_ids = {
            project.id
            for project in projects
            if project.date_added < age_90_days and not project.is_internal_project()
        }

        projects_with_groups = (
            Group.objects.filter(project_id__in=deletable_project_ids, last_seen__gt=age_90_days)
            .values_list("project_id", flat=True)
            .distinct()
        )

        return [
            project
            for project in projects
            if project.id in (deletable_project_ids - set(projects_with_groups))
        ]
