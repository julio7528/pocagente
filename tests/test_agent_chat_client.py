"""Typed portal client contract for the private FastAPI chat boundary."""

from __future__ import annotations

import os
import uuid
from types import SimpleNamespace

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apps.web_portal.config.settings")
os.environ.setdefault("DJANGO_SECRET_KEY", "phase12-chat-client-test-key")

import django

django.setup()

import httpx
import pytest
from django.test import override_settings

from apps.web_portal.conversations.context import (
    ContextMessage,
    ContextRole,
    ConversationContext,
)
from apps.web_portal.integrations import agent_chat, internal_service
from apps.web_portal.integrations.agent_chat import (
    AgentChatAuthorizationFailure,
    AgentChatClient,
    AgentChatContractFailure,
    AgentChatUnavailable,
    build_agent_chat_turn,
)


def _actor(*, role: str = "CLIENT", active: bool = True):
    return SimpleNamespace(
        is_authenticated=True,
        is_active=active,
        role=role,
        pk=uuid.UUID("5e2cc379-5c81-416a-b4b6-cdce850f8e16"),
    )


def _context() -> ConversationContext:
    conversation_id = "daff3c1b-37ce-43f4-af23-296b6eddb780"
    return ConversationContext(
        conversation_id=conversation_id,
        messages=(
            ContextMessage("prior-1", ContextRole.USER, "Me fale sobre Get Smart."),
            ContextMessage("prior-2", ContextRole.ASSISTANT, "Posso ajudar."),
            ContextMessage("current-1", ContextRole.USER, "E quanto custa?"),
        ),
        character_count=52,
    )


class _Response:
    def __init__(self, status_code: int, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _Transport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, path, *, headers, params, json):
        self.calls.append((method, path, dict(headers), params, json))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def close(self):
        return None


@pytest.fixture(autouse=True)
def close_shared_transport():
    yield
    internal_service.clear_internal_http_client_cache()


@override_settings(
    AGENT_API_INTERNAL_URL="http://private-agent-api:8000",
    AGENT_API_SERVICE_TOKEN="server-only-chat-token",
    AGENT_API_CONNECT_TIMEOUT_SECONDS=1.25,
    AGENT_API_READ_TIMEOUT_SECONDS=3.5,
)
def test_client_sends_typed_portal_turn_with_server_derived_ops_claim(monkeypatch):
    transport = _Transport(
        [
            _Response(
                200,
                {
                    "status": "COMPLETED",
                    "route": "KNOWLEDGE",
                    "reason": "GROUNDED",
                    "answer": "Resposta contextual.",
                    "citations": [],
                    "unexpected_graph_state": {"secret": "must be ignored"},
                },
            )
        ]
    )
    pool_configuration = []

    def pool(base_url, connect_timeout, read_timeout):
        pool_configuration.append((base_url, connect_timeout, read_timeout))
        return transport

    monkeypatch.setattr(internal_service, "_pooled_http_client", pool)
    turn = build_agent_chat_turn(context=_context(), client_turn_id=uuid.uuid4())
    actor = _actor()

    response = AgentChatClient(actor).execute(turn)

    assert response.answer == "Resposta contextual."
    assert not hasattr(response, "unexpected_graph_state")
    assert len(transport.calls) == 1
    assert pool_configuration == [("http://private-agent-api:8000", 1.25, 3.5)]
    method, path, headers, params, payload = transport.calls[0]
    assert (method, path, params) == ("POST", "/chat", None)
    assert headers == {
        "Authorization": "Bearer server-only-chat-token",
        "X-Authenticated-User-Id": str(actor.pk),
        "X-Authenticated-Role": "CLIENT",
        "X-Ops-Authorized": "true",
    }
    assert payload["user_id"] == str(actor.pk)
    assert payload["conversation_id"] == str(turn.conversation_id)
    assert payload["client_turn_id"] == str(turn.client_turn_id)
    assert payload["conversation_context"][-1]["content"] == "E quanto custa?"
    assert "server-only-chat-token" not in repr(response)


@override_settings(AGENT_API_INTERNAL_URL="", AGENT_API_SERVICE_TOKEN="server-only-chat-token")
def test_missing_private_base_url_fails_closed_before_opening_transport(monkeypatch):
    opened = []
    monkeypatch.setattr(
        internal_service,
        "_pooled_http_client",
        lambda *args: opened.append(args),
    )
    turn = build_agent_chat_turn(context=_context(), client_turn_id=uuid.uuid4())

    with pytest.raises(AgentChatUnavailable):
        AgentChatClient(_actor()).execute(turn)

    assert opened == []


@override_settings(
    AGENT_API_INTERNAL_URL="http://private-agent-api:8000",
    AGENT_API_SERVICE_TOKEN="server-only-chat-token",
)
def test_client_retries_a_definite_503_once_with_identical_turn(monkeypatch):
    transport = _Transport(
        [
            _Response(503),
            _Response(200, {"status": "COMPLETED", "route": "CONVERSATIONAL", "reason": "ANSWERED", "answer": "Olá."}),
        ]
    )
    monkeypatch.setattr(internal_service, "_pooled_http_client", lambda *_args: transport)
    turn = build_agent_chat_turn(context=_context(), client_turn_id=uuid.uuid4())

    result = AgentChatClient(_actor()).execute(turn)

    assert result.answer == "Olá."
    assert len(transport.calls) == 2
    assert transport.calls[0][4] == transport.calls[1][4]


