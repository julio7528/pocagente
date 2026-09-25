from __future__ import annotations

import uuid

from django.contrib.auth.hashers import make_password
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.models import Conversation
from apps.web_portal.support.models import SupportHandoff


PASSWORD = "P8!qZ_Rs4#vN6wKx"


class ProductAdminPortalTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="portal.admin", password=PASSWORD, role=User.Role.ADMIN
        )
        self.client = Client()
        self.client.force_login(self.admin)

    def _create_user(self, username, role=User.Role.CLIENT, *, active=True, password=PASSWORD):
        return User.objects.create_user(
            username=username,
            password=password,
            role=role,
            is_active=active,
        )

    def _create_account_from_ui(self, username, role):
        response = self.client.post(
            reverse("admin-user-create-submit"),
            {
                "username": username,
                "role": role,
                "is_active": "on",
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 302, response.content[:500])
        return User.objects.get(username=username.strip().lower())

    def test_admin_only_route_matrix_and_product_portal_is_separate(self):
        self.assertEqual(self.client.get(reverse("admin-overview")).status_code, 200)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        for role in (User.Role.CLIENT, User.Role.SUPPORT_AGENT):
            user = self._create_user(f"route.{role.lower()}", role)
            browser = Client()
            browser.force_login(user)
            self.assertEqual(browser.get(reverse("admin-overview")).status_code, 403)
            self.assertEqual(browser.get(reverse("admin-users")).status_code, 403)
            self.assertEqual(
                browser.get(reverse("admin-user-detail", args=(self.admin.pk,))).status_code,
                403,
            )
            self.assertNotEqual(browser.get("/admin/").status_code, 200)
        anonymous = Client()
        self.assertEqual(anonymous.get(reverse("admin-overview")).status_code, 302)
        self.assertIn("/login/", anonymous.get(reverse("admin-users")).url)

    def test_inactive_admin_cannot_use_product_portal(self):
        self.admin.is_active = False
        self.admin.save(update_fields={"is_active", "updated_at"})
        response = self.client.get(reverse("admin-overview"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_overview_counts_only_portal_users(self):
        self._create_user("overview.client", User.Role.CLIENT)
        self._create_user("overview.agent", User.Role.SUPPORT_AGENT, active=False)
        response = self.client.get(reverse("admin-overview"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["counts"]["total"], 3)
        self.assertEqual(response.context["counts"]["active"], 2)
        self.assertEqual(response.context["counts"]["inactive"], 1)
        self.assertEqual(response.context["counts"]["admins"], 1)

    def test_username_search_role_state_and_combined_filters(self):
        self._create_user("alpha.client", User.Role.CLIENT)
        self._create_user("alpha.agent", User.Role.SUPPORT_AGENT)
        self._create_user("beta.client", User.Role.CLIENT, active=False)

        response = self.client.get(reverse("admin-users"), {"q": "ALPHA", "role": "CLIENT"})
        self.assertEqual([u.username for u in response.context["users"]], ["alpha.client"])

        response = self.client.get(reverse("admin-users"), {"role": "SUPPORT_AGENT"})
        self.assertEqual([u.username for u in response.context["users"]], ["alpha.agent"])

        response = self.client.get(reverse("admin-users"), {"role": "ADMIN"})
        self.assertEqual([u.username for u in response.context["users"]], ["portal.admin"])

        response = self.client.get(reverse("admin-users"), {"state": "INACTIVE"})
        self.assertEqual([u.username for u in response.context["users"]], ["beta.client"])

        response = self.client.get(
            reverse("admin-users"), {"q": "beta", "role": "CLIENT", "state": "ACTIVE"}
        )
        self.assertEqual(list(response.context["users"]), [])

    def test_invalid_filters_are_ignored_and_empty_state_is_safe(self):
        self._create_user("visible.client")
        response = self.client.get(
            reverse("admin-users"), {"role": "ROOT", "state": "UNKNOWN"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 2)
        self.assertEqual(response.context["selected_role"], "")
        self.assertEqual(response.context["selected_state"], "")
        empty = self.client.get(reverse("admin-users"), {"q": "not-a-user"})
        self.assertContains(empty, "Nenhum usuário corresponde aos filtros.")

    def test_user_list_is_bounded_and_pagination_preserves_filters(self):
        encoded_password = make_password(PASSWORD)
        User.objects.bulk_create(
            [
                User(
                    username=f"page.user.{index:02d}",
                    role=User.Role.CLIENT,
                    is_active=True,
                    password=encoded_password,
                )
                for index in range(27)
            ]
        )
        first = self.client.get(reverse("admin-users"), {"role": "CLIENT", "state": "ACTIVE"})
        self.assertEqual(first.context["users"].count(), 25)
        self.assertContains(first, "Próxima")
        self.assertIn("role=CLIENT", first.content.decode())
        self.assertIn("state=ACTIVE", first.content.decode())
        second = self.client.get(
            reverse("admin-users"), {"role": "CLIENT", "state": "ACTIVE", "page": "2"}
        )
        self.assertEqual(second.context["users"].count(), 2)
        self.assertEqual(second.context["page_obj"].number, 2)

    def test_user_detail_excludes_password_hash_and_uses_safe_escaped_username(self):
        unsafe = self._create_user("<script>alert(7)</script>")
        response = self.client.get(reverse("admin-user-detail", args=(unsafe.pk,)))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertNotIn("<script>alert(7)</script>", body)
        self.assertIn("&lt;script&gt;alert(7)&lt;/script&gt;", body)
        self.assertNotIn(unsafe.password, body)
        self.assertNotIn("password_hash", body)

    def test_admin_can_create_all_three_roles_with_hash_and_role_landing(self):
        for role, username, landing in (
            (User.Role.CLIENT, "New.Client", "/chat/"),
            (User.Role.SUPPORT_AGENT, "New.Support", "/support/"),
            (User.Role.ADMIN, "New.Admin", "/admin-portal/"),
        ):
            with self.subTest(role=role):
                user = self._create_account_from_ui(username, role)
                self.assertIsInstance(user.pk, uuid.UUID)
                self.assertEqual(user.role, role)
                self.assertTrue(user.is_active)
                self.assertTrue(user.check_password(PASSWORD))
                self.assertNotEqual(user.password, PASSWORD)
                browser = Client()
                login = browser.post(
                    reverse("login"), {"username": username.upper(), "password": PASSWORD}
                )
                self.assertRedirects(login, landing, fetch_redirect_response=False)

    def test_invalid_role_values_cannot_create_or_mutate_application_roles(self):
        target = self._create_user("role.guard")
        changed = self.client.post(
            reverse("admin-user-role", args=(target.pk,)), {"role": "ROOT"}, follow=True
        )
        self.assertEqual(changed.status_code, 200)
        target.refresh_from_db()
        self.assertEqual(target.role, User.Role.CLIENT)
        created = self.client.post(
            reverse("admin-user-create-submit"),
            {
                "username": "forged.role",
                "role": "ROOT",
                "is_active": "on",
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
            },
        )
        self.assertEqual(created.status_code, 400)
        self.assertFalse(User.objects.filter(username="forged.role").exists())

    def test_create_user_normalizes_username_and_never_redisplays_password(self):
        submitted = "  Mixed.Case.User  "
        response = self.client.post(
            reverse("admin-user-create-submit"),
            {
                "username": submitted,
                "role": User.Role.CLIENT,
                "password": "Different-Valid!Pass209",
                "password_confirmation": "not-the-same",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, "Different-Valid!Pass209", status_code=400)
        self.assertNotContains(response, "not-the-same", status_code=400)
        self.assertFalse(User.objects.filter(username="mixed.case.user").exists())

    def test_create_user_applies_django_password_validators_without_echoing_value(self):
        response = self.client.post(
            reverse("admin-user-create-submit"),
            {
                "username": "weak.password.user",
                "role": User.Role.CLIENT,
                "is_active": "on",
                "password": "password",
                "password_confirmation": "password",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "A senha não atende à política configurada.", status_code=400)
        self.assertNotContains(response, "value=\"password\"", status_code=400)
        self.assertFalse(User.objects.filter(username="weak.password.user").exists())

    def test_deactivation_revokes_old_session_and_preserves_user(self):
        target = self._create_user("deactivate.client")
        target_browser = Client()
        self.assertTrue(target_browser.login(username=target.username, password=PASSWORD))
        self.assertEqual(target_browser.get("/chat/").status_code, 200)

        response = self.client.post(reverse("admin-user-deactivate", args=(target.pk,)))
        self.assertRedirects(response, reverse("admin-user-detail", args=(target.pk,)), fetch_redirect_response=False)
        target.refresh_from_db()
        self.assertFalse(target.is_active)
        self.assertEqual(target_browser.get("/chat/").status_code, 302)
        self.assertTrue(User.objects.filter(pk=target.pk).exists())
        self.assertEqual(target.conversations.count(), 0)

    def test_role_change_revokes_old_session_and_new_role_lands_in_support(self):
        target = self._create_user("role.client")
        target_browser = Client()
        self.assertTrue(target_browser.login(username=target.username, password=PASSWORD))
        self.assertEqual(target_browser.get("/chat/").status_code, 200)

        response = self.client.post(
            reverse("admin-user-role", args=(target.pk,)), {"role": User.Role.SUPPORT_AGENT}
        )
        self.assertRedirects(response, reverse("admin-user-detail", args=(target.pk,)), fetch_redirect_response=False)
        target.refresh_from_db()
        self.assertEqual(target.role, User.Role.SUPPORT_AGENT)
        self.assertEqual(target_browser.get("/chat/").status_code, 302)

        fresh_browser = Client()
        login = fresh_browser.post(
            reverse("login"), {"username": target.username, "password": PASSWORD}
        )
        self.assertRedirects(login, "/support/", fetch_redirect_response=False)
        self.assertEqual(fresh_browser.get("/support/").status_code, 200)

    def test_password_reset_hashes_password_revokes_sessions_and_does_not_render_it(self):
        target = self._create_user("password.client")
        target_browser = Client()
        self.assertTrue(target_browser.login(username=target.username, password=PASSWORD))
        new_password = "New-Unique!Password938"
        response = self.client.post(
            reverse("admin-user-password", args=(target.pk,)),
            {"new_password": new_password, "password_confirmation": new_password},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Senha alterada.")
        self.assertNotContains(response, new_password)
        target.refresh_from_db()
        self.assertTrue(target.check_password(new_password))
        self.assertFalse(target.check_password(PASSWORD))
        self.assertNotEqual(target.password, new_password)
        self.assertEqual(target_browser.get("/chat/").status_code, 302)
        self.assertNotContains(
            self.client.get(reverse("admin-user-detail", args=(target.pk,))),
            target.password,
        )

    def test_last_active_admin_service_rejection_is_presented_safely(self):
        detail = reverse("admin-user-detail", args=(self.admin.pk,))
        deactivation = self.client.post(
            reverse("admin-user-deactivate", args=(self.admin.pk,)), follow=True
        )
        self.assertEqual(deactivation.status_code, 200)
        self.assertContains(deactivation, "Não é possível remover o último administrador ativo.")
        demotion = self.client.post(
            reverse("admin-user-role", args=(self.admin.pk,)),
            {"role": User.Role.CLIENT},
            follow=True,
        )
        self.assertContains(demotion, "Não é possível remover o último administrador ativo.")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertEqual(self.admin.role, User.Role.ADMIN)
        self.assertEqual(self.client.get(detail).status_code, 200)

    def test_last_admin_guard_allows_nonlast_deactivation_then_protects_remaining(self):
        second = self._create_user("second.admin", User.Role.ADMIN)
        result = self.client.post(reverse("admin-user-deactivate", args=(second.pk,)))
        self.assertEqual(result.status_code, 302)
        second.refresh_from_db()
        self.assertFalse(second.is_active)
        rejected = self.client.post(
            reverse("admin-user-role", args=(self.admin.pk,)),
            {"role": User.Role.SUPPORT_AGENT},
            follow=True,
        )
        self.assertContains(rejected, "Não é possível remover o último administrador ativo.")
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Role.ADMIN)

    def test_self_deactivation_with_another_admin_ends_the_acting_session(self):
        self._create_user("backup.admin", User.Role.ADMIN)
        response = self.client.post(
            reverse("admin-user-deactivate", args=(self.admin.pk,)), follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sua sessão foi encerrada pela alteração.")
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_active)
        self.assertEqual(self.client.get(reverse("admin-overview")).status_code, 302)

    def test_self_role_change_ends_session_and_new_login_uses_new_role(self):
        self._create_user("backup.role.admin", User.Role.ADMIN)
        response = self.client.post(
            reverse("admin-user-role", args=(self.admin.pk,)),
            {"role": User.Role.CLIENT},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sua sessão foi encerrada pela alteração.")
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Role.CLIENT)
        self.assertEqual(self.client.get(reverse("admin-overview")).status_code, 302)
        fresh_browser = Client()
        login = fresh_browser.post(
            reverse("login"), {"username": self.admin.username, "password": PASSWORD}
        )
        self.assertRedirects(login, "/chat/", fetch_redirect_response=False)

    def test_self_password_change_flushes_current_request_session(self):
        new_password = "Self-Reset!Password752"
        response = self.client.post(
            reverse("admin-user-password", args=(self.admin.pk,)),
            {"new_password": new_password, "password_confirmation": new_password},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sua sessão foi encerrada pela alteração.")
        self.assertEqual(self.client.get(reverse("admin-overview")).status_code, 302)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(new_password))
        self.assertFalse(self.admin.check_password(PASSWORD))

    def test_active_human_support_assignment_prevents_role_change_or_deactivation(self):
        support = self._create_user("assigned.support", User.Role.SUPPORT_AGENT)
        client_user = self._create_user("assigned.client", User.Role.CLIENT)
        conversation = Conversation.objects.create(
            owner=client_user,
            title="Atendimento humano ativo",
            status=Conversation.Status.HUMAN,
        )
        SupportHandoff.objects.create(
            conversation=conversation,
            status=SupportHandoff.Status.ASSIGNED,
            assigned_support_user=support,
            accepted_at=timezone.now(),
        )

        changed = self.client.post(
            reverse("admin-user-role", args=(support.pk,)), {"role": User.Role.CLIENT}, follow=True
        )
        self.assertContains(changed, "O atendente possui um atendimento humano ativo")
        support.refresh_from_db()
        conversation.refresh_from_db()
        handoff = SupportHandoff.objects.get(conversation=conversation)
        self.assertEqual(support.role, User.Role.SUPPORT_AGENT)
        self.assertTrue(support.is_active)
        self.assertEqual(conversation.status, Conversation.Status.HUMAN)
        self.assertEqual(handoff.assigned_support_user_id, support.pk)
        self.assertEqual(handoff.status, SupportHandoff.Status.ASSIGNED)

    def test_csrf_required_for_mutations(self):
        target = self._create_user("csrf.target")
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.admin)
        missing_token = browser.post(reverse("admin-user-deactivate", args=(target.pk,)))
        self.assertEqual(missing_token.status_code, 403)

        page = browser.get(reverse("admin-user-detail", args=(target.pk,)))
        self.assertEqual(page.status_code, 200)
        csrf_token = browser.cookies["csrftoken"].value
        accepted = browser.post(
            reverse("admin-user-deactivate", args=(target.pk,)),
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(accepted.status_code, 302)
        target.refresh_from_db()
        self.assertFalse(target.is_active)

    def test_no_registration_or_physical_delete_route(self):
        for suffix in ("register", "signup", "create-account", "cadastro", "cadastrar"):
            self.assertEqual(self.client.get(f"/{suffix}/").status_code, 404)
        target = self._create_user("no-delete")
        self.assertEqual(self.client.get(f"/admin-portal/users/{target.pk}/delete/").status_code, 404)
