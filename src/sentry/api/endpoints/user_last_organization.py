import logging

from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from sentry.api.bases.user import UserEndpoint
from sentry.api.decorators import sudo_required
from sentry.api.serializers import serialize
from sentry.api.validators import AllowedEmailField
from sentry.models import User, UserEmail, UserOption
from sentry.web.frontend.base import OrganizationMixin


class UserLastOrganization(UserEndpoint, OrganizationMixin):
    def get(self, request: Request, user) -> Response:
        last_active_organization = self.get_active_organization(request)
        return self.respond(serialize(last_active_organization))
