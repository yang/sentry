from django.urls import reverse
from django.conf import settings

from django.http import (
    HttpResponseRedirect,
)

from sentry import features
from sentry.models.user import User
from sentry.services.hybrid_cloud.organization import organization_service
from sentry.auth.superuser import is_active_superuser
from sentry.utils import auth
from sentry.utils.auth import (
    get_login_redirect,
)
from sentry.web.frontend.new_auth.utils import redirect_with_headers


class UserDirector:
    def __init__(self, user: User):
        self.user: User = user

    def direct_user_to_next_page(self, request, organization, active_organization):
        """Returns the next page a user should see in their browser."""
        if not self.user.is_active:
            return HttpResponseRedirect(reverse("sentry-reactivate-account"))
        if organization:
            # Refresh the organization we fetched prior to login in order to check its login state.
            org_context = organization_service.get_organization_by_slug(
                user_id=request.user.id,
                slug=organization.slug,
                only_visible=False,
            )
            if org_context:
                if org_context.member and request.user and not is_active_superuser(request):
                    auth.set_active_org(request, org_context.organization.slug)

                if settings.SENTRY_SINGLE_ORGANIZATION:
                    om = organization_service.check_membership_by_email(
                        organization_id=org_context.organization.id, email=self.user.email
                    )

                    if om is None:
                        om = organization_service.check_membership_by_id(
                            organization_id=org_context.organization.id, user_id=self.user.id
                        )
                    if om is None or om.user_id is None:
                        request.session.pop("_next", None)

        # On login, redirect to onboarding
        if active_organization:
            if features.has(
                "organizations:customer-domains",
                active_organization.organization,
                actor=self.user,
            ):
                setattr(request, "subdomain", self.active_organization.organization.slug)
        return redirect_with_headers(get_login_redirect(request))
