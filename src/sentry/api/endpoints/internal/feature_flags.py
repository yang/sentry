import sys

from django.conf import settings
from rest_framework.request import Request
from rest_framework.response import Response

from sentry.api.base import Endpoint, all_silo_endpoint
from sentry.api.permissions import SuperuserPermission
from sentry.app import env
from sentry.conf.server import SENTRY_FEATURES_DESCRIPTIONS
from django.conf import settings


@all_silo_endpoint
class InternalFeatureFlagsEndpoint(Endpoint):
    permission_classes = (SuperuserPermission,)

    def get(self, request: Request) -> Response:
        result = {}
        for key in SENTRY_FEATURES_DESCRIPTIONS:
            result[key] = {
                "value": settings.SENTRY_FEATURES.get(key, False),
                "description": SENTRY_FEATURES_DESCRIPTIONS[key],
            }
        return Response(result)
