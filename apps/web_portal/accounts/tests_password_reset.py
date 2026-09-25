from __future__ import annotations

from django.conf import settings
from django.contrib.sessions.models import Session
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.web_portal.accounts.models import User
from apps.web_portal.accounts.password_reset_services import (
    PasswordResetRequestConflict,
    PasswordResetRequestFilters,
    SubmissionDisposition,
    list_password_reset_requests,
    reject_password_reset_request,
    request_password_reset,
    resolve_password_reset_request,
)
from apps.web_portal.support.models import PasswordResetRequest


PASSWORD = "T8!vQ4#nL6@zR2$k"
NEW_PASSWORD = "R8!New-Password$Access517"


class PasswordResetBrowserTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="reset.admin", password=PASSWORD, role=User.Role.ADMIN
        )
        self.client_user = User.objects.create_user(
            username="reset.client", password=PASSWORD, role=User.Role.CLIENT
        )
        self.support = User.objects.create_user(
            username="reset.support", password=PASSWORD, role=User.Role.SUPPORT_AGENT
        )
        self.admin_browser = Client()
        self.admin_browser.force_login(self.admin)

    def _request(self, username: str, browser: Client | None = None):
        browser = browser or Client()
        before_count = PasswordResetRequest.objects.count()
        first = browser.post(reverse("password-reset-request"), {"username": username})
        self.assertEqual(first.status_code, 200)
        self.assertContains(first, "Confirmar solicitação")
        self.assertEqual(PasswordResetRequest.objects.count(), before_count)
        result = browser.post(
            reverse("password-reset-request-confirm"),
            {"username": username, "confirm_request": "on"},
        )
        self.assertEqual(result.status_code, 200)
        return result

    def test_two_step_public_request_creates_minimal_open_work_for_all_active_roles(self):
        for user in (self.client_user, self.support, self.admin):
            with self.subTest(role=user.role):
                before = PasswordResetRequest.objects.count()
                response = self._request(f"  {user.username.upper()}  ")
                self.assertContains(response, "Se os dados informados corresponderem a uma conta válida")
                self.assertEqual(PasswordResetRequest.objects.count(), before + 1)
                item = PasswordResetRequest.objects.latest("created_at")
                self.assertEqual(item.requester_id, user.pk)
                self.assertEqual(item.status, PasswordResetRequest.Status.OPEN)
                self.assertIsNone(item.resolved_at)
                self.assertIsNone(item.resolver_id)
                self.assertNotIn(str(item.pk), response.content.decode())

    def test_unknown_and_inactive_accounts_have_same_public_result_and_no_rows(self):
        inactive = User.objects.create_user(
            username="reset.inactive",
            password=PASSWORD,
            role=User.Role.CLIENT,
            is_active=False,
        )
        known = self._request(self.client_user.username)
        unknown = self._request("not.a.real.account")
        blocked = self._request(inactive.username)
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.status_code, blocked.status_code)
        self.assertEqual(known.content, unknown.content)
        self.assertEqual(known.content, blocked.content)
        self.assertEqual(
            PasswordResetRequest.objects.filter(requester=self.client_user).count(), 1
        )
        self.assertFalse(PasswordResetRequest.objects.filter(requester=inactive).exists())

    def test_public_post_requires_explicit_confirmation_and_is_csrf_protected(self):
        browser = Client(enforce_csrf_checks=True)
        self.assertEqual(browser.get(reverse("password-reset-request")).status_code, 200)
        missing_csrf = browser.post(reverse("password-reset-request"), {"username": self.client_user.username})
        self.assertEqual(missing_csrf.status_code, 403)
        token = browser.cookies[settings.CSRF_COOKIE_NAME].value
        first = browser.post(
            reverse("password-reset-request"),
            {"username": self.client_user.username},
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(first.status_code, 200)
        self.assertFalse(PasswordResetRequest.objects.exists())
        unconfirmed = browser.post(
            reverse("password-reset-request-confirm"),
            {"username": self.client_user.username},
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(unconfirmed.status_code, 400)
        self.assertFalse(PasswordResetRequest.objects.exists())
        confirmed = browser.post(
            reverse("password-reset-request-confirm"),
            {"username": self.client_user.username, "confirm_request": "on"},
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(PasswordResetRequest.objects.filter(requester=self.client_user).count(), 1)

    def test_repeated_public_submission_coalesces_open_work_and_terminal_allows_new_item(self):
        self._request(self.client_user.username)
        self._request(self.client_user.username.upper())
        self.assertEqual(PasswordResetRequest.objects.filter(requester=self.client_user).count(), 1)
        first = PasswordResetRequest.objects.get(requester=self.client_user)
        reject_password_reset_request(actor=self.admin, request_id=first.pk)
        self._request(self.client_user.username)
        self.assertEqual(PasswordResetRequest.objects.filter(requester=self.client_user).count(), 2)

    def test_public_unknown_input_is_not_reflected_and_html_is_escaped(self):
        attack = "<script>alert(12)</script>"
        form_page = self.client.post(reverse("password-reset-request"), {"username": attack})
        self.assertEqual(form_page.status_code, 200)
        self.assertNotContains(form_page, "<script>alert(12)</script>")
        self.assertContains(form_page, "&lt;script&gt;alert(12)&lt;/script&gt;")
        result = self.client.post(
            reverse("password-reset-request-confirm"),
            {"username": attack, "confirm_request": "on"},
        )
        self.assertEqual(result.status_code, 200)
        self.assertNotContains(result, attack)
        self.assertNotContains(result, "PasswordResetRequest")
        self.assertFalse(PasswordResetRequest.objects.exists())

    def test_overlong_identifier_is_rejected_before_work_item_creation(self):
        oversized = "x" * 151
        response = self.client.post(reverse("password-reset-request"), {"username": oversized})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "no máximo 150 caracteres", status_code=400)
        self.assertContains(response, f'value="{oversized}"', status_code=400)
        self.assertFalse(PasswordResetRequest.objects.exists())

    def test_admin_queue_auth_filters_pagination_order_and_xss(self):
        for index in range(27):
            requester = User.objects.create_user(
                username=f"queue.user.{index:02d}", password=PASSWORD, role=User.Role.CLIENT
            )
            PasswordResetRequest.objects.create(requester=requester)
        unsafe = User.objects.create_user(
            username="<script>alert(4)</script>", password=PASSWORD, role=User.Role.CLIENT
        )
        unsafe_request = PasswordResetRequest.objects.create(requester=unsafe)

        url = reverse("admin-password-requests")
        first = self.admin_browser.get(url)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.context["page_obj"].paginator.count, 28)
        self.assertEqual(len(first.context["page_obj"].object_list), 25)
        self.assertContains(first, "Próxima")
        self.assertNotContains(first, "<script>alert(4)</script>")
        xss_filter = self.admin_browser.get(
            url, {"status": "OPEN", "query": "<script>alert(4)</script>"}
        )
        self.assertEqual(xss_filter.context["page_obj"].paginator.count, 1)
        self.assertNotContains(xss_filter, "<script>alert(4)</script>")
        self.assertContains(xss_filter, "&lt;script&gt;alert(4)&lt;/script&gt;")
        second = self.admin_browser.get(url, {"status": "OPEN", "query": "queue.user", "page": 2})
        self.assertEqual(len(second.context["page_obj"].object_list), 2)
        resolved = PasswordResetRequest.objects.create(
            requester=self.client_user,
            status=PasswordResetRequest.Status.RESOLVED,
            resolver=self.admin,
            resolved_at=timezone.now(),
        )
        history = self.admin_browser.get(url, {"status": "RESOLVED"})
        self.assertEqual(list(history.context["page_obj"].object_list), [resolved])
        invalid = self.admin_browser.get(url, {"status": "ROOT"})
        self.assertEqual(invalid.status_code, 400)
        self.assertContains(invalid, "ROOT não é uma das escolhas disponíveis.", status_code=400)
        detail = self.admin_browser.get(
            reverse("admin-password-request-detail", args=(unsafe_request.pk,))
        )
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, "<script>alert(4)</script>")
        self.assertContains(detail, "&lt;script&gt;alert(4)&lt;/script&gt;")
        self.assertNotContains(detail, unsafe.password)

    def test_admin_role_matrix_and_anonymous_request_id_access(self):
        item = PasswordResetRequest.objects.create(requester=self.client_user)
        paths = (
            reverse("admin-password-requests"),
            reverse("admin-password-request-detail", args=(item.pk,)),
        )
        anonymous = Client()
        for path in paths:
            response = anonymous.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login/", response.url)
        for user in (self.client_user, self.support):
            browser = Client()
            browser.force_login(user)
            for path in paths:
                self.assertEqual(browser.get(path).status_code, 403)
            self.assertEqual(
                browser.post(
                    reverse("admin-password-request-reject", args=(item.pk,)),
                    {"confirm_rejection": "on"},
                ).status_code,
                403,
            )
        inactive_admin = User.objects.create_user(
            username="inactive.admin", password=PASSWORD, role=User.Role.ADMIN, is_active=False
        )
        browser = Client()
        browser.force_login(inactive_admin)
        self.assertEqual(browser.get(paths[0]).status_code, 302)

    def test_resolve_hashes_password_revokes_sessions_and_records_terminal_metadata(self):
        item = PasswordResetRequest.objects.create(requester=self.client_user)
        old_browser = Client()
        self.assertTrue(old_browser.login(username=self.client_user.username, password=PASSWORD))
        old_session_key = old_browser.cookies[settings.SESSION_COOKIE_NAME].value
        second_old_browser = Client()
        self.assertTrue(second_old_browser.login(username=self.client_user.username, password=PASSWORD))
        second_old_session_key = second_old_browser.cookies[settings.SESSION_COOKIE_NAME].value
        old_role = self.client_user.role
        old_active = self.client_user.is_active

        response = self.admin_browser.post(
            reverse("admin-password-request-resolve", args=(item.pk,)),
            {
                "new_password": NEW_PASSWORD,
                "confirm_password": NEW_PASSWORD,
                "confirm_resolution": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Senha redefinida.")
        self.assertNotContains(response, NEW_PASSWORD)
        self.assertNotIn(NEW_PASSWORD, repr(self.admin_browser.session.items()))
        item.refresh_from_db()
        self.client_user.refresh_from_db()
        self.assertEqual(item.status, PasswordResetRequest.Status.RESOLVED)
        self.assertEqual(item.resolver_id, self.admin.pk)
        self.assertIsNotNone(item.resolved_at)
        self.assertEqual(item.resolved_at.utcoffset(), timezone.get_current_timezone().utcoffset(item.resolved_at))
        self.assertTrue(self.client_user.check_password(NEW_PASSWORD))
        self.assertFalse(self.client_user.check_password(PASSWORD))
        self.assertNotEqual(self.client_user.password, NEW_PASSWORD)
        self.assertEqual(self.client_user.role, old_role)
        self.assertEqual(self.client_user.is_active, old_active)
        self.assertFalse(Session.objects.filter(session_key=old_session_key).exists())
        self.assertFalse(Session.objects.filter(session_key=second_old_session_key).exists())
        self.assertEqual(old_browser.get("/chat/").status_code, 302)
        self.assertEqual(second_old_browser.get("/chat/").status_code, 302)
        new_browser = Client()
        self.assertFalse(new_browser.login(username=self.client_user.username, password=PASSWORD))
        self.assertTrue(new_browser.login(username=self.client_user.username, password=NEW_PASSWORD))
        self.assertEqual(new_browser.get("/chat/").status_code, 200)

    def test_password_validation_failure_does_not_echo_or_resolve(self):
        item = PasswordResetRequest.objects.create(requester=self.client_user)
        weak = "1234567890"
        response = self.admin_browser.post(
            reverse("admin-password-request-resolve", args=(item.pk,)),
            {"new_password": weak, "confirm_password": weak, "confirm_resolution": "on"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A senha não atende à política configurada.")
        self.assertNotContains(response, weak)
        item.refresh_from_db()
        self.client_user.refresh_from_db()
        self.assertEqual(item.status, PasswordResetRequest.Status.OPEN)
        self.assertTrue(self.client_user.check_password(PASSWORD))

    def test_confirmation_mismatch_displays_safe_error_and_clears_both_password_fields(self):
        item = PasswordResetRequest.objects.create(requester=self.client_user)
        submitted = "Mismatch-Password!491"
        response = self.admin_browser.post(
            reverse("admin-password-request-resolve", args=(item.pk,)),
            {
                "new_password": submitted,
                "confirm_password": "different-password-491",
                "confirm_resolution": "on",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "As senhas não coincidem.", status_code=400)
        self.assertNotContains(response, submitted, status_code=400)
        self.assertNotContains(response, "different-password-491", status_code=400)
        item.refresh_from_db()
        self.assertEqual(item.status, PasswordResetRequest.Status.OPEN)

    def test_reject_is_terminal_and_leaves_password_unchanged(self):
        item = PasswordResetRequest.objects.create(requester=self.client_user)
        response = self.admin_browser.post(
            reverse("admin-password-request-reject", args=(item.pk,)),
            {"confirm_rejection": "on"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.client_user.refresh_from_db()
        self.assertEqual(item.status, PasswordResetRequest.Status.REJECTED)
        self.assertEqual(item.resolver_id, self.admin.pk)
        self.assertIsNotNone(item.resolved_at)
        self.assertTrue(self.client_user.check_password(PASSWORD))
        self.assertNotContains(response, PASSWORD)

    def test_repeated_resolution_conflicts_without_second_password_change(self):
        item = PasswordResetRequest.objects.create(requester=self.client_user)
        first_password = NEW_PASSWORD
        self.admin_browser.post(
            reverse("admin-password-request-resolve", args=(item.pk,)),
            {"new_password": first_password, "confirm_password": first_password, "confirm_resolution": "on"},
        )
        second_password = "X6!Another-Password$811"
        repeated = self.admin_browser.post(
            reverse("admin-password-request-resolve", args=(item.pk,)),
            {"new_password": second_password, "confirm_password": second_password, "confirm_resolution": "on"},
            follow=True,
        )
        self.assertContains(repeated, "já foi concluída")
        self.client_user.refresh_from_db()
        self.assertTrue(self.client_user.check_password(first_password))
        self.assertFalse(self.client_user.check_password(second_password))

    def test_admin_self_reset_logs_out_without_reviving_session_or_showing_password(self):
        item = PasswordResetRequest.objects.create(requester=self.admin)
        response = self.admin_browser.post(
            reverse("admin-password-request-resolve", args=(item.pk,)),
            {"new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD, "confirm_resolution": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))
        self.assertNotIn(NEW_PASSWORD, response.content.decode())
        self.assertEqual(self.admin_browser.get(reverse("admin-overview")).status_code, 302)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(NEW_PASSWORD))
        self.assertEqual(self.admin.role, User.Role.ADMIN)
        self.assertTrue(self.admin.is_active)

    def test_csrf_protects_admin_resolve_and_reject(self):
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.admin)
        item_a = PasswordResetRequest.objects.create(requester=self.client_user)
        item_b = PasswordResetRequest.objects.create(requester=self.support)
        resolve_url = reverse("admin-password-request-resolve", args=(item_a.pk,))
        reject_url = reverse("admin-password-request-reject", args=(item_b.pk,))
        self.assertEqual(
            browser.post(resolve_url, {"new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD, "confirm_resolution": "on"}).status_code,
            403,
        )
        self.assertEqual(browser.post(reject_url, {"confirm_rejection": "on"}).status_code, 403)
        browser.get(reverse("admin-password-request-detail", args=(item_a.pk,)))
        token = browser.cookies[settings.CSRF_COOKIE_NAME].value
        accepted = browser.post(
            reject_url,
            {"confirm_rejection": "on"},
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(accepted.status_code, 302)


class PasswordResetServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="service.admin", password=PASSWORD, role=User.Role.ADMIN
        )
        self.target = User.objects.create_user(
            username="service.target", password=PASSWORD, role=User.Role.CLIENT
        )

    def test_request_filters_are_admin_only_and_terminal_rows_are_historical(self):
        item = PasswordResetRequest.objects.create(requester=self.target)
        self.assertEqual(
            list(list_password_reset_requests(
                actor=self.admin, filters=PasswordResetRequestFilters(status="OPEN")
            )),
            [item],
        )
        mutation = reject_password_reset_request(actor=self.admin, request_id=item.pk)
        self.assertEqual(mutation.request.status, PasswordResetRequest.Status.REJECTED)
        self.assertEqual(
            list(list_password_reset_requests(
                actor=self.admin, filters=PasswordResetRequestFilters(status="REJECTED")
            )),
            [item],
        )
        with self.assertRaises(PasswordResetRequestConflict):
            resolve_password_reset_request(
                actor=self.admin, request_id=item.pk, new_password=NEW_PASSWORD
            )
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password(PASSWORD))


class ConcurrentPasswordResetTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        self.admin_a = User.objects.create_user(
            username="race.reset.admin.a", password=PASSWORD, role=User.Role.ADMIN
        )
        self.admin_b = User.objects.create_user(
            username="race.reset.admin.b", password=PASSWORD, role=User.Role.ADMIN
        )
        self.target = User.objects.create_user(
            username="race.reset.target", password=PASSWORD, role=User.Role.CLIENT
        )

    def _race(self, operations):
        from threading import Barrier, Thread
        from django.db import close_old_connections

        barrier = Barrier(len(operations))
        outcomes: list[str] = []

        def run(name, callback):
            close_old_connections()
            try:
                actor_id = self.admin_a.pk if name.endswith("a") else self.admin_b.pk
                actor = User.objects.get(pk=actor_id)
                barrier.wait(timeout=10)
                callback(actor)
                outcomes.append("success")
            except PasswordResetRequestConflict:
                outcomes.append("conflict")
            finally:
                close_old_connections()

        threads = [Thread(target=run, args=op) for op in operations]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=25)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        return outcomes

    def test_concurrent_resolve_and_reject_have_one_terminal_winner(self):
        item = PasswordResetRequest.objects.create(requester=self.target)
        outcomes = self._race(
            [
                ("admin-a", lambda actor: resolve_password_reset_request(
                    actor=actor, request_id=item.pk, new_password=NEW_PASSWORD
                )),
                ("admin-b", lambda actor: reject_password_reset_request(
                    actor=actor, request_id=item.pk
                )),
            ]
        )
        self.assertCountEqual(outcomes, ["success", "conflict"])
        item.refresh_from_db()
        self.target.refresh_from_db()
        self.assertIn(item.status, (PasswordResetRequest.Status.RESOLVED, PasswordResetRequest.Status.REJECTED))
        self.assertIsNotNone(item.resolver_id)
        self.assertIsNotNone(item.resolved_at)
        self.assertEqual(item.status == PasswordResetRequest.Status.RESOLVED, self.target.check_password(NEW_PASSWORD))

    def test_concurrent_resolutions_change_password_exactly_once(self):
        item = PasswordResetRequest.objects.create(requester=self.target)
        password_a = "A6!Race-Password$924"
        password_b = "B6!Race-Password$925"
        outcomes = self._race(
            [
                ("admin-a", lambda actor: resolve_password_reset_request(
                    actor=actor, request_id=item.pk, new_password=password_a
                )),
                ("admin-b", lambda actor: resolve_password_reset_request(
                    actor=actor, request_id=item.pk, new_password=password_b
                )),
            ]
        )
        self.assertCountEqual(outcomes, ["success", "conflict"])
        item.refresh_from_db()
        self.target.refresh_from_db()
        self.assertEqual(item.status, PasswordResetRequest.Status.RESOLVED)
        self.assertEqual(item.resolved_at.utcoffset(), timezone.get_current_timezone().utcoffset(item.resolved_at))
        self.assertEqual(self.target.check_password(password_a) + self.target.check_password(password_b), 1)

    def test_concurrent_public_submissions_coalesce_to_one_open_row(self):
        from threading import Barrier, Thread
        from django.db import close_old_connections

        barrier = Barrier(2)
        outcomes: list[str] = []

        def submit():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                result = request_password_reset(self.target.username)
                outcomes.append(result.disposition.value)
            finally:
                close_old_connections()

        threads = [Thread(target=submit), Thread(target=submit)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=25)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertCountEqual(outcomes, [SubmissionDisposition.CREATED.value, SubmissionDisposition.REUSED.value])
        self.assertEqual(PasswordResetRequest.objects.filter(requester=self.target).count(), 1)
