import logging

from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import View

from sentry.mediators import GrantTypes
from sentry.models import ApiApplication, ApiApplicationStatus, ApiGrant, ApiToken, OpenIDToken
from sentry.utils import json

logger = logging.getLogger("sentry.api")


from rest_framework.request import Request


class OAuthTokenView(View):
    @csrf_exempt
    @never_cache
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    # Note: the reason parameter is for internal use only
    def error(self, request: Request, name, reason=None, status=400):
        client_id = request.POST.get("client_id")
        redirect_uri = request.POST.get("redirect_uri")

        logging.error(
            "oauth.token-error",
            extra={
                "error_name": name,
                "status": status,
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "reason": reason,
            },
        )
        return HttpResponse(
            json.dumps({"error": name}), content_type="application/json", status=status
        )

    @never_cache
    def post(self, request: Request) -> HttpResponse:
        grant_type = request.POST.get("grant_type")

        id_token = None
        if grant_type == GrantTypes.AUTHORIZATION:
            grant = self._get_grant(request)
            if type(grant) != ApiGrant:
                return grant
            access_token_or_error = ApiToken.from_grant(grant)
            if grant.has_scope("openid"):
                id_token = self._get_id_token
        elif grant_type == "refresh_token":
            access_token_or_error = self._get_refresh_token(request)
        else:
            return self.error(request, "unsupported_grant_type")

        if type(access_token_or_error) != ApiToken:
            return access_token_or_error

        return self._process_token_details(access_token_or_error, id_token)

    def _get_grant(self, request):
        client_id = request.POST.get("client_id")
        redirect_uri = request.POST.get("redirect_uri")
        code = request.POST.get("code")

        if not client_id:
            return self.error(request, "invalid_client", "missing client_id")
        try:
            application = ApiApplication.objects.get(
                client_id=client_id, status=ApiApplicationStatus.active
            )
        except ApiApplication.DoesNotExist:
            return self.error(request, "invalid_client", "invalid client_id")

        try:
            grant = ApiGrant.objects.get(application=application, code=code)
        except ApiGrant.DoesNotExist:
            return self.error(request, "invalid_grant", "invalid grant")

        if grant.is_expired():
            return self.error(request, "invalid_grant", "grant expired")

        if not redirect_uri:
            redirect_uri = application.get_default_redirect_uri()
        elif grant.redirect_uri != redirect_uri:
            return self.error(request, "invalid_grant", "invalid redirect_uri")

        return grant

    def _get_refresh_token(self, request):
        refresh_token = request.POST.get("refresh_token")
        scope = request.POST.get("scope")
        client_id = request.POST.get("client_id")

        if not refresh_token:
            return self.error(request, "invalid_request")

        # TODO(dcramer): support scope
        if scope:
            return self.error(request, "invalid_request")

        if not client_id:
            return self.error(request, "invalid_client", "missing client_id")

        try:
            application = ApiApplication.objects.get(
                client_id=client_id, status=ApiApplicationStatus.active
            )
        except ApiApplication.DoesNotExist:
            return self.error(request, "invalid_client", "invalid client_id")

        try:
            token = ApiToken.objects.get(application=application, refresh_token=refresh_token)
        except ApiToken.DoesNotExist:
            return self.error(request, "invalid_grant", "invalid token")

        token.refresh()

        return token

    def _get_open_id_token(self, request):
        open_id_token = OpenIDToken.objects.create(
            user="temp",  # Find out how to get the user in here
            aud=request.POST.get("client_id"),
            nonce=request.POST.get("nonce"),
        )
        return open_id_token.get_encrypted_id_token()

    def _process_token_details(self, token, id_token=None):
        token_information = {
            "access_token": token.token,
            "refresh_token": token.refresh_token,
            "expires_in": int((token.expires_at - timezone.now()).total_seconds())
            if token.expires_at
            else None,
            "expires_at": token.expires_at,
            "token_type": "bearer",
            "scope": " ".join(token.get_scopes()),
            "user": {
                "id": str(token.user.id),
                # we might need these to become scope based
                "name": token.user.name,
                "email": token.user.email,
            },
        }
        if id_token:
            token_information["id_token"] = id_token
        return HttpResponse(
            json.dumps(token_information),
            content_type="application/json",
        )
