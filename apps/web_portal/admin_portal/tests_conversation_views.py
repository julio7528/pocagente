from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.support.models import SupportHandoff


PASSWORD = "Test-only-Conversation-Views-783!"


@override_settings(PASSWORD_HASHERS=("django.contrib.auth.hashers.MD5PasswordHasher",))
class AdminConversationViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="view.admin", password=PASSWORD, role=User.Role.ADMIN
        )
        self.client_user = User.objects.create_user(
            username="view.client", password=PASSWORD, role=User.Role.CLIENT
        )
        self.other_client = User.objects.create_user(
            username="view.other", password=PASSWORD, role=User.Role.CLIENT
        )
        self.support = User.objects.create_user(
            username="view.support", password=PASSWORD, role=User.Role.SUPPORT_AGENT
        )
        self.browser = Client()
        self.browser.force_login(self.admin)

    def conversation(
        self, title="View conversation", *, owner=None, status=Conversation.Status.ACTIVE
    ):
        return Conversation.objects.create(
            owner=owner or self.client_user, title=title, status=status
        )

    def add_client_message(self, conversation, body, *, created_at=None):
        message = Message.objects.create(
            conversation=conversation,
            sender_type=Message.SenderType.CLIENT,
            sender_user=conversation.owner,
            body=body,
            idempotency_key=uuid.uuid4(),
        )
        if created_at is not None:
            Message.objects.filter(pk=message.pk).update(created_at=created_at)
        return message

    def test_route_matrix_and_anonymous_redirect(self):
        conversation = self.conversation()
        base = reverse("admin-conversations")
        detail = reverse("admin-conversation-detail", args=(conversation.pk,))
        self.assertEqual(self.browser.get(base).status_code, 200)
        self.assertEqual(self.browser.get(detail).status_code, 200)

        anonymous = Client()
        response = anonymous.get(detail)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

        for role in (User.Role.CLIENT, User.Role.SUPPORT_AGENT):
            user = User.objects.create_user(
                username=f"denied.{role.lower()}", password=PASSWORD, role=role
            )
            browser = Client()
            browser.force_login(user)
            self.assertEqual(browser.get(base).status_code, 403)
            self.assertEqual(browser.get(detail).status_code, 403)
            for route in (
                "admin-conversation-block",
                "admin-conversation-unblock",
                "admin-conversation-delete",
            ):
                self.assertEqual(
                    browser.post(
                        reverse(route, args=(conversation.pk,)),
                        {"confirm": "on"},
                    ).status_code,
                    403,
                )

    def test_inactive_admin_cannot_access_detail_or_mutation(self):
        conversation = self.conversation()
        self.admin.is_active = False
        self.admin.save(update_fields=("is_active", "updated_at"))
        detail = self.browser.get(
            reverse("admin-conversation-detail", args=(conversation.pk,))
        )
        self.assertEqual(detail.status_code, 302)
        self.assertIn("/login/", detail.url)
        blocked = self.browser.post(
            reverse("admin-conversation-block", args=(conversation.pk,)),
            {"confirm": "on"},
        )
        self.assertEqual(blocked.status_code, 302)
        conversation.refresh_from_db()
        self.assertEqual(conversation.status, Conversation.Status.ACTIVE)

    def test_search_owner_status_date_filters_combine_and_pagination_is_bounded(self):
        matched = self.conversation("Invoice question")
        old = self.conversation("Invoice old")
        Conversation.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=3)
        )
        self.conversation("Invoice other owner", owner=self.other_client)
        self.conversation("Invoice waiting", status=Conversation.Status.WAITING_HUMAN)
        response = self.browser.get(
            reverse("admin-conversations"),
            {
                "query": "invoice",
                "owner_username": "view.client",
                "status": Conversation.Status.ACTIVE,
                "date_from": timezone.localdate().isoformat(),
                "date_to": timezone.localdate().isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row.pk for row in response.context["conversations"]], [matched.pk])

        for number in range(26):
            self.conversation(f"Page {number:02d}")
        first = self.browser.get(reverse("admin-conversations"), {"owner_username": "view.client"})
        self.assertEqual(len(first.context["conversations"]), 25)
        self.assertContains(first, "Próxima")
        self.assertContains(first, "owner_username=view.client")
        second = self.browser.get(
            reverse("admin-conversations"), {"owner_username": "view.client", "page": "2"}
        )
        self.assertEqual(len(second.context["conversations"]), 4)

    def test_invalid_status_search_length_and_date_range_do_not_run_unfiltered_query(self):
        from apps.web_portal.admin_portal import conversation_views

        cases = (
            {"status": "ROOT"},
            {"query": "x" * 101},
            {"date_from": "2026-01-01"},
            {"date_from": "2025-01-01", "date_to": "2026-01-02"},
            {"date_from": "2026-02-02", "date_to": "2026-02-01"},
        )
        with patch.object(conversation_views, "list_admin_conversations") as listing:
            for params in cases:
                response = self.browser.get(reverse("admin-conversations"), params)
                self.assertEqual(response.status_code, 400)
            listing.assert_not_called()

    def test_detail_shows_complete_escaped_transcript_and_has_no_reply_controls(self):
        conversation = self.conversation("<unsafe title>")
        bodies = (
            (Message.SenderType.CLIENT, self.client_user, "<script>alert(1)</script>"),
            (Message.SenderType.AGENT, None, "<img src=x onerror=alert(2)>"),
            (Message.SenderType.SYSTEM, None, "Aviso <b>seguro</b>"),
            (Message.SenderType.SUPPORT_AGENT, self.support, "Atendimento concluído."),
        )
        for sender_type, sender_user, body in bodies:
            Message.objects.create(
                conversation=conversation,
                sender_type=sender_type,
                sender_user=sender_user,
                body=body,
                idempotency_key=uuid.uuid4() if sender_type == Message.SenderType.CLIENT else None,
            )

        response = self.browser.get(
            reverse("admin-conversation-detail", args=(conversation.pk,))
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;", html=False)
        self.assertContains(response, "&lt;img src=x onerror=alert(2)&gt;", html=False)
        self.assertContains(response, "&lt;b&gt;seguro&lt;/b&gt;", html=False)
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertNotIn("<img src=x onerror=alert(2)>", body)
        self.assertContains(response, "Atendimento humano")
        self.assertNotContains(response, "textarea")
        self.assertNotContains(response, 'name="body"')
        self.assertNotContains(response, "Responder como")
        self.assertContains(response, "Bloquear conversa")
        self.assertContains(response, "somente leitura")

    def test_admin_history_renders_more_than_context_window_and_full_oversized_body(self):
        conversation = self.conversation("Full transcript")
        body = ("conteúdo integral " * 400) + "FIM-DO-TEXTO-INTEGRAL"
        for number in range(14):
            Message.objects.create(
                conversation=conversation,
                sender_type=Message.SenderType.CLIENT,
                sender_user=self.client_user,
                body=f"Turno {number:02d}: {body}",
                idempotency_key=uuid.uuid4(),
            )
        response = self.browser.get(
            reverse("admin-conversation-detail", args=(conversation.pk,))
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["history"]), 14)
        self.assertIn("FIM-DO-TEXTO-INTEGRAL", response.content.decode("utf-8"))
        self.assertGreater(len(response.content), 6000)

    def test_active_block_post_ignores_forged_restore_and_deleted_by_fields(self):
        conversation = self.conversation()
        response = self.browser.post(
            reverse("admin-conversation-block", args=(conversation.pk,)),
            {
                "confirm": "on",
                "status_before_block": "HUMAN",
                "deleted_by": str(self.support.pk),
                "assigned_support_user": str(self.support.pk),
            },
        )
        self.assertRedirects(
            response,
            reverse("admin-conversation-detail", args=(conversation.pk,)),
            fetch_redirect_response=False,
        )
        conversation.refresh_from_db()
        self.assertEqual(conversation.status, Conversation.Status.BLOCKED)
        self.assertEqual(conversation.status_before_block, Conversation.Status.ACTIVE)
        self.assertIsNone(conversation.deleted_by_id)
        restored = self.browser.post(
            reverse("admin-conversation-unblock", args=(conversation.pk,)),
            {"confirm": "on", "status": "HUMAN"},
        )
        self.assertEqual(restored.status_code, 302)
        conversation.refresh_from_db()
        self.assertEqual(conversation.status, Conversation.Status.ACTIVE)
        self.assertIsNone(conversation.status_before_block)

    def test_blocked_state_freezes_client_and_assigned_support_writes(self):
        from apps.web_portal.conversations.services import (
            ConversationNotWritableError,
            append_client_message,
        )
        from apps.web_portal.support.services import (
            SupportConversationUnavailable,
            append_assigned_support_message,
        )

        conversation = self.conversation(status=Conversation.Status.HUMAN)
        handoff = SupportHandoff.objects.create(
            conversation=conversation,
            status=SupportHandoff.Status.ASSIGNED,
            assigned_support_user=self.support,
            accepted_at=timezone.now(),
        )
        self.browser.post(
            reverse("admin-conversation-block", args=(conversation.pk,)),
            {"confirm": "on"},
        )
        conversation.refresh_from_db()
        handoff.refresh_from_db()
        self.assertEqual(handoff.assigned_support_user_id, self.support.pk)
        self.assertEqual(handoff.status, SupportHandoff.Status.ASSIGNED)
        with self.assertRaises(ConversationNotWritableError):
            append_client_message(
                actor=self.client_user, conversation=conversation,
                body="Blocked", client_turn_key=uuid.uuid4(),
            )
        with self.assertRaises(SupportConversationUnavailable):
            append_assigned_support_message(
                actor=self.support, conversation_id=conversation.pk,
                body="Blocked", support_turn_key=uuid.uuid4(),
            )
        self.browser.post(
            reverse("admin-conversation-unblock", args=(conversation.pk,)),
            {"confirm": "on"},
        )
        conversation.refresh_from_db()
        handoff.refresh_from_db()
        self.assertEqual(conversation.status, Conversation.Status.HUMAN)
        self.assertEqual(handoff.assigned_support_user_id, self.support.pk)
        self.assertEqual(handoff.status, SupportHandoff.Status.ASSIGNED)

    def test_delete_is_soft_retains_history_and_hides_from_client(self):
        conversation = self.conversation()
        message = self.add_client_message(conversation, "Retained transcript.")
        response = self.browser.post(
            reverse("admin-conversation-delete", args=(conversation.pk,)),
            {"confirm": "on"},
        )
        self.assertEqual(response.status_code, 302)
        conversation.refresh_from_db()
        self.assertEqual(conversation.status, Conversation.Status.DELETED)
        self.assertIsNotNone(conversation.deleted_at)
        self.assertEqual(conversation.deleted_by_id, self.admin.pk)
        self.assertTrue(Conversation.objects.filter(pk=conversation.pk).exists())
        self.assertTrue(Message.objects.filter(pk=message.pk).exists())
        self.assertEqual(
            self.browser.get(reverse("admin-conversation-detail", args=(conversation.pk,))).status_code,
            200,
        )
        client_browser = Client()
        client_browser.force_login(self.client_user)
        self.assertNotContains(client_browser.get("/chat/"), conversation.title)
        self.assertNotEqual(client_browser.get(f"/chat/{conversation.pk}/").status_code, 200)
        tombstones = self.browser.get(
            reverse("admin-conversations"), {"status": Conversation.Status.DELETED}
        )
        self.assertEqual(tombstones.status_code, 200)
        self.assertContains(tombstones, conversation.title)
        self.assertContains(tombstones, "Apagada")
        self.assertEqual(
            self.browser.get(
                reverse("admin-conversation-delete", args=(conversation.pk,))
            ).status_code,
            405,
        )
        self.assertEqual(
            self.browser.get(
                f"/admin-portal/conversations/{conversation.pk}/restore/"
            ).status_code,
            404,
        )

    def test_deleted_finalized_handoff_is_hidden_from_support_portal(self):
        conversation = self.conversation("Finalized support record", status=Conversation.Status.CLOSED)
        handoff = SupportHandoff.objects.create(
            conversation=conversation,
            status=SupportHandoff.Status.RESOLVED,
            assigned_support_user=self.support,
            accepted_at=timezone.now(),
            resolved_at=timezone.now(),
            resolved_by=self.support,
        )
        self.browser.post(
            reverse("admin-conversation-delete", args=(conversation.pk,)),
            {"confirm": "on"},
        )
        handoff.refresh_from_db()
        self.assertEqual(handoff.status, SupportHandoff.Status.RESOLVED)
        support_browser = Client()
        support_browser.force_login(self.support)
        dashboard = support_browser.get(reverse("support-landing"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertNotContains(dashboard, conversation.title)
        detail = support_browser.get(
            reverse("support-conversation", args=(conversation.pk,))
        )
        self.assertEqual(detail.status_code, 404)

    def test_waiting_or_assigned_handoff_has_no_delete_control_and_is_rejected(self):
        for state, handoff_state in (
            (Conversation.Status.WAITING_HUMAN, SupportHandoff.Status.WAITING),
            (Conversation.Status.HUMAN, SupportHandoff.Status.ASSIGNED),
        ):
            conversation = self.conversation(f"Active handoff {state}", status=state)
            values = {"conversation": conversation, "status": handoff_state}
            if handoff_state == SupportHandoff.Status.ASSIGNED:
                values.update(
                    assigned_support_user=self.support, accepted_at=timezone.now()
                )
            SupportHandoff.objects.create(**values)
            detail = self.browser.get(
                reverse("admin-conversation-detail", args=(conversation.pk,))
            )
            self.assertNotContains(detail, "Confirmar exclusão lógica")
            response = self.browser.post(
                reverse("admin-conversation-delete", args=(conversation.pk,)),
                {"confirm": "on"},
                follow=True,
            )
            self.assertContains(
                response,
                "Há um atendimento humano ativo. A conversa não pode ser apagada.",
            )
            conversation.refresh_from_db()
            self.assertEqual(conversation.status, state)

    def test_csrf_confirmation_and_post_only_mutations(self):
        conversation = self.conversation()
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.admin)
        action = reverse("admin-conversation-block", args=(conversation.pk,))
        for route in (
            "admin-conversation-block",
            "admin-conversation-unblock",
            "admin-conversation-delete",
        ):
            self.assertEqual(
                protected.post(
                    reverse(route, args=(conversation.pk,)), {"confirm": "on"}
                ).status_code,
                403,
            )
        page = protected.get(reverse("admin-conversation-detail", args=(conversation.pk,)))
        self.assertEqual(page.status_code, 200)
        csrf = protected.cookies["csrftoken"].value
        self.assertEqual(
            protected.post(action, {"confirm": "on"}, HTTP_X_CSRFTOKEN="invalid").status_code,
            403,
        )
        self.assertEqual(protected.post(action, {"confirm": "on"}, HTTP_X_CSRFTOKEN=csrf).status_code, 302)
        conversation.refresh_from_db()
        self.assertEqual(conversation.status, Conversation.Status.BLOCKED)

        invalid_confirmation = self.conversation("Needs confirmation")
        response = self.browser.post(
            reverse("admin-conversation-delete", args=(invalid_confirmation.pk,)),
            {},
            follow=True,
        )
        self.assertContains(response, "Confirme a ação para continuar.")
        invalid_confirmation.refresh_from_db()
        self.assertEqual(invalid_confirmation.status, Conversation.Status.ACTIVE)

    def test_unknown_detail_returns_safe_404_and_no_exception_data(self):
        response = self.browser.get(
            reverse("admin-conversation-detail", args=(uuid.uuid4(),))
        )
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Conversa não encontrada", status_code=404)
        body = response.content.decode("utf-8")
        self.assertNotIn("DoesNotExist", body)
        self.assertNotIn("Traceback", body)
