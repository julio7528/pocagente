"""Phase 12.14 route, CSRF, and complete browser-journey security gates."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import URLResolver, get_resolver, reverse

from apps.agent_api.app.agents.conversational import ConversationalResult
from apps.agent_api.app.agents.human_escalation import (
    ConversationReference,
    HumanEscalationAction,
    HumanEscalationAgent,
    HumanEscalationReason,
    HumanEscalationRequest,
    HumanEscalationState,
)
from apps.agent_api.app.agents.orchestration import OrchestrationResult, OrchestrationStatus
from apps.agent_api.app.agents.router import RouterRoute
from apps.agent_api.app.auth import ServiceAuthConfig
from apps.agent_api.app.chat import ChatApplicationService
from apps.agent_api.app.main import create_app
from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.support.models import SupportHandoff


PASSWORD = "Phase14-Synthetic-Only-Password-91!"
SERVICE_TOKEN = "phase14-in-process-synthetic-service-token"
UNKNOWN_UUID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


# Machine-readable protected product-route inventory. Each route is tied to one
# application role; object routes use an unguessable fixture UUID and therefore
# also exercise denial-before-existence behavior for the other roles.
PROTECTED_ROUTE_MATRIX = (
    (User.Role.CLIENT, "client-landing", ()),
    (User.Role.CLIENT, "chat-new", ()),
    (User.Role.CLIENT, "chat-updates", (UNKNOWN_UUID,)),
    (User.Role.CLIENT, "chat-retry-agent", (UNKNOWN_UUID, UNKNOWN_UUID)),
    (User.Role.CLIENT, "support-confirm", (UNKNOWN_UUID,)),
    (User.Role.CLIENT, "support-request-human", (UNKNOWN_UUID,)),
    (User.Role.CLIENT, "chat-detail", (UNKNOWN_UUID,)),
    (User.Role.CLIENT, "chat-message", (UNKNOWN_UUID,)),
    (User.Role.SUPPORT_AGENT, "support-landing", ()),
    (User.Role.SUPPORT_AGENT, "support-updates", ()),
    (User.Role.SUPPORT_AGENT, "support-conversation", (UNKNOWN_UUID,)),
    (User.Role.SUPPORT_AGENT, "support-conversation-updates", (UNKNOWN_UUID,)),
    (User.Role.SUPPORT_AGENT, "support-claim", (UNKNOWN_UUID,)),
    (User.Role.SUPPORT_AGENT, "support-message", (UNKNOWN_UUID,)),
    (User.Role.SUPPORT_AGENT, "support-close", (UNKNOWN_UUID,)),
    (User.Role.ADMIN, "admin-overview", ()),
    (User.Role.ADMIN, "admin-users", ()),
    (User.Role.ADMIN, "admin-user-create", ()),
    (User.Role.ADMIN, "admin-user-create-submit", ()),
    (User.Role.ADMIN, "admin-user-detail", (UNKNOWN_UUID,)),
    (User.Role.ADMIN, "admin-user-activate", (UNKNOWN_UUID,)),
    (User.Role.ADMIN, "admin-user-deactivate", (UNKNOWN_UUID,)),
    (User.Role.ADMIN, "admin-user-role", (UNKNOWN_UUID,)),
    (User.Role.ADMIN, "admin-user-password", (UNKNOWN_UUID,)),
    (User.Role.ADMIN, "admin-security", ()),
    (User.Role.ADMIN, "admin-security-data", ()),
    (User.Role.ADMIN, "admin-security-event-detail", (987654321,)),
    (User.Role.ADMIN, "admin-conversations", ()),
    (User.Role.ADMIN, "admin-password-requests", ()),
    (User.Role.ADMIN, "admin-password-request-detail", (UNKNOWN_UUID,)),
    (User.Role.ADMIN, "admin-password-request-resolve", (UNKNOWN_UUID,)),
    (User.Role.ADMIN, "admin-password-request-reject", (UNKNOWN_UUID,)),
    (User.Role.ADMIN, "admin-conversation-detail", (UNKNOWN_UUID,)),
    (User.Role.ADMIN, "admin-conversation-block", (UNKNOWN_UUID,)),
    (User.Role.ADMIN, "admin-conversation-unblock", (UNKNOWN_UUID,)),
    (User.Role.ADMIN, "admin-conversation-delete", (UNKNOWN_UUID,)),
)


# Every current state-changing browser route, including the public two-step
# recovery request. The matrix is exercised with both missing and invalid CSRF.
MUTATION_ROUTE_MATRIX = (
    ("login", ()),
    ("logout", ()),
    ("password-reset-request", ()),
    ("password-reset-request-confirm", ()),
    ("chat-new", ()),
    ("chat-message", (UNKNOWN_UUID,)),
    ("chat-retry-agent", (UNKNOWN_UUID, UNKNOWN_UUID)),
    ("support-request-human", (UNKNOWN_UUID,)),
    ("support-claim", (UNKNOWN_UUID,)),
    ("support-message", (UNKNOWN_UUID,)),
    ("support-close", (UNKNOWN_UUID,)),
    ("admin-user-create-submit", ()),
    ("admin-user-activate", (UNKNOWN_UUID,)),
    ("admin-user-deactivate", (UNKNOWN_UUID,)),
    ("admin-user-role", (UNKNOWN_UUID,)),
    ("admin-user-password", (UNKNOWN_UUID,)),
    ("admin-conversation-block", (UNKNOWN_UUID,)),
    ("admin-conversation-unblock", (UNKNOWN_UUID,)),
    ("admin-conversation-delete", (UNKNOWN_UUID,)),
    ("admin-password-request-resolve", (UNKNOWN_UUID,)),
    ("admin-password-request-reject", (UNKNOWN_UUID,)),
)


def _flatten_named_routes(patterns, prefix=""):
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from _flatten_named_routes(pattern.url_patterns, route)
        elif pattern.name:
            yield route, pattern.name


class PortalSecurityInventoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client_user = User.objects.create_user(
            username="phase14.inventory.client", password=PASSWORD, role=User.Role.CLIENT
        )
        cls.support_user = User.objects.create_user(
            username="phase14.inventory.support", password=PASSWORD, role=User.Role.SUPPORT_AGENT
        )
        cls.admin_user = User.objects.create_user(
            username="phase14.inventory.admin", password=PASSWORD, role=User.Role.ADMIN
        )

    def test_inventory_covers_every_protected_product_route(self):
        expected_names = {name for _role, name, _args in PROTECTED_ROUTE_MATRIX}
        actual_names = {
            name
            for route, name in _flatten_named_routes(get_resolver().url_patterns)
            if route.startswith(("chat/", "support/", "admin-portal/"))
        }
        self.assertSetEqual(actual_names, expected_names)

    def test_anonymous_and_wrong_role_matrix_covers_every_protected_route(self):
        anonymous = Client()
        role_clients = {
            User.Role.CLIENT: Client(),
            User.Role.SUPPORT_AGENT: Client(),
            User.Role.ADMIN: Client(),
        }
        role_users = {
            User.Role.CLIENT: self.client_user,
            User.Role.SUPPORT_AGENT: self.support_user,
            User.Role.ADMIN: self.admin_user,
        }
        for role, browser in role_clients.items():
            browser.force_login(role_users[role])

        for allowed_role, route_name, args in PROTECTED_ROUTE_MATRIX:
            path = reverse(route_name, args=args or None)
            with self.subTest(route=route_name, actor="anonymous"):
                response = anonymous.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith("/login/"))
                self.assertNotContains(response, "phase14.inventory", status_code=302)
            for role, browser in role_clients.items():
                if role == allowed_role:
                    continue
                with self.subTest(route=route_name, actor=role):
                    response = browser.get(path)
                    self.assertEqual(response.status_code, 403)
                    self.assertContains(
                        response,
                        "Você não possui permissão para acessar esta área.",
                        status_code=403,
                    )

        # The built-in technical admin remains separate, but authenticated
        # wrong-role users receive the same controlled denial as product areas.
        for path in ("/admin/", "/admin/accounts/user/"):
            for user in (self.client_user, self.support_user):
                browser = Client()
                browser.force_login(user)
                with self.subTest(route=path, actor=user.role):
                    self.assertEqual(browser.get(path).status_code, 403)

    def test_every_state_changing_browser_route_rejects_missing_and_invalid_csrf(self):
        browser = Client(enforce_csrf_checks=True)
        before = (
            User.objects.count(),
            Conversation.objects.count(),
            Message.objects.count(),
            SupportHandoff.objects.count(),
        )
        for route_name, args in MUTATION_ROUTE_MATRIX:
            path = reverse(route_name, args=args or None)
            with self.subTest(route=route_name, token="missing"):
                response = browser.post(path, {})
                self.assertEqual(response.status_code, 403)

            invalid_browser = Client(enforce_csrf_checks=True)
            invalid_browser.get("/login/")
            invalid_browser.cookies[settings.CSRF_COOKIE_NAME] = "invalid-phase14-token"
            with self.subTest(route=route_name, token="invalid"):
                response = invalid_browser.post(
                    path,
                    {"csrfmiddlewaretoken": "invalid-phase14-token"},
                    HTTP_X_CSRFTOKEN="invalid-phase14-token",
                )
                self.assertEqual(response.status_code, 403)

        after = (
            User.objects.count(),
            Conversation.objects.count(),
            Message.objects.count(),
            SupportHandoff.objects.count(),
        )
        self.assertEqual(after, before)


class _InProcessFastAPITransport:
    def __init__(self, client):
        self.client = client
        self.calls = []

    def request(self, method, path, *, headers, params, json):
        self.calls.append({
            "method": method,
            "path": path,
            "headers": dict(headers),
            "params": params,
            "json": json,
        })
        return self.client.request(method, path, headers=headers, params=params, json=json)

    def close(self):
        return None


class _JourneyRuntime:
    def __init__(self, human_agent):
        self.human_agent = human_agent
        self.requests = []

    async def execute(self, request):
        self.requests.append(request)
        conversation = ConversationReference(conversation_id=request.conversation_id)
        if request.message == "Quero falar com um atendente.":
            human_result = self.human_agent.transition(
                HumanEscalationRequest(
                    conversation=conversation,
                    current_state=HumanEscalationState.BOT,
                    action=HumanEscalationAction.OFFER,
                    reason=HumanEscalationReason.USER_REQUESTED_HUMAN,
                )
            )
            return OrchestrationResult(
                status=OrchestrationStatus.COMPLETED,
                route=RouterRoute.HUMAN_ESCALATION,
                reason="HUMAN_CONFIRMATION_OFFERED",
                human_escalation_required=True,
                human_escalation_result=human_result,
            )
        return OrchestrationResult(
            status=OrchestrationStatus.COMPLETED,
            route=RouterRoute.CONVERSATIONAL,
            reason="DETERMINISTIC_PHASE14_E2E",
            conversational_result=ConversationalResult(
                answer=f"Resposta de teste para: {request.message}",
                reason="BOUNDED_CONVERSATIONAL_RESPONSE",
            ),
        )


@override_settings(DEBUG=False)
class CompleteClientToHumanJourneyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="phase14.journey.admin", password=PASSWORD, role=User.Role.ADMIN
        )
        self.client_user = User.objects.create_user(
            username="phase14.journey.client", password=PASSWORD, role=User.Role.CLIENT
        )
        self.support = User.objects.create_user(
            username="phase14.journey.support", password=PASSWORD, role=User.Role.SUPPORT_AGENT
        )

    @staticmethod
    def _csrf(browser):
        if settings.CSRF_COOKIE_NAME not in browser.cookies:
            browser.get("/login/")
        return browser.cookies[settings.CSRF_COOKIE_NAME].value

    def _login(self, browser, user, destination):
        token = self._csrf(browser)
        response = browser.post(
            "/login/",
            {
                "username": user.username,
                "password": PASSWORD,
                "csrfmiddlewaretoken": token,
            },
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, destination)
        return response

    def _post(self, browser, path, data=None, **headers):
        token = self._csrf(browser)
        payload = dict(data or {})
        payload["csrfmiddlewaretoken"] = token
        return browser.post(path, payload, HTTP_X_CSRFTOKEN=token, **headers)

    @override_settings(
        AGENT_API_INTERNAL_URL="http://phase14-in-process-agent",
        AGENT_API_SERVICE_TOKEN=SERVICE_TOKEN,
        AGENT_API_CONNECT_TIMEOUT_SECONDS=1.0,
        AGENT_API_READ_TIMEOUT_SECONDS=2.0,
    )
    def test_complete_persistent_client_agent_human_closed_journey(self):
        human_agent = HumanEscalationAgent()
        runtime = _JourneyRuntime(human_agent)
        app = create_app(
            chat_service=ChatApplicationService(runtime),
            auth_config=ServiceAuthConfig(service_token=SERVICE_TOKEN),
            human_escalation_agent=human_agent,
        )
        from apps.web_portal.integrations import internal_service

        with self.subTest("in-process private FastAPI boundary"):
            from fastapi.testclient import TestClient

            with TestClient(app) as api:
                bridge = _InProcessFastAPITransport(api)
                from unittest.mock import patch

                with patch.object(internal_service, "_pooled_http_client", return_value=bridge):
                    client_browser = Client(enforce_csrf_checks=True)
                    self._login(client_browser, self.client_user, "/chat/")

                    first_text = "O que é a Getnet?"
                    created = self._post(
                        client_browser,
                        "/chat/new/",
                        {"body": first_text, "client_turn_key": str(uuid.uuid4())},
                    )
                    self.assertEqual(created.status_code, 302)
                    conversation_id = created.url.rstrip("/").rsplit("/", 1)[-1]
                    conversation = Conversation.objects.get(pk=conversation_id, owner=self.client_user)
                    self.assertEqual(conversation.status, Conversation.Status.ACTIVE)
                    first_answer = Message.objects.get(
                        conversation=conversation, sender_type=Message.SenderType.AGENT
                    )
                    self.assertIn(first_text, first_answer.body)

                    follow_up = "E quais soluções ela oferece?"
                    second = self._post(
                        client_browser,
                        f"/chat/{conversation_id}/messages/",
                        {"body": follow_up, "client_turn_key": str(uuid.uuid4())},
                    )
                    self.assertEqual(second.status_code, 302)
                    self.assertEqual(second.url, f"/chat/{conversation_id}/")
                    self.assertEqual(len(runtime.requests), 2)
                    self.assertEqual(
                        [item.content for item in runtime.requests[1].conversation_context],
                        [first_text, first_answer.body],
                    )
                    self.assertEqual(runtime.requests[1].message, follow_up)
                    second_answer = (
                        Message.objects.filter(
                            conversation=conversation,
                            sender_type=Message.SenderType.AGENT,
                        )
                        .order_by("created_at", "id")
                        .last()
                    )
                    self.assertIsNotNone(second_answer)
                    self.assertIn(follow_up, second_answer.body)

                    offer_text = "Quero falar com um atendente."
                    offer = self._post(
                        client_browser,
                        f"/chat/{conversation_id}/messages/",
                        {"body": offer_text, "client_turn_key": str(uuid.uuid4())},
                    )
                    self.assertEqual(offer.status_code, 302)
                    conversation.refresh_from_db()
                    self.assertEqual(conversation.status, Conversation.Status.ACTIVE)
                    self.assertFalse(SupportHandoff.objects.filter(conversation=conversation).exists())
                    self.assertContains(client_browser.get(offer.url), "Solicitar atendimento humano")
                    confirm_page = client_browser.get(
                        f"/chat/{conversation_id}/human-support/confirm/"
                    )
                    self.assertEqual(confirm_page.status_code, 200)
                    self.assertContains(confirm_page, "Confirmar solicitação")
                    confirmed = self._post(
                        client_browser,
                        f"/chat/{conversation_id}/human-support/request/",
                        {"confirm_human_support": "on"},
                    )
                    self.assertEqual(confirmed.status_code, 302)
                    handoff = SupportHandoff.objects.get(conversation=conversation)
                    conversation.refresh_from_db()
                    self.assertEqual(conversation.status, Conversation.Status.WAITING_HUMAN)
                    self.assertEqual(handoff.status, SupportHandoff.Status.WAITING)
                    self.assertEqual(SupportHandoff.objects.filter(conversation=conversation).count(), 1)

                    chat_call_count = sum(call["path"] == "/chat" for call in bridge.calls)
                    waiting_message = "Ainda estou aguardando."
                    waiting_post = self._post(
                        client_browser,
                        f"/chat/{conversation_id}/messages/",
                        {"body": waiting_message, "client_turn_key": str(uuid.uuid4())},
                    )
                    self.assertEqual(waiting_post.status_code, 302)
                    self.assertEqual(
                        sum(call["path"] == "/chat" for call in bridge.calls), chat_call_count
                    )

                    support_browser = Client(enforce_csrf_checks=True)
                    self._login(support_browser, self.support, "/support/")
                    queue = support_browser.get("/support/")
                    self.assertContains(queue, conversation.title)
                    waiting_detail = support_browser.get(f"/support/{conversation_id}/")
                    self.assertContains(waiting_detail, waiting_message)
                    claimed = self._post(
                        support_browser, f"/support/{conversation_id}/claim/"
                    )
                    self.assertEqual(claimed.status_code, 302)
                    handoff.refresh_from_db()
                    conversation.refresh_from_db()
                    self.assertEqual(conversation.status, Conversation.Status.HUMAN)
                    self.assertEqual(handoff.status, SupportHandoff.Status.ASSIGNED)
                    self.assertEqual(handoff.assigned_support_user_id, self.support.pk)

                    human_message = "Ainda estou aqui."
                    human_post = self._post(
                        client_browser,
                        f"/chat/{conversation_id}/messages/",
                        {"body": human_message, "client_turn_key": str(uuid.uuid4())},
                    )
                    self.assertEqual(human_post.status_code, 302)
                    self.assertEqual(
                        sum(call["path"] == "/chat" for call in bridge.calls), chat_call_count
                    )

                    support_turn_key = str(uuid.uuid4())
                    support_text = "Olá, vou verificar seu atendimento."
                    support_post = self._post(
                        support_browser,
                        f"/support/{conversation_id}/messages/",
                        {"body": support_text, "support_turn_key": support_turn_key},
                    )
                    self.assertEqual(support_post.status_code, 302)
                    client_history = client_browser.get(f"/chat/{conversation_id}/")
                    for visible_text in (
                        first_text,
                        first_answer.body,
                        follow_up,
                        second_answer.body,
                        offer_text,
                        waiting_message,
                        human_message,
                        support_text,
                    ):
                        self.assertContains(client_history, visible_text)

                    finalized = self._post(
                        support_browser,
                        f"/support/{conversation_id}/close/",
                        {"confirm_finalization": "on"},
                    )
                    self.assertEqual(finalized.status_code, 302)
                    handoff.refresh_from_db()
                    conversation.refresh_from_db()
                    self.assertEqual(conversation.status, Conversation.Status.CLOSED)
                    self.assertEqual(handoff.status, SupportHandoff.Status.RESOLVED)
                    self.assertEqual(handoff.resolved_by_id, self.support.pk)

                    closed_history = client_browser.get(f"/chat/{conversation_id}/")
                    self.assertEqual(closed_history.status_code, 200)
                    self.assertContains(closed_history, support_text)
                    self.assertNotContains(closed_history, 'name="body"')
                    transcript = list(
                        Message.objects.filter(conversation=conversation)
                        .order_by("created_at", "id")
                        .values_list("sender_type", "body")
                    )
                    self.assertEqual(
                        [sender for sender, _body in transcript],
                        [
                            Message.SenderType.CLIENT,
                            Message.SenderType.AGENT,
                            Message.SenderType.CLIENT,
                            Message.SenderType.AGENT,
                            Message.SenderType.CLIENT,
                            Message.SenderType.CLIENT,
                            Message.SenderType.CLIENT,
                            Message.SenderType.SUPPORT_AGENT,
                        ],
                    )
                    before_forged_post = Message.objects.filter(conversation=conversation).count()
                    before_forged_chat_calls = sum(
                        call["path"] == "/chat" for call in bridge.calls
                    )
                    forged = self._post(
                        client_browser,
                        f"/chat/{conversation_id}/messages/",
                        {
                            "body": "forged post after close",
                            "client_turn_key": str(uuid.uuid4()),
                            "user_id": str(self.admin.pk),
                            "role": User.Role.ADMIN,
                            "ops_authorized": "true",
                            "service_token": SERVICE_TOKEN,
                        },
                        HTTP_X_AUTHENTICATED_ROLE=User.Role.ADMIN,
                        HTTP_X_OPS_AUTHORIZED="true",
                    )
                    self.assertEqual(forged.status_code, 409)
                    self.assertEqual(
                        Message.objects.filter(conversation=conversation).count(),
                        before_forged_post,
                    )
                    self.assertEqual(
                        sum(call["path"] == "/chat" for call in bridge.calls),
                        before_forged_chat_calls,
                    )
                    self.assertEqual(len(runtime.requests), 3)
                    self.assertEqual(
                        SupportHandoff.objects.filter(conversation=conversation).count(), 1
                    )
                    self.assertTrue(all(
                        call["headers"]["X-Ops-Authorized"] == (
                            "true" if call["path"] == "/chat" else "false"
                        )
                        for call in bridge.calls
                    ))
                    self.assertTrue(all(
                        call["json"]["conversation_id"] == str(conversation.pk)
                        for call in bridge.calls
                    ))
                    self.assertTrue(all(
                        SERVICE_TOKEN not in response.content.decode("utf-8")
                        for response in (client_history, closed_history, confirmed)
                    ))
