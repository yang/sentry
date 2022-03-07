from rest_framework.request import Request
from rest_framework.response import Response

from sentry.api.bases import ProjectEndpoint
from sentry.api.exceptions import ResourceDoesNotExist
from sentry.api.serializers.base import serialize
from sentry.replay.models import ReplaySession
from sentry.replay.serializers import *  # NOQA


# TODO: switch to using sessionId instead of replay pk, gather all rows
class ProjectReplayDetailsEndpoint(ProjectEndpoint):
    def get(self, request: Request, project, replay_id) -> Response:
        try:
            replay_session = ReplaySession.objects.get(project=project, id=replay_id)
        except ReplaySession.DoesNotExist:
            raise ResourceDoesNotExist
        return Response(serialize(replay_session))
