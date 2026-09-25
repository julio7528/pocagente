"""Django portal turns through the real FastAPI route, entirely in process."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from fastapi.testclient import TestClient

from apps.agent_api.app.agents.conversational import ConversationalResult
from apps.agent_api.app.agents.human_escalation import (
    ConversationReference,
    HumanEscalationReason,
    HumanEscalationResult,
    HumanEscalationState,
    HumanEscalationStatus,
)
from apps.agent_api.app.agents.orchestration import OrchestrationResult, OrchestrationStatus
from apps.agent_api.app.agents.router import RouterRoute
from apps.agent_api.app.auth import ServiceAuthConfig
from apps.agent_api.app.chat import ChatApplicationService
from apps.agent_api.app.main import create_app
from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.agent_turns import execute_agent_turn
from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.conversations.services import append_client_message, create_conversation
from apps.web_portal.integrations import internal_service
from apps.web_portal.support.models import SupportHandoff


SERVICE_TOKEN = "phase12-13-in-process-token"


class DeterministicPortalAgent:
    """Stable fixture for the API/runtime boundary; no external providers run."""

    def __init__(self, *, human_offer: bool = False):
        self.requests = []
        self.human_offer = human_offer

    async def execute(self, request):
        self.requests.append(request)
        if self.human_offer:
            human = HumanEscalationResult(
                status=HumanEscalationStatus.TRANSITIONED,
                conversation=ConversationReference(
                    conversation_id=request.conversation_id or "legacy-runtime-correlation"
                ),
                state=HumanEscalationState.WAITING_CONFIRMATION,
                reason=HumanEscalationReason.USER_REQUESTED_HUMAN,
                assigned_operator_id=None,
                automation_suspended=False,
            )
            return OrchestrationResult(
                status=OrchestrationStatus.COMPLETED,
                route=RouterRoute.HUMAN_ESCALATION,
                reason="HUMAN_CONFIRMATION_OFFERED",
                human_escalation_required=True,
                human_escalation_result=human,
            )
        return OrchestrationResult(
            status=OrchestrationStatus.COMPLETED,
            route=RouterRoute.CONVERSATIONAL,
            reason="CONVERSATION_COMPLETED",
            conversational_result=ConversationalResult(
                answer="Resposta determinística do runtime Getnet.",
                reason="BOUNDED_CONVERSATIONAL_RESPONSE",
            ),
        )


class InProcessFastAPITransport:
    def __init__(self, fastapi_client):
        self.client = fastapi_client
        self.calls = []

    def request(self, method, path, *, headers, params, json):
        self.calls.append((method, path, dict(headers), params, json))
        return self.client.request(
            method, path, headers=headers, params=params, json=json
        )

    def close(self):
        return None


class DjangoFastAPIChatIntegrationTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username="phase13.integration.client",
            password="Safe-Test-Password-13!",
            role=User.Role.CLIENT,
        )

    @override_settings(
        AGENT_API_INTERNAL_URL="http://in-process-agent-api",
        AGENT_API_SERVICE_TOKEN=SERVICE_TOKEN,
        AGENT_API_CONNECT_TIMEOUT_SECONDS=1.0,
        AGENT_API_READ_TIMEOUT_SECONDS=2.0,
    )
    def test_same_conversation_context_crosses_real_chat_route_and_is_isolated(self):
        runtime = DeterministicPortalAgent()
        app = create_app(
            chat_service=ChatApplicationService(runtime),
            auth_config=ServiceAuthConfig(service_token=SERVICE_TOKEN),
        )
        with TestClient(app) as api:
            bridge = InProcessFastAPITransport(api)
            with patch.object(internal_service, "_pooled_http_client", return_value=bridge):
                get_smart = create_conversation(
                    owner=self.client_user,
                    first_message="Me fale sobre a Get Smart.",
                    client_turn_key=uuid.uuid4(),
                )
                first = execute_agent_turn(
                    actor=self.client_user,
                    conversation_id=get_smart.conversation.pk,
                    client_message_id=get_smart.first_message.pk,
                )
                self.assertEqual(first.outcome, "COMPLETED")
                follow_up = append_client_message(
                    actor=self.client_user,
                    conversation=get_smart.conversation,
                    body="E quanto custa?",
                    client_turn_key=uuid.uuid4(),
                )
                second = execute_agent_turn(
                    actor=self.client_user,
                    conversation_id=get_smart.conversation.pk,
                    client_message_id=follow_up.message.pk,
                )
                self.assertEqual(second.outcome, "COMPLETED")

                other = create_conversation(
                    owner=self.client_user,
                    first_message="Quero saber sobre maquininha.",
                    client_turn_key=uuid.uuid4(),
                )
                other_first = execute_agent_turn(
                    actor=self.client_user,
                    conversation_id=other.conversation.pk,
                    client_message_id=other.first_message.pk,
                )
                self.assertEqual(other_first.outcome, "COMPLETED")
                other_follow_up = append_client_message(
                    actor=self.client_user,
                    conversation=other.conversation,
                    body="E qual o prazo?",
                    client_turn_key=uuid.uuid4(),
                )
                third = execute_agent_turn(
                    actor=self.client_user,
                    conversation_id=other.conversation.pk,
                    client_message_id=other_follow_up.message.pk,
                )
                self.assertEqual(third.outcome, "COMPLETED")

        self.assertEqual(len(runtime.requests), 4)
        prior = runtime.requests[1].conversation_context
        self.assertEqual(
            [item.content for item in prior],
            ["Me fale sobre a Get Smart.", "Resposta determinística do runtime Getnet."],
        )
        self.assertTrue(all(
            item.content != "E quanto custa?" for item in prior
        ))
        other_context = runtime.requests[3].conversation_context
        self.assertEqual(
            [item.content for item in other_context],
            ["Quero saber sobre maquininha.", "Resposta determinística do runtime Getnet."],
        )
        self.assertNotIn("Get Smart", " ".join(item.content for item in other_context))
        self.assertEqual(
            runtime.requests[1].ops_access_context.can_read_operational_facts,
            True,
        )
        self.assertEqual(runtime.requests[1].ops_access_context.principal_id, str(self.client_user.pk))

        for conversation in (get_smart.conversation, other.conversation):
            self.assertEqual(
                Message.objects.filter(
                    conversation=conversation,
                    sender_type=Message.SenderType.CLIENT,
                ).count(),
                2,
            )
            self.assertEqual(
                Message.objects.filter(
                    conversation=conversation,
                    sender_type=Message.SenderType.AGENT,
                ).count(),
                2,
            )

    @override_settings(
        AGENT_API_INTERNAL_URL="http://in-process-agent-api",
        AGENT_API_SERVICE_TOKEN=SERVICE_TOKEN,
    )
    def test_ai_human_offer_stays_active_until_existing_explicit_confirmation(self):
        runtime = DeterministicPortalAgent(human_offer=True)
        app = create_app(
            chat_service=ChatApplicationService(runtime),
            auth_config=ServiceAuthConfig(service_token=SERVICE_TOKEN),
        )
        with TestClient(app) as api:
            bridge = InProcessFastAPITransport(api)
            with patch.object(internal_service, "_pooled_http_client", return_value=bridge):
                browser = Client(enforce_csrf_checks=True)
                browser.force_login(self.client_user)
                browser.get("/chat/")
                csrf = browser.cookies["csrftoken"].value
                response = browser.post(
                    "/chat/new/",
                    {
                        "body": "Quero falar com uma pessoa.",
                        "client_turn_key": str(uuid.uuid4()),
                        "csrfmiddlewaretoken": csrf,
                    },
                    HTTP_X_CSRFTOKEN=csrf,
                )

        self.assertEqual(response.status_code, 302)
        method, path, headers, _params, payload = bridge.calls[0]
        self.assertEqual((method, path), ("POST", "/chat"))
        self.assertEqual(headers["X-Authenticated-Role"], "CLIENT")
        self.assertEqual(headers["X-Ops-Authorized"], "true")
        self.assertEqual(payload["conversation_id"], response.url.removeprefix("/chat/").removesuffix("/"))
        self.assertEqual(payload["conversation_context"][-1]["content"], "Quero falar com uma pessoa.")
        conversation = Conversation.objects.get(owner=self.client_user)
        self.assertEqual(conversation.status, Conversation.Status.ACTIVE)
        self.assertFalse(SupportHandoff.objects.filter(conversation=conversation).exists())
        self.assertEqual(Message.objects.filter(conversation=conversation, sender_type=Message.SenderType.AGENT).count(), 0)
        page = browser.get(response.url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Solicitar atendimento humano")
        self.assertContains(page, "O atendimento humano está disponível para confirmação.")
        confirmation = browser.get(f"/chat/{conversation.pk}/human-support/confirm/")
        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, "Confirmar solicitação")
        self.assertEqual(Conversation.objects.get(pk=conversation.pk).status, Conversation.Status.ACTIVE)

    @override_settings(
        AGENT_API_INTERNAL_URL="http://in-process-agent-api",
        AGENT_API_SERVICE_TOKEN=SERVICE_TOKEN,
    )
    def test_outgoing_context_keeps_twelve_prior_and_accepted_character_projection(self):
        runtime = DeterministicPortalAgent()
        app = create_app(
            chat_service=ChatApplicationService(runtime),
            auth_config=ServiceAuthConfig(service_token=SERVICE_TOKEN),
        )
        with TestClient(app) as api:
            bridge = InProcessFastAPITransport(api)
            with patch.object(internal_service, "_pooled_http_client", return_value=bridge):
                thread = create_conversation(
                    owner=self.client_user,
                    first_message="prior-00",
                    client_turn_key=uuid.uuid4(),
                )
                for number in range(1, 15):
                    append_client_message(
                        actor=self.client_user,
                        conversation=thread.conversation,
                        body=f"prior-{number:02d}",
                        client_turn_key=uuid.uuid4(),
                    )
                current = append_client_message(
                    actor=self.client_user,
                    conversation=thread.conversation,
                    body="current turn",
                    client_turn_key=uuid.uuid4(),
                )
                result = execute_agent_turn(
                    actor=self.client_user,
                    conversation_id=thread.conversation.pk,
                    client_message_id=current.message.pk,
                )
                self.assertEqual(result.outcome, "COMPLETED")

                for character_count in (5_999, 6_000, 6_001):
                    body = "ç" * character_count
                    oversized = create_conversation(
                        owner=self.client_user,
                        first_message=body,
                        client_turn_key=uuid.uuid4(),
                    )
                    result = execute_agent_turn(
                        actor=self.client_user,
                        conversation_id=oversized.conversation.pk,
                        client_message_id=oversized.first_message.pk,
                    )
                    self.assertEqual(result.outcome, "COMPLETED")
                    oversized.first_message.refresh_from_db()
                    self.assertEqual(oversized.first_message.body, body)

        context = bridge.calls[0][4]["conversation_context"]
        self.assertEqual(len(context) - 1, 12)
        self.assertEqual(context[0]["content"], "prior-03")
        self.assertEqual(context[-1]["content"], "current turn")
        for index, character_count in enumerate((5_999, 6_000, 6_001), start=1):
            payload = bridge.calls[index][4]
            item = payload["conversation_context"]
            expected = min(character_count, 6_000)
            self.assertEqual(len(payload["message"]), expected)
            self.assertEqual(len(item), 1)
            self.assertEqual(len(item[0]["content"]), expected)
            self.assertEqual(item[0]["sender_type"], "CLIENT")
            if character_count > 6_000:
                self.assertTrue(item[0]["truncated"])
                self.assertEqual(item[0]["original_character_count"], character_count)
            else:
                self.assertFalse(item[0]["truncated"])
                self.assertIsNone(item[0]["original_character_count"])
