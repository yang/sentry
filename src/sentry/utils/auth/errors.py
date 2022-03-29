from __future__ import annotations

import logging
from typing import Any, Mapping

from rest_framework.request import Request

from sentry.auth.exceptions import IdentityNotValid
from sentry.shared_integrations.exceptions import ApiError

logger = logging.getLogger(__name__)


def handle_refresh_error(
    request: Request,
    payload: Mapping[str, Any],
    provider_key: str | None = None,
) -> None:
    if request.status_code == 200:
        return None

    error_name = "unknown_error"
    error_description = "no description available"
    for name_key in ["error", "Error"]:
        if name_key in payload:
            error_name = payload.get(name_key)
            break

    for desc_key in ["error_description", "ErrorDescription"]:
        if desc_key in payload:
            error_description = payload.get(desc_key)
            break

    formatted_error = f"HTTP {request.status_code} ({error_name}): {error_description}"
    if request.status_code == 401 or (
        # This may not be common, but at the very least Google will return
        # an invalid grant when a user is suspended.
        request.status_code == 400
        and error_name == "invalid_grant"
    ):
        error_key = "identity.oauth.refresh.identity-not-valid-error"
        error_class = IdentityNotValid
    else:
        error_key = "identity.oauth.refresh.api-error"
        error_class = ApiError

    if provider_key:
        logger.info(
            error_key,
            extra={
                "error_name": error_name,
                "error_status_code": request.status_code,
                "error_description": error_description,
                "provider_key": provider_key,
            },
        )
    raise error_class(formatted_error)
