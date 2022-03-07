from rest_framework import permissions
from rest_framework.request import Request

from sentry.api.bases import ProjectEndpoint
from sentry.api.paginator import OffsetPaginator
from sentry.api.serializers.base import serialize
from sentry.replay.models import ReplaySession


class P(permissions.BasePermission):
    def has_permission(self, request: Request, view):
        return True


class ProjectReplayIndexEndpoint(ProjectEndpoint):
    permission_classes = (P,)

    def get(self, request, project):
        queryset = ReplaySession.objects.filter(project=project)

        return self.paginate(
            request=request,
            queryset=queryset,
            on_results=lambda x: serialize(x, request.user),
            paginator_cls=OffsetPaginator,
        )
