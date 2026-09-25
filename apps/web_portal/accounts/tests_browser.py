from __future__ import annotations

from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.test import Client, TestCase, override_settings

from apps.web_portal.accounts.models import User
from apps.web_portal.accounts.services import change_role, deactivate_user, set_user_password
from apps.web_portal.accounts.session_policy import (
    AUTHENTICATED_AT_KEY,
    LAST_ACTIVITY_AT_KEY,
    SESSION_UNAVAILABLE_MESSAGE,
)


PASSWORD = "T8!vQ4#nL6@zR2$k"
NEW_PASSWORD = "B7!mP9#xK2@qV5$w"
BASE_TIME = 2_000_000_000


@override_settings(DEBUG=False)
class BrowserAuthenticationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin.user", password=PASSWORD, role=User.Role.ADMIN
        )
        self.client_user = User.objects.create_user(
            username="client.user", password=PASSWORD, role=User.Role.CLIENT
        )
        self.support = User.objects.create_user(
            username="support.user", password=PASSWORD, role=User.Role.SUPPORT_AGENT
        )

    @staticmethod
    def _csrf(client: Client) -> str:
        client.get("/login/")
        return client.cookies[settings.CSRF_COOKIE_NAME].value

    def _login(self, client: Client, user: User, *, password: str = PASSWORD):
        token = self._csrf(client)
        return client.post(
            "/login/",
            {"username": user.username, "password": password, "csrfmiddlewaretoken": token},
            HTTP_X_CSRFTOKEN=token,
        )

    def test_login_page_is_accessible_semantic_and_contains_no_deferred_controls(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertContains(response, "Getnet Support")
        self.assertContains(response, 'for="id_username"')
        self.assertContains(response, 'for="id_password"')
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertContains(response, 'href="/password-reset/request/">Esqueci minha senha</a>')
        for forbidden in (
            "Remember me",
            "Cadastrar",
            "Criar conta",
            "Signup",
            "AGENT_API_SERVICE_TOKEN",
            "DEEPSEEK_API_KEY",
            "TAVILY_API_KEY",
            "POSTGRES_PASSWORD",
            "ops_authorized",
        ):
            self.assertNotIn(forbidden, html)

    def test_successful_login_destinations_are_server_derived_and_ignore_browser_role(self):
        expectations = (
            (self.client_user, "/chat/"),
            (self.support, "/support/"),
            (self.admin, "/admin-portal/"),
        )
        for user, destination in expectations:
            browser = Client(enforce_csrf_checks=True)
            token = self._csrf(browser)
            response = browser.post(
                "/login/?next=https://attacker.example/",
                {
                    "username": f"  {user.username.upper()}  ",
                    "password": PASSWORD,
                    "role": User.Role.ADMIN,
                    "next": "https://attacker.example/",
                    "csrfmiddlewaretoken": token,
                },
                HTTP_X_CSRFTOKEN=token,
            )
            self.assertRedirects(response, destination, fetch_redirect_response=False)

    def test_invalid_login_outcomes_are_generic_and_do_not_block(self):
        inactive = User.objects.create_user(
            username="inactive.user", password=PASSWORD, role=User.Role.CLIENT, is_active=False
        )
        cases = (
            ("missing.user", PASSWORD),
            (self.client_user.username, "wrong-password"),
            ("   ", PASSWORD),
            (inactive.username, PASSWORD),
        )
        for username, password in cases:
            browser = Client(enforce_csrf_checks=True)
            token = self._csrf(browser)
            response = browser.post(
                "/login/",
                {"username": username, "password": password, "csrfmiddlewaretoken": token},
                HTTP_X_CSRFTOKEN=token,
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Usuário ou senha inválidos.")
            self.assertNotContains(response, password)
        self.client_user.refresh_from_db()
        self.assertTrue(self.client_user.is_active)

    def test_malformed_role_fails_closed(self):
        from apps.web_portal.accounts.views import landing_for_role

        self.assertIsNone(landing_for_role("UNKNOWN"))

    def test_anonymous_and_wrong_role_matrices(self):
        for path in ("/chat/", "/support/", "/admin-portal/"):
            response = self.client.get(path)
            self.assertRedirects(response, "/login/", fetch_redirect_response=False)

        matrix = (
            (self.client_user, {"/chat/": 200, "/support/": 403, "/admin-portal/": 403}),
            (self.support, {"/chat/": 403, "/support/": 200, "/admin-portal/": 403}),
            (self.admin, {"/chat/": 403, "/support/": 403, "/admin-portal/": 200}),
        )
        for user, routes in matrix:
            browser = Client()
            browser.force_login(user)
            for path, expected in routes.items():
                response = browser.get(path)
                self.assertEqual(response.status_code, expected)
                if expected == 403:
                    self.assertContains(
                        response,
                        "Você não possui permissão para acessar esta área.",
                        status_code=403,
                    )

    def test_wrong_role_denial_does_not_refresh_inactivity(self):
        browser = Client()
        with patch(
            "apps.web_portal.accounts.session_policy.current_timestamp", return_value=BASE_TIME
        ):
            self._login(browser, self.client_user)
        with patch(
            "apps.web_portal.accounts.session_policy.current_timestamp",
            return_value=BASE_TIME + 60,
        ):
            self.assertEqual(browser.get("/support/").status_code, 403)
        self.assertEqual(browser.session[LAST_ACTIVITY_AT_KEY], BASE_TIME)

    def test_technical_admin_remains_active_admin_only(self):
        for user, allowed in (
            (self.admin, True),
            (self.client_user, False),
            (self.support, False),
        ):
            browser = Client()
            browser.force_login(user)
            response = browser.get("/admin/")
            self.assertEqual(response.status_code, 200 if allowed else 403)

        self.admin.is_active = False
        self.admin.save(update_fields={"is_active", "updated_at"})
        browser = Client()
        browser.force_login(self.admin)
        self.assertEqual(browser.get("/admin/").status_code, 302)

    def test_login_rotates_session_and_logout_requires_csrf_then_invalidates(self):
        browser = Client(enforce_csrf_checks=True)
        seed = browser.session
        seed["pre_auth"] = "synthetic"
        seed.save()
        old_key = seed.session_key

        response = self._login(browser, self.client_user)
        self.assertRedirects(response, "/chat/", fetch_redirect_response=False)
        new_key = browser.session.session_key
        self.assertNotEqual(old_key, new_key)
        self.assertFalse(Session.objects.filter(session_key=old_key).exists())
        self.assertIn(AUTHENTICATED_AT_KEY, browser.session)
        self.assertIn(LAST_ACTIVITY_AT_KEY, browser.session)

        self.assertEqual(browser.post("/logout/").status_code, 403)
        token = browser.cookies[settings.CSRF_COOKIE_NAME].value
        response = browser.post(
            "/logout/",
            {"csrfmiddlewaretoken": token},
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertRedirects(response, "/login/", fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, browser.session)
        self.assertRedirects(browser.get("/chat/"), "/login/", fetch_redirect_response=False)
        self.assertEqual(browser.get("/logout/").status_code, 405)

    def test_login_requires_csrf(self):
        browser = Client(enforce_csrf_checks=True)
        response = browser.post(
            "/login/", {"username": self.client_user.username, "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 403)

    def test_deactivated_user_loses_existing_browser_session_with_safe_message(self):
        browser = Client()
        self._login(browser, self.client_user)
        self.assertEqual(browser.get("/chat/").status_code, 200)
        deactivate_user(actor=self.admin, target=self.client_user)
        response = browser.get("/chat/", follow=True)
        self.assertRedirects(response, "/login/")
        self.assertContains(response, SESSION_UNAVAILABLE_MESSAGE)
        self.assertNotIn(SESSION_KEY, browser.session)

    def test_role_change_revokes_session_and_new_login_uses_new_landing(self):
        browser = Client()
        self._login(browser, self.client_user)
        self.assertEqual(browser.get("/chat/").status_code, 200)
        change_role(actor=self.admin, target=self.client_user, new_role=User.Role.SUPPORT_AGENT)
        self.assertRedirects(browser.get("/chat/"), "/login/", fetch_redirect_response=False)
        response = self._login(browser, self.client_user)
        self.assertRedirects(response, "/support/", fetch_redirect_response=False)

    def test_password_change_revokes_session_and_replaces_credential(self):
        browser = Client()
        self._login(browser, self.client_user)
        set_user_password(actor=self.admin, target=self.client_user, new_password=NEW_PASSWORD)
        self.assertRedirects(browser.get("/chat/"), "/login/", fetch_redirect_response=False)
        self.assertEqual(self._login(Client(), self.client_user).status_code, 200)
        response = self._login(Client(), self.client_user, password=NEW_PASSWORD)
        self.assertRedirects(response, "/chat/", fetch_redirect_response=False)

    def test_inactivity_boundary_and_safe_expiry(self):
        browser = Client()
        with patch(
            "apps.web_portal.accounts.session_policy.current_timestamp", return_value=BASE_TIME
        ):
            self._login(browser, self.client_user)
        with patch(
            "apps.web_portal.accounts.session_policy.current_timestamp",
            return_value=BASE_TIME + 29 * 60 + 59,
        ):
            self.assertEqual(browser.get("/chat/").status_code, 200)
        session = browser.session
        session[LAST_ACTIVITY_AT_KEY] = BASE_TIME
        session.save()
        with patch(
            "apps.web_portal.accounts.session_policy.current_timestamp",
            return_value=BASE_TIME + 30 * 60,
        ):
            response = browser.get("/chat/", follow=True)
        self.assertRedirects(response, "/login/")
        self.assertContains(response, SESSION_UNAVAILABLE_MESSAGE)

    def test_absolute_boundary_is_independent_of_recent_activity(self):
        browser = Client()
        with patch(
            "apps.web_portal.accounts.session_policy.current_timestamp", return_value=BASE_TIME
        ):
            self._login(browser, self.client_user)

        session = browser.session
        session[LAST_ACTIVITY_AT_KEY] = BASE_TIME + 7 * 60 * 60 + 50 * 60
        session.save()
        with patch(
            "apps.web_portal.accounts.session_policy.current_timestamp",
            return_value=BASE_TIME + 8 * 60 * 60 - 1,
        ):
            self.assertEqual(browser.get("/chat/").status_code, 200)

        session = browser.session
        self.assertEqual(session[AUTHENTICATED_AT_KEY], BASE_TIME)
        session[LAST_ACTIVITY_AT_KEY] = BASE_TIME + 8 * 60 * 60 - 1
        session.save()
        with patch(
            "apps.web_portal.accounts.session_policy.current_timestamp",
            return_value=BASE_TIME + 8 * 60 * 60,
        ):
            response = browser.get("/chat/", follow=True)
        self.assertRedirects(response, "/login/")
        self.assertContains(response, SESSION_UNAVAILABLE_MESSAGE)

    def test_cookie_policy_has_fixed_server_limits_and_no_browser_duration_control(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.PORTAL_SESSION_INACTIVITY_SECONDS, 1800)
        self.assertEqual(settings.PORTAL_SESSION_ABSOLUTE_SECONDS, 28800)
        self.assertFalse(settings.SESSION_COOKIE_SECURE)

        response = self.client.get("/login/")
        html = response.content.decode().lower()
        self.assertNotIn("remember", html)
        self.assertNotIn("session_cookie_age", html)

    @override_settings(SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
    def test_secure_cookie_mode_is_supported_for_https_deployment(self):
        browser = Client(enforce_csrf_checks=True)
        response = browser.get("/login/", secure=True)
        self.assertTrue(response.cookies[settings.CSRF_COOKIE_NAME]["secure"])
        token = browser.cookies[settings.CSRF_COOKIE_NAME].value
        response = browser.post(
            "/login/",
            {"username": self.client_user.username, "password": PASSWORD, "csrfmiddlewaretoken": token},
            HTTP_X_CSRFTOKEN=token,
            HTTP_REFERER="https://testserver/login/",
            secure=True,
        )
        self.assertRedirects(response, "/chat/", fetch_redirect_response=False)
        self.assertTrue(browser.cookies[settings.SESSION_COOKIE_NAME]["secure"])

    def test_registration_routes_do_not_exist_and_password_request_requires_confirmation(self):
        before = User.objects.count()
        for path in (
            "/register/",
            "/signup/",
            "/create-account/",
        ):
            self.assertEqual(self.client.get(path).status_code, 404)
            self.assertEqual(self.client.post(path, {"username": "intruder"}).status_code, 404)
        self.assertEqual(self.client.get("/password-reset/request/").status_code, 200)
        first_step = self.client.post("/password-reset/request/", {"username": "intruder"})
        self.assertEqual(first_step.status_code, 200)
        self.assertContains(first_step, "Confirmar solicitação")
        self.assertEqual(
            self.client.post(
                "/password-reset/request/confirm/",
                {"username": "intruder", "confirm_request": "on"},
            ).status_code,
            200,
        )
        self.assertEqual(User.objects.count(), before)