@override_settings(
    AGENT_API_INTERNAL_URL="http://private-agent-api:8000",
    AGENT_API_SERVICE_TOKEN="server-only-chat-token",
)
def test_second_503_is_retryable_and_ambiguous_read_timeout_is_not_retried(monkeypatch):
    transport = _Transport([_Response(503), _Response(503)])
    monkeypatch.setattr(internal_service, "_pooled_http_client", lambda *_args: transport)
    turn = build_agent_chat_turn(context=_context(), client_turn_id=uuid.uuid4())
    with pytest.raises(AgentChatUnavailable) as unavailable:
        AgentChatClient(_actor()).execute(turn)
    assert unavailable.value.retryable is True
    assert len(transport.calls) == 2

    transport = _Transport([httpx.ReadTimeout("private request may have completed")])
    monkeypatch.setattr(internal_service, "_pooled_http_client", lambda *_args: transport)
    with pytest.raises(AgentChatUnavailable) as timeout:
        AgentChatClient(_actor()).execute(turn)
    assert timeout.value.retryable is True
    assert len(transport.calls) == 1
    assert "private request" not in str(timeout.value)


@override_settings(
    AGENT_API_INTERNAL_URL="http://private-agent-api:8000",
    AGENT_API_SERVICE_TOKEN="server-only-chat-token",
)
def test_connection_failure_retries_once_but_reuses_same_turn(monkeypatch):
    transport = _Transport([
        httpx.ConnectError("connection refused"),
        _Response(200, {"status": "COMPLETED", "route": "CONVERSATIONAL", "reason": "ANSWERED", "answer": "Olá."}),
    ])
    monkeypatch.setattr(internal_service, "_pooled_http_client", lambda *_args: transport)
    turn = build_agent_chat_turn(context=_context(), client_turn_id=uuid.uuid4())

    result = AgentChatClient(_actor()).execute(turn)

    assert result.answer == "Olá."
    assert len(transport.calls) == 2
    assert transport.calls[0][4] == transport.calls[1][4]


@override_settings(
    AGENT_API_INTERNAL_URL="http://private-agent-api:8000",
    AGENT_API_SERVICE_TOKEN="server-only-chat-token",
)
def test_mismatched_human_offer_conversation_is_a_safe_contract_failure(monkeypatch):
    transport = _Transport([_Response(200, {
        "status": "COMPLETED",
        "route": "HUMAN_ESCALATION",
        "reason": "OFFERED",
        "answer": "Posso encaminhar para atendimento humano.",
        "requires_human": True,
        "human": {
            "state": "WAITING_CONFIRMATION",
            "conversation_id": "33333333-3333-4333-8333-333333333333",
            "assigned_operator_id": None,
            "automation_suspended": False,
        },
    })])
    monkeypatch.setattr(internal_service, "_pooled_http_client", lambda *_args: transport)
    turn = build_agent_chat_turn(context=_context(), client_turn_id=uuid.uuid4())

    with pytest.raises(AgentChatContractFailure):
        AgentChatClient(_actor()).execute(turn)


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (401, AgentChatAuthorizationFailure),
        (403, AgentChatAuthorizationFailure),
        (422, AgentChatContractFailure),
    ],
)
@override_settings(
    AGENT_API_INTERNAL_URL="http://private-agent-api:8000",
    AGENT_API_SERVICE_TOKEN="server-only-chat-token",
)
def test_client_maps_internal_http_errors_without_response_body_leak(
    monkeypatch, status, error_type
):
    transport = _Transport([_Response(status, {"detail": "secret-diagnostic-DO-NOT-SHOW"})])
    monkeypatch.setattr(internal_service, "_pooled_http_client", lambda *_args: transport)
    turn = build_agent_chat_turn(context=_context(), client_turn_id=uuid.uuid4())

    with pytest.raises(error_type) as error:
        AgentChatClient(_actor()).execute(turn)

    assert "secret-diagnostic" not in str(error.value)
    assert len(transport.calls) == 1


def test_chat_client_is_client_only_and_ops_claim_is_server_derived(monkeypatch):
    calls = []
    monkeypatch.setattr(agent_chat, "request_internal", lambda *args, **kwargs: calls.append((args, kwargs)))
    turn = build_agent_chat_turn(context=_context(), client_turn_id=uuid.uuid4())

    for actor in (_actor(role="SUPPORT_AGENT"), _actor(role="ADMIN"), _actor(active=False)):
        with pytest.raises(AgentChatAuthorizationFailure):
            AgentChatClient(actor).execute(turn)
    assert calls == []

    client_headers = internal_service.trusted_service_headers(
        _actor(), ops_authorized=True, endpoint="/chat"
    )
    assert client_headers["X-Ops-Authorized"] == "true"
    with pytest.raises(internal_service.InternalServicePrincipalError):
        internal_service.trusted_service_headers(
            _actor(role="ADMIN"), ops_authorized=True, endpoint="/chat"
        )
    with pytest.raises(internal_service.InternalServicePrincipalError):
        internal_service.trusted_service_headers(
            _actor(), ops_authorized=True, endpoint="/internal/admin/audit/summary"
        )
