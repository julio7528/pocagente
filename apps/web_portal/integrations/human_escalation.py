"""Typed, server-only client for the narrow Human Escalation transition API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx

from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.models import Conversation
from apps.web_portal.integrations.internal_service import (
    InternalServiceConfigurationError,
    InternalServicePrincipalError,
    request_internal,
)

TransitionAction = Literal["CONFIRM", "ACCEPT", "RESOLVE"]


class HumanTransitionError(Exception):
    """Safe base error for a failed trusted transition call."""


class HumanTransitionConflict(HumanTransitionError):
    """FastAPI rejected a valid but stale or unauthorized state transition."""


class HumanTransitionUnavailable(HumanTransitionError):
    """The trusted transition API could not return a valid result."""


@dataclass(frozen=True)
class TransitionResult:
    action: TransitionAction
    state: str
    status: str
    conversation_id: str
    assigned_operator_id: str | None
    automation_suspended: bool


def _payload(
    *,
    conversation: Conversation,
    action: TransitionAction,
    current_state: str,
    active_operator_id: str | None,
) -> dict:
    request: dict = {
        "conversation_id": str(conversation.pk),
        "current_state": current_state,
        "action": action,
    }
    if action == "RESOLVE":
        request["active_operator_id"] = active_operator_id
    if action in {"CONFIRM", "ACCEPT"}:
        request["reason"] = "USER_REQUESTED_HUMAN"
        request["handoff"] = {
            "conversation_id": str(conversation.pk),
            "problem_summary": conversation.title,
            "reason": "USER_REQUESTED_HUMAN",
            "user_confirmation": True,
        }
    return request


def transition_human_escalation(
    *,
    actor: User,
    conversation: Conversation,
    action: TransitionAction,
    current_state: str,
    active_operator_id: str | None = None,
) -> TransitionResult:
    """Call the private typed API; trusted identity is never body-supplied."""

    role = actor.role
    if action == "CONFIRM" and role != User.Role.CLIENT:
        raise HumanTransitionConflict("The transition is not available.")
    if action in {"ACCEPT", "RESOLVE"} and role != User.Role.SUPPORT_AGENT:
        raise HumanTransitionConflict("The transition is not available.")

    try:
        response = request_internal(
            "POST",
            "/internal/human-escalation/transition",
            actor=actor,
            ops_authorized=False,
            json=_payload(
                conversation=conversation,
                action=action,
                current_state=current_state,
                active_operator_id=active_operator_id,
            ),
        )
    except (httpx.HTTPError, InternalServiceConfigurationError, InternalServicePrincipalError) as exc:
        raise HumanTransitionUnavailable("Human support is temporarily unavailable.") from exc

    if response.status_code == 409:
        raise HumanTransitionConflict("The transition is no longer available.")
    if response.status_code != 200:
        raise HumanTransitionUnavailable("Human support is temporarily unavailable.")
    try:
        data = response.json()
        suspended = data["automation_suspended"]
        assigned_operator = data.get("assigned_operator_id")
        if not isinstance(suspended, bool) or (
            assigned_operator is not None and not isinstance(assigned_operator, str)
        ):
            raise TypeError("Invalid typed transition response")
        result = TransitionResult(
            action=action,
            state=data["state"],
            status=data["status"],
            conversation_id=data["conversation"]["conversation_id"],
            assigned_operator_id=assigned_operator,
            automation_suspended=suspended,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HumanTransitionUnavailable("Human support is temporarily unavailable.") from exc

    if result.conversation_id != str(conversation.pk) or result.status != "TRANSITIONED":
        raise HumanTransitionUnavailable("Human support is temporarily unavailable.")
    expected = {"CONFIRM": "WAITING_HUMAN", "ACCEPT": "HUMAN", "RESOLVE": "RESOLVED"}[action]
    if result.state != expected:
        raise HumanTransitionUnavailable("Human support is temporarily unavailable.")
    if action == "ACCEPT" and (
        result.assigned_operator_id != str(actor.pk) or not result.automation_suspended
    ):
        raise HumanTransitionUnavailable("Human support is temporarily unavailable.")
    if action == "RESOLVE" and result.assigned_operator_id is not None:
        raise HumanTransitionUnavailable("Human support is temporarily unavailable.")
    return result
