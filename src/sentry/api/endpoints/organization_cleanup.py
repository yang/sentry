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
from sentry.api.serializers.models.team import TeamSerializer
from sentry.models import Group, Organization, Project, ProjectTeam, Team, TeamStatus, User

AGE_90_DAYS = timezone.now() - timedelta(days=90)


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
                status=status.HTTP_400_BAD_REQUEST, data={"detail": "Category is required"}
            )

        if category not in ("projects", "teams", "users"):
            return Response(status=status.HTTP_400_BAD_REQUEST, data={"detail": "Invalid category"})

        if category == "projects":
            projects = self.get_projects(request, organization)
            projects_to_delete = self.get_projects_to_delete(projects)

            serialized_projects = serialize(projects_to_delete, request.user, ProjectSerializer())
            return Response(serialize({"projects": serialized_projects}, request.user))

        if category == "teams":
            teams_to_delete = self.get_teams_to_delete(organization.id)

            serialized_teams = serialize(teams_to_delete, request.user, TeamSerializer())
            return Response(serialize({"teams": serialized_teams}, request.user))

        if category == "users":
            # We return the members here instead of the users because the remove method exists on OrganizationMember
            members_to_delete = self.get_members_to_delete(organization)

            serialized_members = serialize(
                members_to_delete, request.user, OrganizationMemberSerializer()
            )
            return Response(serialize({"users": serialized_members}, request.user))

        return Response(status=status.HTTP_400_BAD_REQUEST, data={"details": "Not implemented"})

    def get_members_to_delete(self, organization: Organization) -> list[User]:
        """
        Returns a list of organization members that can be cleaned up.

        Members can be cleaned up if the corresponding user hasn't been active for 1 year.

        """
        user_ids = organization.member_set.values_list("user_id", flat=True)
        users = User.objects.filter(id__in=user_ids)

        user_ids_to_delete = {user.id for user in users if user.last_active < AGE_90_DAYS}
        return list(organization.member_set.filter(user_id__in=user_ids_to_delete))

    def get_teams_to_delete(self, organization_id: int) -> list[Team]:
        """
        Returns a list of teams that can be cleaned up.

        Teams can be cleaned up if they are older than 90 days and they either
            - have no projects
            - have no members
        """
        teams = Team.objects.filter(
            organization_id=organization_id, status=TeamStatus.ACTIVE, date_added__lt=AGE_90_DAYS
        )
        team_ids = {team.id for team in teams}
        team_ids_to_delete = {team.id for team in teams if not team.member_set.exists()}

        project_teams = set(
            ProjectTeam.objects.filter(team__in=teams).values_list("team_id", flat=True).distinct()
        )
        teams_without_projects = team_ids - project_teams
        team_ids_to_delete.update(teams_without_projects)

        return list(teams.filter(id__in=team_ids_to_delete))

    def get_projects_to_delete(self, projects: list[Project]) -> list[Project]:
        """
        Returns a list of projects that can be cleaned up.

        Projects can be cleaned up if they are older than 90 days and
            - have never received an event
            - have no events in the past 90 days
        """
        project_ids_to_delete = {
            project.id
            for project in projects
            if project.date_added < AGE_90_DAYS and not project.first_event
        }
        project_ids = {project.id for project in projects}

        projects_with_groups = (
            Group.objects.filter(project__in=projects, last_seen__gt=AGE_90_DAYS)
            .values_list("project_id", flat=True)
            .distinct()
        )
        project_ids_to_delete.update(project_ids - set(projects_with_groups))
        return [project for project in projects if project.id in project_ids_to_delete]
