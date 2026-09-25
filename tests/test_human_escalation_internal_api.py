from fastapi.testclient import TestClient
from pydantic import SecretStr

from apps.agent_api.app.auth import ServiceAuthConfig
from apps.agent_api.app.main import create_app


TOKEN = "phase12-support-transition-test-token"
CONVERSATION = "7f6e3f4e-0ff4-4aa5-9e24-1d669b95ce52"
PACKAGE = {
    "conversation_id": CONVERSATION,
    "problem_summary": "Cliente precisa de atendimento humano",
    "reason": "USER_REQUESTED_HUMAN",
    "user_confirmation": True,
}


def _headers(user_id: str, role: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {TOKEN}",
        "X-Authenticated-User-Id": user_id,
        "X-Authenticated-Role": role,
        "X-Ops-Authorized": "false",
    }


def _client() -> TestClient:
    return TestClient(create_app(auth_config=ServiceAuthConfig(service_token=SecretStr(TOKEN))))


def _transition(client: TestClient, *, user_id: str, role: str, state: str, action: str, handoff=None, active_operator_id=None):
    return client.post(
        "/internal/human-escalation/transition",
        headers=_headers(user_id, role),
        json={
            "conversation_id": CONVERSATION,
            "current_state": state,
            "action": action,
            **({"handoff": handoff} if handoff is not None else {}),
            **({"active_operator_id": active_operator_id} if active_operator_id is not None else {}),
        },
    )


def test_confirm_accept_and_resolve_delegate_to_existing_agent():
    with _client() as client:
        confirmed = _transition(
            client,
            user_id="client-uuid",
            role="CLIENT",
            state="WAITING_CONFIRMATION",
            action="CONFIRM",
            handoff=PACKAGE,
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["state"] == "WAITING_HUMAN"

        accepted = _transition(
            client,
            user_id="support-a-uuid",
            role="SUPPORT_AGENT",
            state="WAITING_HUMAN",
            action="ACCEPT",
            handoff=PACKAGE,
        )
        assert accepted.status_code == 200
        assert accepted.json()["state"] == "HUMAN"
        assert accepted.json()["assigned_operator_id"] == "support-a-uuid"
        assert accepted.json()["automation_suspended"] is True

        wrong_operator = _transition(
            client,
            user_id="support-b-uuid",
            role="SUPPORT_AGENT",
            state="HUMAN",
            action="RESOLVE",
            active_operator_id="support-a-uuid",
        )
        assert wrong_operator.status_code == 409
        assert "ACTIVE_HUMAN_OWNER_MATCH_REQUIRED" not in wrong_operator.text

        resolved = _transition(
            client,
            user_id="support-a-uuid",
            role="SUPPORT_AGENT",
            state="HUMAN",
            action="RESOLVE",
            active_operator_id="support-a-uuid",
        )
        assert resolved.status_code == 200
        assert resolved.json()["state"] == "RESOLVED"


def test_internal_transition_requires_service_auth_and_role():
    with _client() as client:
        unauthenticated = client.post(
            "/internal/human-escalation/transition",
            json={"conversation_id": CONVERSATION, "current_state": "HUMAN", "action": "RESOLVE"},
        )
        assert unauthenticated.status_code == 401

        client_cannot_accept = _transition(
            client,
            user_id="client-uuid",
            role="CLIENT",
            state="WAITING_HUMAN",
            action="ACCEPT",
            handoff=PACKAGE,
        )
        assert client_cannot_accept.status_code == 403


def test_transition_does_not_expose_return_to_automation_or_cross_conversation_package():
    with _client() as client:
        unsupported = _transition(
            client,
            user_id="support-a-uuid",
            role="SUPPORT_AGENT",
            state="HUMAN",
            action="RETURN_TO_AUTOMATION",
        )
        assert unsupported.status_code == 422

        mismatch = dict(PACKAGE, conversation_id="different-conversation")
        rejected = _transition(
            client,
            user_id="support-a-uuid",
            role="SUPPORT_AGENT",
            state="WAITING_HUMAN",
            action="ACCEPT",
            handoff=mismatch,
        )
        assert rejected.status_code == 422
