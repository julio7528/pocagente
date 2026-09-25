from __future__ import annotations

from threading import Barrier, Thread

from django.contrib.sessions.models import Session
from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.utils import timezone

from apps.web_portal.accounts import services
from apps.web_portal.accounts.authorization import (
    client_owns_conversation,
    require_admin,
    require_assigned_human_conversation,
    support_agent_is_assigned_to_human,
    user_is_admin,
    user_is_client,
    user_is_support_agent,
)
from apps.web_portal.accounts.models import User
from apps.web_portal.admin_portal.admin_site import technical_admin_site
from apps.web_portal.conversations.models import Conversation
from apps.web_portal.support.models import SupportHandoff


TEST_PASSWORD = "T8!vQ4#nL6@zR2$k"


class IdentityPolicyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin.one", password=TEST_PASSWORD, role=User.Role.ADMIN
        )
        self.client_user = User.objects.create_user(
            username="client.one", password=TEST_PASSWORD, role=User.Role.CLIENT
        )
        self.other_client = User.objects.create_user(
            username="client.two", password=TEST_PASSWORD, role=User.Role.CLIENT
        )
        self.support = User.objects.create_user(
            username="support.one", password=TEST_PASSWORD, role=User.Role.SUPPORT_AGENT
        )

    def _session_for(self, user):
        session = SessionStore()
        session["_auth_user_id"] = str(user.pk)
        session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
        session["_auth_user_hash"] = user.get_session_auth_hash()
        session.save()
        return session.session_key

    def _conversation(self, owner, *, status=Conversation.Status.ACTIVE):
        return Conversation.objects.create(owner=owner, title="First message", status=status)

    def test_role_contract_predicates_and_admin_only_service_authority(self):
        from django.contrib.auth import authenticate

        self.assertEqual(tuple(User.Role.values), ("ADMIN", "CLIENT", "SUPPORT_AGENT"))
        self.assertTrue(user_is_admin(self.admin))
        self.assertTrue(user_is_client(self.client_user))
        self.assertTrue(user_is_support_agent(self.support))
        self.assertEqual(
            authenticate(username="  CLIENT.ONE ", password=TEST_PASSWORD).pk,
            self.client_user.pk,
        )
        with self.assertRaises(PermissionDenied):
            services.create_user(
                actor=self.client_user,
                username="attempt",
                password=TEST_PASSWORD,
                role=User.Role.CLIENT,
                is_active=True,
            )
        with self.assertRaises(PermissionDenied):
            require_admin(self.support)

    def test_account_creation_normalizes_hashes_and_has_no_ops_authority(self):
        result = services.create_user(
            actor=self.admin,
            username="  New.Client ",
            password=TEST_PASSWORD,
            role=User.Role.CLIENT,
            is_active=True,
        )
        created = result.user
        self.assertEqual(created.username, "new.client")
        self.assertTrue(created.check_password(TEST_PASSWORD))
        self.assertNotEqual(created.password, TEST_PASSWORD)
        self.assertFalse(created.is_staff)
        self.assertFalse(created.is_superuser)
        self.assertFalse(hasattr(created, "ops_authorized"))
        for role in User.Role.values:
            allowed = services.create_user(
                actor=self.admin,
                username=f"new-{role.lower()}",
                password=TEST_PASSWORD,
                role=role,
                is_active=True,
            ).user
            self.assertEqual(allowed.role, role)
        with self.assertRaises(services.AccountPolicyError):
            services.create_user(
                actor=self.admin,
                username="bad-role",
                password=TEST_PASSWORD,
                role="OPERATOR",
                is_active=True,
            )

    def test_deactivation_uses_is_active_and_revokes_existing_session(self):
        from django.contrib.auth import authenticate

        conversation = self._conversation(self.client_user)
        key = self._session_for(self.client_user)
        result = services.deactivate_user(actor=self.admin, target=self.client_user)
        self.assertEqual(result.action, "DEACTIVATED")
        self.client_user.refresh_from_db()
        self.assertFalse(self.client_user.is_active)
        self.assertFalse(Session.objects.filter(session_key=key).exists())
        self.assertFalse(user_is_client(self.client_user))
        self.assertTrue(User.objects.filter(pk=self.client_user.pk).exists())
        self.assertTrue(Conversation.objects.filter(pk=conversation.pk, owner=self.client_user).exists())
        self.assertIsNone(authenticate(username="client.one", password=TEST_PASSWORD))

    def test_role_change_invalidates_sessions_and_syncs_django_flags(self):
        key = self._session_for(self.client_user)
        services.change_role(actor=self.admin, target=self.client_user, new_role=User.Role.SUPPORT_AGENT)
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.role, User.Role.SUPPORT_AGENT)
        self.assertTrue(self.client_user.is_active)
        self.assertFalse(self.client_user.is_staff)
        self.assertFalse(self.client_user.is_superuser)
        self.assertFalse(Session.objects.filter(session_key=key).exists())
        services.change_role(actor=self.admin, target=self.client_user, new_role=User.Role.ADMIN)
        self.client_user.refresh_from_db()
        self.assertTrue(self.client_user.is_staff)
        self.assertFalse(self.client_user.is_superuser)

    def test_password_change_hashes_and_invalidates_sessions(self):
        key = self._session_for(self.client_user)
        new_password = "B7!mP9#xK2@qV5$w"
        services.set_user_password(actor=self.admin, target=self.client_user, new_password=new_password)
        self.client_user.refresh_from_db()
        self.assertTrue(self.client_user.check_password(new_password))
        self.assertNotEqual(self.client_user.password, new_password)
        self.assertFalse(Session.objects.filter(session_key=key).exists())

    def test_active_human_assignment_blocks_support_role_change_and_deactivation(self):
        conversation = self._conversation(self.client_user, status=Conversation.Status.HUMAN)
        SupportHandoff.objects.create(
            conversation=conversation,
            status=SupportHandoff.Status.ASSIGNED,
            assigned_support_user=self.support,
            accepted_at=timezone.now(),
        )
        with self.assertRaises(services.ActiveSupportAssignmentError):
            services.change_role(actor=self.admin, target=self.support, new_role=User.Role.CLIENT)
        with self.assertRaises(services.ActiveSupportAssignmentError):
            services.deactivate_user(actor=self.admin, target=self.support)
        self.support.refresh_from_db()
        self.assertEqual(self.support.role, User.Role.SUPPORT_AGENT)
        self.assertTrue(self.support.is_active)

    def test_last_active_admin_cannot_be_deactivated_or_demoted(self):
        with self.assertRaises(services.LastActiveAdminError):
            services.deactivate_user(actor=self.admin, target=self.admin)
        for role in (User.Role.CLIENT, User.Role.SUPPORT_AGENT):
            with self.assertRaises(services.LastActiveAdminError):
                services.change_role(actor=self.admin, target=self.admin, new_role=role)
        self.assertEqual(User.objects.filter(role=User.Role.ADMIN, is_active=True).count(), 1)

    def test_one_of_two_admins_can_be_demoted_then_last_one_is_protected(self):
        second = User.objects.create_user(
            username="admin.two", password=TEST_PASSWORD, role=User.Role.ADMIN
        )
        services.change_role(actor=self.admin, target=second, new_role=User.Role.CLIENT)
        self.assertEqual(User.objects.filter(role=User.Role.ADMIN, is_active=True).count(), 1)
        with self.assertRaises(services.LastActiveAdminError):
            services.deactivate_user(actor=self.admin, target=self.admin)

    def test_django_admin_requires_active_admin_role_not_framework_flags(self):
        request = RequestFactory().get("/admin/")
        request.user = self.admin
        self.assertTrue(technical_admin_site.has_permission(request))
        for role_user in (self.client_user, self.support):
            User.objects.filter(pk=role_user.pk).update(is_staff=True, is_superuser=True)
            role_user.refresh_from_db()
            request.user = role_user
            self.assertFalse(technical_admin_site.has_permission(request))
        self.admin.is_active = False
        self.admin.save()
        request.user = self.admin
        self.assertFalse(technical_admin_site.has_permission(request))

    def test_technical_admin_user_entry_is_read_only_and_role_gated(self):
        from apps.web_portal.admin_portal.user_admin import ReadOnlyPortalUserAdmin

        model_admin = technical_admin_site._registry[User]
        request = RequestFactory().get("/admin/accounts/user/")
        request.user = self.admin
        self.assertIsInstance(model_admin, ReadOnlyPortalUserAdmin)
        self.assertTrue(model_admin.has_view_permission(request))
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        request.user = self.client_user
        self.assertFalse(model_admin.has_view_permission(request))

    def test_object_authorization_scopes_clients_and_human_assignment(self):
        owned = self._conversation(self.client_user)
        other = self._conversation(self.other_client)
        self.assertTrue(client_owns_conversation(self.client_user, owned))
        self.assertFalse(client_owns_conversation(self.client_user, other))
        deleted = Conversation.objects.create(
            owner=self.client_user,
            title="Deleted conversation",
            status=Conversation.Status.DELETED,
            deleted_at=timezone.now(),
            deleted_by=self.admin,
        )
        self.assertFalse(client_owns_conversation(self.client_user, deleted))
        human = self._conversation(self.client_user, status=Conversation.Status.HUMAN)
        handoff = SupportHandoff.objects.create(
            conversation=human,
            status=SupportHandoff.Status.ASSIGNED,
            assigned_support_user=self.support,
            accepted_at=timezone.now(),
        )
        self.assertTrue(support_agent_is_assigned_to_human(self.support, human, handoff))
        self.assertFalse(support_agent_is_assigned_to_human(self.other_client, human, handoff))
        with self.assertRaises(PermissionDenied):
            require_assigned_human_conversation(self.other_client, human, handoff)

    def test_no_registration_route_and_no_superuser_creation_shortcut(self):
        from django.urls import get_resolver

        paths = [str(pattern.pattern) for pattern in get_resolver().url_patterns]
        self.assertEqual(
            paths,
            [
                "login/",
                "password-reset/request/",
                "password-reset/request/confirm/",
                "logout/",
                "chat/",
                "support/",
                "admin-portal/",
                "admin/",
            ],
        )
        self.assertFalse(any(token in "/".join(paths).lower() for token in ("register", "signup", "create-account")))
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                username="superuser", password=TEST_PASSWORD, role=User.Role.ADMIN
            )

    def test_users_cannot_be_physically_deleted(self):
        with self.assertRaises(ValidationError):
            self.client_user.delete()
        with self.assertRaises(ValidationError):
            User.objects.filter(pk=self.client_user.pk).delete()


