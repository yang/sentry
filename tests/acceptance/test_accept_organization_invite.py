# from django.db.models import F

# from sentry.models import AuthProvider, Organization

# from sentry.testutils.silo import region_silo_test
import time

from django.conf import settings
from django.contrib.auth import login
from django.core import signing

from sentry.auth.superuser import COOKIE_DOMAIN as SU_COOKIE_DOMAIN
from sentry.auth.superuser import COOKIE_NAME as SU_COOKIE_NAME
from sentry.auth.superuser import COOKIE_PATH as SU_COOKIE_PATH
from sentry.auth.superuser import COOKIE_SALT as SU_COOKIE_SALT
from sentry.auth.superuser import COOKIE_SECURE as SU_COOKIE_SECURE
from sentry.auth.superuser import ORG_ID as SU_ORG_ID

# from sentry.testutils import AcceptanceTestCase
from sentry.testutils import BaseTestCase
from sentry.testutils.factories import Factories
from sentry.testutils.silo import exempt_from_silo_limits
from sentry.utils.auth import SsoSession

# @region_silo_test
"""
def setUp(self):
    super().setUp()
    self.user = self.create_user("foo@example.com")
    self.org = self.create_organization(name="Rowdy Tiger", owner=None)
    self.team = self.create_team(organization=self.org, name="Mariachi Band")
    self.member = self.create_member(
        user=None,
        email="bar@example.com",
        organization=self.org,
        role="owner",
        teams=[self.team],
    )
"""
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest

from sentry.auth.superuser import Superuser

session = Factories.create_session()


def make_request(user=None, auth=None, method=None, is_superuser=False, path="/"):
    request = HttpRequest()
    if method:
        request.method = method
    request.path = path
    request.META["REMOTE_ADDR"] = "127.0.0.1"
    request.META["SERVER_NAME"] = "testserver"
    request.META["SERVER_PORT"] = 80

    # order matters here, session -> user -> other things
    request.session = Factories.create_session()
    request.auth = auth
    request.user = user or AnonymousUser()
    # must happen after request.user/request.session is populated
    request.superuser = Superuser(request)
    if is_superuser:
        # XXX: this is gross, but its a one off and apis change only once in a great while
        request.superuser.set_logged_in(user)
    request.is_superuser = lambda: request.superuser.is_active
    request.successful_authenticator = None
    return request


def save_cookie(browser, name, value, server_url, **params):
    print(f"SAVE_COOKIE {name}={value}")
    browser.save_cookie(name=name, value=value, server_url=server_url, **params)


def save_session(client, browser, server_url):
    session.save()
    save_cookie(
        browser,
        name=settings.SESSION_COOKIE_NAME,
        value=session.session_key,
        server_url=server_url,
    )
    print(f"client.cookies {settings.SESSION_COOKIE_NAME}={session.session_key}")
    # Forward session cookie to django client.
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key


def login_as(
    client,
    server_url,
    browser,
    user,
    organization_id=None,
    organization_ids=None,
    superuser=False,
    superuser_sso=True,
):
    user.backend = settings.AUTHENTICATION_BACKENDS[0]
    print(f"user.backend => {user.backend}")

    request = make_request()
    with exempt_from_silo_limits():
        print("HELLLLLLOOOOO??????")
        login(request, user)
    request.user = user

    if organization_ids is None:
        organization_ids = set()
    else:
        organization_ids = set(organization_ids)
    if superuser and superuser_sso is not False:
        if SU_ORG_ID:
            organization_ids.add(SU_ORG_ID)
    if organization_id:
        organization_ids.add(organization_id)

    # TODO(dcramer): ideally this would get abstracted
    if organization_ids:
        for o in organization_ids:
            sso_session = SsoSession.create(o)
            session[sso_session.session_key] = sso_session.to_dict()

    # logging in implicitly binds superuser, but for test cases we
    # want that action to be explicit to avoid accidentally testing
    # superuser-only code
    if not superuser:
        # XXX(dcramer): we're calling the internal method to avoid logging
        request.superuser._set_logged_out()
    elif request.user.is_superuser and superuser:
        request.superuser.set_logged_in(request.user)
        # XXX(dcramer): awful hack to ensure future attempts to instantiate
        # the Superuser object are successful
        save_cookie(
            name=SU_COOKIE_NAME,
            value=signing.get_cookie_signer(salt=SU_COOKIE_NAME + SU_COOKIE_SALT).sign(
                request.superuser.token
            ),
            server_url=server_url,
            max_age=None,
            path=SU_COOKIE_PATH,
            domain=SU_COOKIE_DOMAIN,
            secure=SU_COOKIE_SECURE or None,
            expires=None,
        )
    # Save the session values.
    save_session(client, browser, server_url)


def test_invite_simple(client, live_server, session_browser):
    user = Factories.create_user("foo@example.com")
    org = Factories.create_organization(name="Rowdy Tiger", owner=None)
    team = Factories.create_team(organization=org, name="Mariachi Band")
    member = Factories.create_member(
        user=None,
        email="bar@example.com",
        organization=org,
        role="owner",
        teams=[team],
    )

    login_as(client, live_server.url, session_browser, user)
    session_browser.get(live_server.url, member.get_invite_link().split("/", 3)[-1])
    session_browser.wait_until('[data-test-id="accept-invite"]')
    session_browser.snapshot(name="accept organization invite")
    time.sleep(60)
    assert session_browser.element_exists('[data-test-id="join-organization"]')


"""
    def test_invite_not_authenticated(self):
        self.browser.get(self.member.get_invite_link().split("/", 3)[-1])
        self.browser.wait_until('[data-test-id="accept-invite"]')
        assert self.browser.element_exists('[data-test-id="create-account"]')

    def test_invite_2fa_enforced_org(self):
        self.org.update(flags=F("flags").bitor(Organization.flags.require_2fa))
        self.browser.get(self.member.get_invite_link().split("/", 3)[-1])
        self.browser.wait_until('[data-test-id="accept-invite"]')
        assert not self.browser.element_exists_by_test_id("2fa-warning")

        self.login_as(self.user)
        self.org.update(flags=F("flags").bitor(Organization.flags.require_2fa))
        self.browser.get(self.member.get_invite_link().split("/", 3)[-1])
        self.browser.wait_until('[data-test-id="accept-invite"]')
        assert self.browser.element_exists_by_test_id("2fa-warning")

    def test_invite_sso_org(self):
        AuthProvider.objects.create(organization=self.org, provider="google")
        self.browser.get(self.member.get_invite_link().split("/", 3)[-1])
        self.browser.wait_until('[data-test-id="accept-invite"]')
        assert self.browser.element_exists_by_test_id("action-info-sso")
        assert self.browser.element_exists('[data-test-id="sso-login"]')
"""
