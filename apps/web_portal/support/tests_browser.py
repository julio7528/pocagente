from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.test import Client, TestCase
from django.utils import timezone

from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.conversations.services import create_conversation
from apps.web_portal.integrations.human_escalation import TransitionResult
from apps.web_portal.support.models import SupportHandoff


PASSWORD = "SupportBrowserTest!83"


def _transition_result(action, actor, conversation):
    target = {"CONFIRM": "WAITING_HUMAN", "ACCEPT": "HUMAN", "RESOLVE": "RESOLVED"}[action]
    return TransitionResult(
        action=action,
        state=target,
        status="TRANSITIONED",
        conversation_id=str(conversation.pk),
        assigned_operator_id=str(actor.pk) if action == "ACCEPT" else None,
        automation_suspended=action == "ACCEPT",
    )


class SupportPortalBrowserTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="support.browser.client", password=PASSWORD, role=User.Role.CLIENT
        )
        self.agent_a = User.objects.create_user(
            username="support.browser.a", password=PASSWORD, role=User.Role.SUPPORT_AGENT
        )
        self.agent_b = User.objects.create_user(
            username="support.browser.b", password=PASSWORD, role=User.Role.SUPPORT_AGENT
        )
        self.admin = User.objects.create_user(
            username="support.browser.admin", password=PASSWORD, role=User.Role.ADMIN
        )
        self.browser = Client(enforce_csrf_checks=True)

    def _login(self, user):
        self.browser.force_login(user)
        self.browser.get("/support/" if user.role == User.Role.SUPPORT_AGENT else "/chat/")
        return self.browser.cookies[settings.CSRF_COOKIE_NAME].value

    def _thread(self, title, status=Conversation.Status.ACTIVE, *, assigned=None):
        created = create_conversation(
            owner=self.owner,
            first_message=title,
            client_turn_key=uuid.uuid4(),
        )
        conversation = created.conversation
        if status == Conversation.Status.ACTIVE:
            return conversation
        conversation.status = status
        conversation.save(update_fields={"status", "updated_at"})
        fields = {"conversation": conversation}
        if status == Conversation.Status.WAITING_HUMAN:
            pass
        elif status == Conversation.Status.HUMAN:
            fields.update(
                status=SupportHandoff.Status.ASSIGNED,
                assigned_support_user=assigned,
                accepted_at=timezone.now(),
            )
        elif status == Conversation.Status.CLOSED:
            fields.update(
                status=SupportHandoff.Status.RESOLVED,
                assigned_support_user=assigned,
                accepted_at=timezone.now(),
                resolved_at=timezone.now(),
                resolved_by=assigned,
            )
        handoff = SupportHandoff.objects.create(**fields)
        return conversation

    def _post(self, path, data=None, *, token=None):
        if token is None:
            self.browser.get("/support/")
            token = self.browser.cookies[settings.CSRF_COOKIE_NAME].value
        payload = dict(data or {})
        payload["csrfmiddlewaretoken"] = token
        return self.browser.post(path, payload, HTTP_X_CSRFTOKEN=token)

    def test_client_gets_explicit_confirmation_then_same_thread_waiting_state(self):
        conversation = self._thread("POC-OPS-0004")
        token = self._login(self.owner)
        page = self.browser.get(f"/chat/{conversation.pk}/")
        self.assertContains(page, "Solicitar atendimento humano")
        confirm = self.browser.get(f"/chat/{conversation.pk}/human-support/confirm/")
        self.assertContains(confirm, "Confirmar solicitação")
        self.assertEqual(conversation.status, Conversation.Status.ACTIVE)
        self.assertFalse(SupportHandoff.objects.filter(conversation=conversation).exists())

        with patch("apps.web_portal.support.services.transition_human_escalation") as transition:
            transition.side_effect = lambda **kwargs: _transition_result(
                kwargs["action"], kwargs["actor"], kwargs["conversation"]
            )
            response = self._post(
                f"/chat/{conversation.pk}/human-support/request/", token=token
            )
        self.assertEqual(response.status_code, 302)
        conversation.refresh_from_db()
        handoff = SupportHandoff.objects.get(conversation=conversation)
        self.assertEqual(conversation.status, Conversation.Status.WAITING_HUMAN)
        self.assertEqual(handoff.status, SupportHandoff.Status.WAITING)
        self.assertEqual(transition.call_count, 1)
        client_page = self.browser.get(f"/chat/{conversation.pk}/")
        self.assertContains(client_page, "Aguardando atendimento humano")
        self.assertContains(client_page, "data-live-poll-url")

    def test_queue_assignment_message_finalization_and_client_visibility(self):
        waiting = self._thread("Esperando atendimento", Conversation.Status.WAITING_HUMAN)
        token = self._login(self.agent_a)
        dashboard = self.browser.get("/support/")
        self.assertContains(dashboard, "Aguardando atendimento")
        self.assertContains(dashboard, "Meus atendimentos ativos")
        self.assertContains(dashboard, "Finalizados")
        self.assertContains(dashboard, "Chats abertos")
        self.assertContains(dashboard, waiting.title)
        detail = self.browser.get(f"/support/{waiting.pk}/")
        self.assertContains(detail, "Assumir atendimento")
        self.assertContains(detail, "Esperando atendimento")
        self.assertContains(detail, "Histórico completo da conversa")

        with patch("apps.web_portal.support.services.transition_human_escalation") as transition:
            transition.side_effect = lambda **kwargs: _transition_result(
                kwargs["action"], kwargs["actor"], kwargs["conversation"]
            )
            claimed = self._post(f"/support/{waiting.pk}/claim/", token=token)
            self.assertEqual(claimed.status_code, 302)
            claimed_page = self.browser.get(claimed.url)
            self.assertContains(claimed_page, "Atendimento humano em andamento")
            self.assertContains(claimed_page, 'name="body"')

            turn_key = uuid.uuid4()
            path = f"/support/{waiting.pk}/messages/"
            reply_data = {"body": "Olá, vou verificar seu caso.", "support_turn_key": str(turn_key)}
            sent = self._post(path, reply_data, token=token)
            replay = self._post(path, reply_data, token=token)
            self.assertEqual(sent.status_code, 302)
            self.assertEqual(replay.status_code, 302)
            self.assertEqual(
                Message.objects.filter(
                    conversation=waiting, sender_type=Message.SenderType.SUPPORT_AGENT
                ).count(),
                1,
            )
            conflict = self._post(
                path,
                {"body": "Texto diferente", "support_turn_key": str(turn_key)},
                token=token,
            )
            self.assertEqual(conflict.status_code, 302)

            self.assertEqual(self._post(f"/support/{waiting.pk}/close/", token=token).status_code, 302)
            waiting.refresh_from_db()
            self.assertEqual(waiting.status, Conversation.Status.HUMAN)
            close = self._post(
                f"/support/{waiting.pk}/close/",
                {"confirm_finalization": "on"},
                token=token,
            )
            self.assertEqual(close.status_code, 302)
            closed_page = self.browser.get(close.url)
            self.assertContains(closed_page, "somente para leitura")
            self.assertNotContains(closed_page, 'name="body"')
            # Repeating a confirmed close is deterministic and does not call FastAPI again.
            repeat = self._post(
                f"/support/{waiting.pk}/close/",
                {"confirm_finalization": "on"},
                token=token,
            )
            self.assertEqual(repeat.status_code, 302)
            self.assertEqual(transition.call_count, 2)

        waiting.refresh_from_db()
        self.assertEqual(waiting.status, Conversation.Status.CLOSED)
        self.assertEqual(SupportHandoff.objects.get(conversation=waiting).status, SupportHandoff.Status.RESOLVED)

        client = Client()
        client.force_login(self.owner)
        client_page = client.get(f"/chat/{waiting.pk}/")
        self.assertContains(client_page, "Finalizada")
        self.assertContains(client_page, "Olá, vou verificar seu caso.")
        self.assertNotContains(client_page, 'data-chat-form')

    def test_assignment_isolation_roles_anonymous_and_csrf(self):
        owned = self._thread("Minha fila", Conversation.Status.HUMAN, assigned=self.agent_a)
        self.browser = Client()
        self._login(self.agent_b)
        self.assertIn(self.browser.get(f"/support/{owned.pk}/").status_code, (403, 404))
        claim_attempt = self.browser.post(f"/support/{owned.pk}/claim/", {})
        self.assertEqual(claim_attempt.status_code, 409)
        self.assertContains(claim_attempt, "Este atendimento já foi assumido por outro atendente.", status_code=409)
        for path in (f"/support/{owned.pk}/messages/", f"/support/{owned.pk}/close/"):
            self.assertIn(self.browser.post(path, {}).status_code, (403, 404))

        self.browser = Client(enforce_csrf_checks=True)
        self.assertRedirects(self.browser.get("/support/"), "/login/", fetch_redirect_response=False)
        self._login(self.agent_a)
        self.assertEqual(self.browser.post(f"/support/{owned.pk}/claim/").status_code, 403)
        self.assertEqual(self.browser.get(f"/support/{owned.pk}/claim/").status_code, 405)
        self.assertEqual(self.browser.get(f"/support/{owned.pk}/close/").status_code, 405)
        self.assertEqual(
            self.browser.post(
                f"/support/{owned.pk}/messages/",
                {"body": "Sem token", "support_turn_key": str(uuid.uuid4())},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.browser.post(
                f"/support/{owned.pk}/close/", {"confirm_finalization": "on"}
            ).status_code,
            403,
        )
        self.browser = Client()
        self.browser.force_login(self.owner)
        self.assertEqual(self.browser.get("/support/").status_code, 403)

    def test_waiting_queue_oldest_first_and_assigned_history_is_private(self):
        older = self._thread("Fila antiga", Conversation.Status.WAITING_HUMAN)
        newer = self._thread("Fila nova", Conversation.Status.WAITING_HUMAN)
        SupportHandoff.objects.filter(conversation=older).update(requested_at=timezone.now() - timedelta(minutes=10))
        SupportHandoff.objects.filter(conversation=newer).update(requested_at=timezone.now() - timedelta(minutes=1))
        other_active = self._thread("Ativo de outro atendente", Conversation.Status.HUMAN, assigned=self.agent_b)
        other_closed = self._thread("Finalizado de outro atendente", Conversation.Status.CLOSED, assigned=self.agent_b)
        self._login(self.agent_a)
        page = self.browser.get("/support/")
        html = page.content.decode()
        self.assertLess(html.index("Fila antiga"), html.index("Fila nova"))
        self.assertNotIn("Ativo de outro atendente", html)
        self.assertNotIn("Finalizado de outro atendente", html)
        self.assertNotEqual(other_active.pk, other_closed.pk)

    def test_polling_updates_are_scoped_and_detect_client_messages(self):
        conversation = self._thread("Atualização compartilhada", Conversation.Status.HUMAN, assigned=self.agent_a)
        self._login(self.agent_a)
        page = self.browser.get(f"/support/{conversation.pk}/")
        old_version = page.context["live_version"]
        client_browser = Client()
        client_browser.force_login(self.owner)
        client_browser.post(
            f"/chat/{conversation.pk}/messages/",
            {"body": "Nova mensagem do cliente", "client_turn_key": str(uuid.uuid4())},
        )
        update = self.browser.get(f"/support/{conversation.pk}/updates/")
        self.assertEqual(update.status_code, 200)
        self.assertNotEqual(update.json()["version"], old_version)
        self.assertEqual(self.browser.get(f"/support/{uuid.uuid4()}/updates/").status_code, 404)
        self.browser.force_login(self.admin)
        self.assertEqual(self.browser.get("/support/").status_code, 403)

    def test_support_message_xss_is_escaped_and_long_unicode_wraps(self):
        conversation = self._thread("Segurança", Conversation.Status.HUMAN, assigned=self.agent_a)
        token = self._login(self.agent_a)
        body = "Olá " + "ç" * 3800 + "\n<script>alert(1)</script>"
        response = self._post(
            f"/support/{conversation.pk}/messages/",
            {"body": body, "support_turn_key": str(uuid.uuid4())},
            token=token,
        )
        self.assertEqual(response.status_code, 302)
        page = self.browser.get(response.url)
        html = page.content.decode()
        self.assertIn("ç" * 3800, html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)
