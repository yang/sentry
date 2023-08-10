import sys
import os

import sentry
from django.conf import settings
from rest_framework.request import Request
from rest_framework.response import Response

from sentry.api.base import Endpoint, all_silo_endpoint
from sentry.api.permissions import SuperuserPermission
from sentry.app import env
from sentry.conf.server import SENTRY_FEATURES_DESCRIPTIONS
from sentry.runner.settings import configure, discover_configs


@all_silo_endpoint
class InternalFeatureFlagsEndpoint(Endpoint):
    permission_classes = (SuperuserPermission,)

    def get(self, request: Request) -> Response:
        result = {}
        print(settings.SENTRY_FEATURES)
        for key in SENTRY_FEATURES_DESCRIPTIONS:
            result[key] = {
                "value": settings.SENTRY_FEATURES.get(key, False),
                "description": SENTRY_FEATURES_DESCRIPTIONS[key],
            }

        return Response(result)

    def put(self, request: Request) -> Response:
        data = request.data.keys()
        valid_feature_flags = [
            flag for flag in data if SENTRY_FEATURES_DESCRIPTIONS.get(flag, False)
        ]
        _, py, yml = discover_configs()
        # Open the file for reading and writing
        with open(py, "r+") as file:
            lines = file.readlines()
            # print(lines)
            for valid_flag in valid_feature_flags:
                match_found = False
                new_string = (
                    f'\nSENTRY_FEATURES["{valid_flag}"]={request.data.get(valid_flag,False)}\n'
                )
                # Search for the string match and update lines
                for i, line in enumerate(lines):
                    if valid_flag in line:
                        match_found = True
                        lines[i] = new_string

                        break

                # If no match found, append a new line
                if not match_found:
                    lines.append(new_string)

                # Move the file pointer to the beginning and truncate the file
                file.seek(0)
                file.truncate()

                # Write modified lines back to the file
                file.writelines(lines)
                print("sucess")
                configure(None, py, yml)
            # # TODO: need to write to ~/.sentry/sentry.conf.py
            # settings.SENTRY_FEATURES[valid_flag] = request.data.get(valid_flag)
        return Response(status=200)
