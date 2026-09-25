"""CLIENT browser flow over isolated portal PostgreSQL test data."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from django.conf import settings
from django.db import DatabaseError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.agent_turns import AgentTurnResult, execute_agent_turn
from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.conversations.services import (
    append_agent_message,
    append_client_message,
    append_support_message,
    append_system_message,
    create_conversation,
    mark_client_turn_failed,
)
from apps.web_portal.support.models import SupportHandoff
from apps.web_portal.integrations.agent_chat import AgentChatResponse, AgentChatUnavailable


PASSWORD = "T8!vQ4#nL6@zR2$k"


@override_settings(DEBUG=False)
class ClientChatBrowserTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="chat.owner", password=PASSWORD, role=User.Role.CLIENT
        )
        cls.other = User.objects.create_user(
            username="chat.other", password=PASSWORD, role=User.Role.CLIENT
        )
        cls.support = User.objects.create_user(
            username="chat.support", password=PASSWORD, role=User.Role.SUPPORT_AGENT
        )
        cls.admin = User.objects.create_user(
            username="chat.admin", password=PASSWORD, role=User.Role.ADMIN
        )

    def setUp(self):
        self.browser = Client(enforce_csrf_checks=True)
        self.browser.force_login(self.owner)
        self.agent_turn_patch = patch(
            "apps.web_portal.conversations.views.execute_agent_turn",
            return_value=AgentTurnResult(outcome="NO_ANSWER"),
        )
        self.agent_turn_mock = self.agent_turn_patch.start()
        self.addCleanup(self.agent_turn_patch.stop)

    @staticmethod
    def csrf(browser: Client) -> str:
        browser.get("/chat/")
        return browser.cookies[settings.CSRF_COOKIE_NAME].value

    def post(self, path: str, *, body: str, key: uuid.UUID | None = None, browser=None):
        browser = browser or self.browser
        token = self.csrf(browser)
        return browser.post(
            path,
            {
                "body": body,
                "client_turn_key": str(key or uuid.uuid4()),
                "csrfmiddlewaretoken": token,
            },
            HTTP_X_CSRFTOKEN=token,
        )

    def thread(self, *, owner=None, body="Primeira pergunta"):
        return create_conversation(
            owner=owner or self.owner,
            first_message=body,
            client_turn_key=uuid.uuid4(),
        )

    def test_real_login_empty_new_conversation_append_and_logout_flow(self):
        browser = Client(enforce_csrf_checks=True)
        login_page = browser.get("/login/")
        self.assertEqual(login_page.status_code, 200)
        login_token = browser.cookies[settings.CSRF_COOKIE_NAME].value
        login = browser.post(
            "/login/",
            {
                "username": self.owner.username,
                "password": PASSWORD,
                "csrfmiddlewaretoken": login_token,
            },
            HTTP_X_CSRFTOKEN=login_token,
        )
        self.assertEqual(login.url, "/chat/")
        home = browser.get("/chat/")
        self.assertContains(home, "Você ainda não possui conversas.")
        self.assertContains(home, "Nova conversa")
        self.assertContains(home, "<main", html=False)
        self.assertContains(home, "<aside", html=False)
        self.assertContains(home, "<footer", html=False)

        first = self.post("/chat/new/", body="  Como   funciona o Link?  ", browser=browser)
        self.assertEqual(first.status_code, 302)
        conversation = Conversation.objects.get(owner=self.owner)
        self.assertEqual(conversation.status, Conversation.Status.ACTIVE)
        self.assertEqual(conversation.title, "Como funciona o Link?")
        detail = browser.get(first.url)
        self.assertContains(detail, "Como funciona o Link?")
        self.assertContains(detail, "  Como   funciona o Link?  ")
        self.assertContains(detail, "Mensagem registrada.")

        second = self.post(
            f"/chat/{conversation.id}/messages/", body="E o prazo de recebimento?", browser=browser
        )
        self.assertEqual(second.url, first.url)
        detail = browser.get(second.url)
        content = detail.content.decode()
        self.assertLess(content.index("Como   funciona o Link?"), content.index("E o prazo de recebimento?"))
        self.assertEqual(Conversation.objects.get(pk=conversation.id).title, "Como funciona o Link?")
        self.assertEqual(Message.objects.filter(conversation=conversation).count(), 2)
        self.assertContains(detail, "+ Nova conversa")
        self.assertContains(detail, "Minha conta")
        self.assertContains(detail, "Sair")

        logout_token = browser.cookies[settings.CSRF_COOKIE_NAME].value
        logout = browser.post(
            "/logout/",
            {"csrfmiddlewaretoken": logout_token},
            HTTP_X_CSRFTOKEN=logout_token,
        )
        self.assertEqual(logout.url, "/login/")
        self.assertEqual(browser.get(second.url).url, "/login/")

    def test_sidebar_is_owned_non_deleted_and_reorders_after_new_message(self):
        older = self.thread(body="Conversa antiga").conversation
        newer = self.thread(body="Conversa recente").conversation
        other = self.thread(owner=self.other, body="Segredo de outro cliente").conversation
        deleted = self.thread(body="Oculta").conversation
        deleted.status = Conversation.Status.DELETED
        deleted.deleted_at = timezone.now()
        deleted.deleted_by = self.admin
        deleted.save()

        page = self.browser.get("/chat/")
        html = page.content.decode()
        self.assertLess(html.index("Conversa recente"), html.index("Conversa antiga"))
        self.assertNotIn("Segredo de outro cliente", html)
        self.assertNotIn("Oculta", html)
        self.assertEqual(self.post(f"/chat/{older.id}/messages/", body="Nova mensagem").status_code, 302)
        html = self.browser.get("/chat/").content.decode()
        self.assertLess(html.index("Conversa antiga"), html.index("Conversa recente"))
        self.assertEqual(other.owner, self.other)

    def test_first_form_and_existing_turn_replays_do_not_duplicate(self):
        first_key = uuid.uuid4()
        first = self.post("/chat/new/", body="Uma nova conversa", key=first_key)
        replay = self.post("/chat/new/", body="Uma nova conversa", key=first_key)
        self.assertEqual(replay.url, first.url)
        self.assertEqual(Conversation.objects.filter(owner=self.owner).count(), 1)
        conversation = Conversation.objects.get(owner=self.owner)
        self.assertEqual(Message.objects.filter(conversation=conversation).count(), 1)

        turn_key = uuid.uuid4()
        path = f"/chat/{conversation.id}/messages/"
        self.assertEqual(self.post(path, body="Segundo turno", key=turn_key).status_code, 302)
        self.assertEqual(self.post(path, body="Segundo turno", key=turn_key).status_code, 302)
        self.assertEqual(Message.objects.filter(conversation=conversation).count(), 2)
        conflict = self.post(path, body="Conteúdo conflitante", key=turn_key)
        self.assertEqual(conflict.status_code, 409)
        self.assertContains(conflict, "Esta tentativa de envio já foi utilizada.", status_code=409)
        self.assertEqual(Message.objects.filter(conversation=conversation).count(), 2)

    def test_cross_client_urls_and_post_body_substitution_are_denied(self):
        mine = self.thread(body="Meu título").conversation
        foreign = self.thread(owner=self.other, body="Título privado").conversation
        home = self.browser.get("/chat/")
        self.assertContains(home, "Meu título")
        self.assertNotContains(home, "Título privado")
        detail = self.browser.get(f"/chat/{foreign.id}/")
        self.assertIn(detail.status_code, (403, 404))
        self.assertNotIn("Título privado", detail.content.decode())
        response = self.post(
            f"/chat/{foreign.id}/messages/", body="Tentativa cruzada"
        )
        self.assertIn(response.status_code, (403, 404))
        self.assertFalse(Message.objects.filter(conversation=foreign, body="Tentativa cruzada").exists())
        response = self.post(
            f"/chat/{mine.id}/messages/", body="Mensagem própria",
        )
        self.assertEqual(response.status_code, 302)

    def test_blocked_and_closed_are_readable_without_composer_or_writes(self):
        for status in (Conversation.Status.BLOCKED, Conversation.Status.CLOSED):
            with self.subTest(status=status):
                conversation = self.thread(body=f"Histórico {status}").conversation
                conversation.status = status
                if status == Conversation.Status.BLOCKED:
                    conversation.status_before_block = Conversation.Status.ACTIVE
                conversation.save()
                page = self.browser.get(f"/chat/{conversation.id}/")
                self.assertContains(page, f"Histórico {status}")
                self.assertContains(page, "somente para leitura")
                self.assertNotContains(page, 'data-chat-form')
                forged = self.post(
                    f"/chat/{conversation.id}/messages/", body="Forjado"
                )
                self.assertEqual(forged.status_code, 409)
                self.assertFalse(Message.objects.filter(conversation=conversation, body="Forjado").exists())

    def test_deleted_is_hidden_and_retained_without_restore(self):
        created = self.thread(body="Mensagem preservada")
        conversation = created.conversation
        conversation.status = Conversation.Status.DELETED
        conversation.deleted_at = timezone.now()
        conversation.deleted_by = self.admin
        conversation.save()
        self.assertNotContains(self.browser.get("/chat/"), "Mensagem preservada")
        self.assertIn(self.browser.get(f"/chat/{conversation.id}/").status_code, (403, 404))
        self.assertIn(
            self.post(f"/chat/{conversation.id}/messages/", body="Forjado").status_code,
            (403, 404),
        )
        self.assertTrue(Message.objects.filter(pk=created.first_message.id).exists())

    def test_in_flight_agent_result_is_discarded_if_admin_blocks_conversation(self):
        created = self.thread(body="Pergunta antes do bloqueio")
        safe_response = AgentChatResponse(
            status="COMPLETED",
            route="CONVERSATIONAL",
            answer="Resposta que chegou depois do bloqueio",
            reason="CONVERSATION_COMPLETED",
        )

        def block_then_return(_client, _turn):
            Conversation.objects.filter(pk=created.conversation.pk).update(
                status=Conversation.Status.BLOCKED,
                status_before_block=Conversation.Status.ACTIVE,
            )
            return safe_response

        with patch(
            "apps.web_portal.conversations.agent_turns.AgentChatClient.execute",
            new=block_then_return,
        ):
            result = execute_agent_turn(
                actor=self.owner,
                conversation_id=created.conversation.pk,
                client_message_id=created.first_message.pk,
            )

        self.assertEqual(result.outcome, "SUSPENDED")
        created.conversation.refresh_from_db()
        created.first_message.refresh_from_db()
        self.assertEqual(created.conversation.status, Conversation.Status.BLOCKED)
        self.assertEqual(
            created.first_message.processing_status,
            Message.ProcessingStatus.FAILED,
        )
        self.assertFalse(
            Message.objects.filter(
                conversation=created.conversation,
                sender_type=Message.SenderType.AGENT,
            ).exists()
        )

    def test_waiting_and_human_keep_same_thread_without_agent_invocation(self):
        for status, label in (
            (Conversation.Status.WAITING_HUMAN, "Aguardando atendimento humano"),
            (Conversation.Status.HUMAN, "Atendimento humano"),
        ):
            with self.subTest(status=status):
                created = self.thread(body=f"Início {status}")
                conversation = created.conversation
                conversation.status = status
                conversation.save()
                page = self.browser.get(f"/chat/{conversation.id}/")
                self.assertContains(page, label)
                self.assertContains(page, 'data-chat-form')
                with patch("apps.web_portal.conversations.views.append_client_message", wraps=append_client_message) as write:
                    response = self.post(
                        f"/chat/{conversation.id}/messages/", body="Acompanhamento"
                    )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(write.call_count, 1)
                self.assertEqual(
                    Message.objects.filter(conversation=conversation, sender_type=Message.SenderType.AGENT).count(),
                    0,
                )
                self.assertEqual(Message.objects.filter(conversation=conversation).count(), 2)

    def test_active_turn_persists_one_safe_agent_answer_and_replay_reuses_it(self):
        from apps.web_portal.conversations.agent_turns import execute_agent_turn
        from apps.web_portal.integrations.agent_chat import AgentChatResponse

        created = self.thread(body="Sobre a Get Smart")
        turn = append_client_message(
            actor=self.owner, conversation=created.conversation,
            body="E quanto custa?", client_turn_key=uuid.uuid4(),
        ).message
        response = AgentChatResponse(
            status="COMPLETED", route="KNOWLEDGE", reason="GROUNDED",
            answer="<script>alert(1)</script> Resposta contextual.",
        )
        with patch(
            "apps.web_portal.conversations.agent_turns.AgentChatClient"
        ) as client_class:
            client_class.return_value.execute.return_value = response
            result = execute_agent_turn(
                actor=self.owner, conversation_id=created.conversation.pk,
                client_message_id=turn.pk,
            )
            replay = execute_agent_turn(
                actor=self.owner, conversation_id=created.conversation.pk,
                client_message_id=turn.pk,
            )

        self.assertEqual(result.outcome, "COMPLETED")
        self.assertEqual(replay.outcome, "ALREADY_COMPLETED")
        client_class.return_value.execute.assert_called_once()
        sent_turn = client_class.return_value.execute.call_args.args[0]
        self.assertEqual(sent_turn.conversation_id, created.conversation.pk)
        self.assertEqual(sent_turn.message, "E quanto custa?")
        self.assertEqual(
            [item.content for item in sent_turn.conversation_context],
            ["Sobre a Get Smart", "E quanto custa?"],
        )
        self.assertEqual(
            Message.objects.filter(
                conversation=created.conversation,
                sender_type=Message.SenderType.CLIENT,
            ).count(),
            2,
        )
        agent_rows = Message.objects.filter(
            conversation=created.conversation,
            sender_type=Message.SenderType.AGENT,
        )
        self.assertEqual(agent_rows.count(), 1)
        self.assertIn("<script>alert(1)</script>", agent_rows.get().body)
        rendered = self.browser.get(f"/chat/{created.conversation.pk}/")
        self.assertContains(rendered, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(rendered, "<script>alert(1)</script>")

    def test_retry_reuses_client_turn_and_never_duplicates_agent_response(self):
        from apps.web_portal.integrations.agent_chat import AgentChatResponse

        self.agent_turn_patch.stop()
        retries = [
            AgentChatUnavailable(retryable=True),
            AgentChatResponse(
                status="COMPLETED", route="CONVERSATIONAL", reason="ANSWERED",
                answer="Resposta após retry.",
            ),
        ]
        with patch(
            "apps.web_portal.conversations.agent_turns.AgentChatClient.execute",
            side_effect=retries,
        ) as execute:
            first = self.post("/chat/new/", body="Pergunta que precisa de retry")
            self.assertEqual(first.status_code, 302)
            conversation = Conversation.objects.get(owner=self.owner)
            client_turn = Message.objects.get(
                conversation=conversation, sender_type=Message.SenderType.CLIENT
            )
            self.assertEqual(client_turn.processing_status, Message.ProcessingStatus.FAILED)
            self.assertTrue(self.browser.session.get("recoverable_agent_chat_turns"))
            detail = self.browser.get(first.url)
            self.assertContains(detail, "Tentar obter resposta novamente")

            csrf = self.csrf(self.browser)
            retry_path = f"/chat/{conversation.pk}/messages/{client_turn.pk}/retry/"
            retried = self.browser.post(
                retry_path,
                {"csrfmiddlewaretoken": csrf},
                HTTP_X_CSRFTOKEN=csrf,
            )
            self.assertEqual(retried.status_code, 302)
            client_turn.refresh_from_db()
            self.assertEqual(client_turn.processing_status, Message.ProcessingStatus.COMPLETED)
            self.assertEqual(execute.call_count, 2)
            self.assertEqual(
                execute.call_args_list[0].args[0].client_turn_id,
                execute.call_args_list[1].args[0].client_turn_id,
            )

            duplicate = self.browser.post(
                retry_path,
                {"csrfmiddlewaretoken": csrf},
                HTTP_X_CSRFTOKEN=csrf,
            )
            self.assertEqual(duplicate.status_code, 302)
            self.assertEqual(execute.call_count, 2)
            self.assertEqual(Message.objects.filter(conversation=conversation).count(), 2)

    def test_suspended_conversation_never_calls_agent_client(self):
        from apps.web_portal.conversations.agent_turns import execute_agent_turn

        for state in (
            Conversation.Status.WAITING_HUMAN,
            Conversation.Status.HUMAN,
            Conversation.Status.CLOSED,
            Conversation.Status.BLOCKED,
        ):
            with self.subTest(state=state):
                created = self.thread(body=f"Estado {state}")
                conversation = created.conversation
                conversation.status = state
                if state == Conversation.Status.BLOCKED:
                    conversation.status_before_block = Conversation.Status.ACTIVE
                conversation.save()
                with patch(
                    "apps.web_portal.conversations.agent_turns.AgentChatClient.execute"
                ) as execute:
                    result = execute_agent_turn(
                        actor=self.owner, conversation_id=conversation.pk,
                        client_message_id=created.first_message.pk,
                    )
                self.assertEqual(result.outcome, "SUSPENDED")
                execute.assert_not_called()

    def test_all_sender_classes_and_failed_state_render_safely(self):
        created = self.thread(body="Pergunta")
        conversation = created.conversation
        append_agent_message(conversation=conversation, client_message=created.first_message, body="Resposta do agente")
        append_system_message(conversation=conversation, body="Aviso público")
        pending = append_client_message(
            actor=self.owner, conversation=conversation, body="Nova dúvida",
            client_turn_key=uuid.uuid4(),
        ).message
        mark_client_turn_failed(conversation=conversation, client_message=pending)
        conversation.status = Conversation.Status.HUMAN
        conversation.save()
        SupportHandoff.objects.create(
            conversation=conversation,
            status=SupportHandoff.Status.ASSIGNED,
            accepted_at=timezone.now(),
            assigned_support_user=self.support,
        )
        append_support_message(actor=self.support, conversation=conversation, body="Resposta humana")
        page = self.browser.get(f"/chat/{conversation.id}/")
        for visible in (
            "Você", "Assistente", "Aviso", "Atendimento humano",
            "Resposta do agente", "Aviso público", "Resposta humana",
            "Sua mensagem foi preservada.",
        ):
            self.assertContains(page, visible)

    def test_long_body_is_complete_and_html_payloads_are_escaped(self):
        payload = "<script>alert(1)</script>\n<a href=\"https://example.test\">texto</a>"
        body = "ç" * 6_100 + "\n" + payload
        created = self.thread(body=body)
        page = self.browser.get(f"/chat/{created.conversation.id}/")
        html = page.content.decode()
        self.assertIn("ç" * 6_100, html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;a href=", html)
        self.assertNotIn("truncated", html)

    def test_ui_history_has_no_twelve_message_projection_limit(self):
        created = self.thread(body="turn-00")
        for number in range(1, 15):
            append_client_message(
                actor=self.owner,
                conversation=created.conversation,
                body=f"turn-{number:02d}",
                client_turn_key=uuid.uuid4(),
            )
        page = self.browser.get(f"/chat/{created.conversation.id}/")
        self.assertEqual(page.status_code, 200)
        for number in range(15):
            self.assertContains(page, f"turn-{number:02d}")
        self.assertEqual(len(page.context["history"]), 15)

    def test_invalid_input_and_controlled_database_failure_are_safe(self):
        created = self.thread()
        invalid = self.post(f"/chat/{created.conversation.id}/messages/", body="  \n  ")
        self.assertEqual(invalid.status_code, 400)
        self.assertContains(invalid, "Escreva uma mensagem antes de enviar.", status_code=400)
        with patch("apps.web_portal.conversations.views.append_client_message", side_effect=DatabaseError("synthetic SQL diagnostic")):
            unavailable = self.post(
                f"/chat/{created.conversation.id}/messages/", body="Tentativa"
            )
        self.assertEqual(unavailable.status_code, 503)
        self.assertContains(unavailable, "Tente novamente em instantes.", status_code=503)
        self.assertNotIn("synthetic SQL diagnostic", unavailable.content.decode())

    def test_csrf_and_method_guards_protect_writes(self):
        created = self.thread()
        self.assertEqual(self.browser.post("/chat/new/", {"body": "Sem CSRF"}).status_code, 403)
        self.assertEqual(
            self.browser.post(f"/chat/{created.conversation.id}/messages/", {"body": "Sem CSRF"}).status_code,
            403,
        )
        self.assertEqual(self.browser.get("/chat/new/").status_code, 405)
        self.assertEqual(self.browser.get(f"/chat/{created.conversation.id}/messages/").status_code, 405)

    def test_role_and_anonymous_access(self):
        created = self.thread()
        paths = (
            "/chat/", "/chat/new/", f"/chat/{created.conversation.id}/",
            f"/chat/{created.conversation.id}/messages/",
        )
        anonymous = Client()
        for path in paths:
            response = anonymous.post(path) if path.endswith("new/") or path.endswith("messages/") else anonymous.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "/login/")
            self.assertEqual(anonymous.get(path).url, "/login/")
        for user in (self.support, self.admin):
            browser = Client()
            browser.force_login(user)
            for path in paths:
                response = browser.post(path) if path.endswith("new/") or path.endswith("messages/") else browser.get(path)
                self.assertEqual(response.status_code, 403)

    def test_session_expiry_and_inactive_user_still_block_chat(self):
        from apps.web_portal.accounts.session_policy import AUTHENTICATED_AT_KEY, LAST_ACTIVITY_AT_KEY

        session = self.browser.session
        now = int(timezone.now().timestamp())
        session[AUTHENTICATED_AT_KEY] = now - 8 * 60 * 60
        session[LAST_ACTIVITY_AT_KEY] = now - 10
        session.save()
        self.assertEqual(self.browser.get("/chat/").url, "/login/")

        self.browser.force_login(self.owner)
        session = self.browser.session
        session[AUTHENTICATED_AT_KEY] = now - 10
        session[LAST_ACTIVITY_AT_KEY] = now - 30 * 60
        session.save()
        self.assertEqual(self.browser.get("/chat/").url, "/login/")

        self.browser.force_login(self.owner)
        self.owner.is_active = False
        self.owner.save(update_fields={"is_active", "updated_at"})
        self.assertEqual(self.browser.get("/chat/").url, "/login/")