class BootstrapAdminCommandTests(TestCase):
    def test_bootstrap_command_creates_hashed_active_admin_without_plaintext_output(self):
        from io import StringIO
        from unittest.mock import patch

        from django.core.management import call_command

        output = StringIO()
        with patch("builtins.input", return_value="  First.Admin "), patch(
            "getpass.getpass", side_effect=[TEST_PASSWORD, TEST_PASSWORD]
        ):
            call_command("bootstrap_admin", stdout=output)
        admin_user = User.objects.get(role=User.Role.ADMIN)
        self.assertEqual(admin_user.username, "first.admin")
        self.assertTrue(admin_user.is_active)
        self.assertTrue(admin_user.check_password(TEST_PASSWORD))
        self.assertNotIn(TEST_PASSWORD, admin_user.password)
        self.assertNotIn(TEST_PASSWORD, output.getvalue())

    def test_bootstrap_refuses_repeat(self):
        from io import StringIO
        from unittest.mock import patch

        from django.core.management import call_command
        from django.core.management.base import CommandError

        User.objects.create_user(username="existing-admin", password=TEST_PASSWORD, role=User.Role.ADMIN)
        with patch("builtins.input", return_value="second"), patch(
            "getpass.getpass", side_effect=[TEST_PASSWORD, TEST_PASSWORD]
        ):
            with self.assertRaises(CommandError):
                call_command("bootstrap_admin", stdout=StringIO())
        self.assertEqual(User.objects.filter(role=User.Role.ADMIN).count(), 1)

    def test_bootstrap_rejects_mismatched_confirmation(self):
        from io import StringIO
        from unittest.mock import patch

        from django.core.management import call_command
        from django.core.management.base import CommandError

        with patch("builtins.input", return_value="first"), patch(
            "getpass.getpass", side_effect=[TEST_PASSWORD, "different-password"]
        ):
            with self.assertRaises(CommandError):
                call_command("bootstrap_admin", stdout=StringIO())
        self.assertFalse(User.objects.filter(role=User.Role.ADMIN).exists())

    def test_bootstrap_applies_password_validation(self):
        from io import StringIO
        from unittest.mock import patch

        from django.core.management import call_command
        from django.core.management.base import CommandError

        with patch("builtins.input", return_value="weak-password"), patch(
            "getpass.getpass", side_effect=["weak-password", "weak-password"]
        ):
            with self.assertRaises(CommandError):
                call_command("bootstrap_admin", stdout=StringIO())
        self.assertFalse(User.objects.filter(role=User.Role.ADMIN).exists())


class ConcurrentLastAdminTests(TransactionTestCase):
    reset_sequences = False

    def test_simultaneous_demotion_attempts_leave_one_active_admin(self):
        first = User.objects.create_user(username="race-admin-a", password=TEST_PASSWORD, role=User.Role.ADMIN)
        second = User.objects.create_user(username="race-admin-b", password=TEST_PASSWORD, role=User.Role.ADMIN)
        barrier = Barrier(2)
        outcomes: list[str] = []

        def demote(actor_id, target_id):
            close_old_connections()
            try:
                actor = User.objects.get(pk=actor_id)
                barrier.wait(timeout=10)
                services.change_role(actor=actor, target=target_id, new_role=User.Role.CLIENT)
                outcomes.append("changed")
            except (services.LastActiveAdminError, PermissionDenied):
                outcomes.append("denied")
            finally:
                close_old_connections()

        threads = [
            Thread(target=demote, args=(first.pk, second.pk)),
            Thread(target=demote, args=(second.pk, first.pk)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(outcomes.count("changed"), 1)
        self.assertEqual(outcomes.count("denied"), 1)
        self.assertEqual(User.objects.filter(role=User.Role.ADMIN, is_active=True).count(), 1)
