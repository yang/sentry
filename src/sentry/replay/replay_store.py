from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.response import Response

from sentry.api.base import Endpoint
from sentry.replay.models import ReplayData, ReplaySession
from sentry.utils import json


class P(permissions.BasePermission):
    def has_permission(self, request: Request, view):
        return True


class ReplayStoreEndpoint(Endpoint):
    permission_classes = (P,)

    def post(self, request, project_id, session_id):

        try:
            replay_session = ReplaySession.objects.get(
                project=project_id, session_id=request.json_body["sessionId"]
            )
            replay_session.sentry_event_ids = (
                replay_session.sentry_event_ids + request.json_body["sentryEvents"]
            )
            replay_session.save()

        except ReplaySession.DoesNotExist:
            replay_session = ReplaySession(
                project_id=project_id,
                sentry_event_ids=request.json_body["sentryEvents"],
                session_id=request.json_body["sessionId"],
            )
            replay_session.save()

        replay_data = ReplayData(
            data=json.dumps(request.json_body["events"]), replay_session=replay_session
        )
        replay_data.save()

        return Response(201)
