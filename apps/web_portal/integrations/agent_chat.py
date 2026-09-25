"""Typed, bounded Django client for the internal FastAPI ``/chat`` endpoint."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.context import ContextRole, ConversationContext
from apps.web_portal.integrations.internal_service import (
    InternalServiceConfigurationError,
    InternalServicePrincipalError,
    request_internal,
)


class AgentChatUnavailable(Exception):
    """Safe internal chat failure, optionally eligible for an explicit retry."""

    def __init__(self, *, retryable: bool = False) -> None:
        self.retryable = retryable
        super().__init__("Agent chat is temporarily unavailable.")


class AgentChatAuthorizationFailure(AgentChatUnavailable):
    """The trusted internal service rejected authentication or authorization."""


class AgentChatContractFailure(AgentChatUnavailable):
    """The internal service rejected or violated the typed chat contract."""


class AgentChatCitation(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=256)
    attribution: str = Field(min_length=1, max_length=512)
    source_url: str | None = Field(default=None, max_length=2_048)


class AgentChatHumanState(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    state: Literal["BOT", "WAITING_CONFIRMATION", "WAITING_HUMAN", "HUMAN", "RESOLVED"]
    conversation_id: str = Field(min_length=1, max_length=128)
    assigned_operator_id: str | None = Field(default=None, max_length=128)
    automation_suspended: bool = False


class AgentChatResponse(BaseModel):
    """Only the safe user-facing response subset consumed by the portal."""

    model_config = ConfigDict(extra="ignore", frozen=True, str_strip_whitespace=True)

    status: str = Field(min_length=1, max_length=64)
    route: str = Field(min_length=1, max_length=64)
    answer: str | None = Field(default=None, max_length=50_000)
    citations: tuple[AgentChatCitation, ...] = Field(default=(), max_length=32)
    requires_human: bool = False
    human: AgentChatHumanState | None = None
    reason: str = Field(min_length=1, max_length=128)


class AgentChatContextMessage(BaseModel):
    """Allowlisted transcript data; sender labels do not represent claims."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message_id: str = Field(min_length=1, max_length=128)
    sender_type: Literal["CLIENT", "AGENT", "SUPPORT_AGENT", "SYSTEM"]
    content: str = Field(min_length=1, max_length=6_000)
    truncated: bool = False
    original_character_count: int | None = Field(default=None, ge=1, le=10_000_000)


@dataclass(frozen=True)
class AgentChatTurn:
    """One projected portal turn; its full original remains in Django."""

    message: str
    conversation_id: uuid.UUID
    client_turn_id: uuid.UUID
    conversation_context: tuple[AgentChatContextMessage, ...]


def build_agent_chat_turn(
    *, context: ConversationContext, client_turn_id: uuid.UUID | str
) -> AgentChatTurn:
    """Translate the Phase 12.6 context DTO without reimplementing its limits."""

    if not context.messages:
        raise AgentChatContractFailure
    try:
        turn_id = client_turn_id if isinstance(client_turn_id, uuid.UUID) else uuid.UUID(str(client_turn_id))
        conversation_id = uuid.UUID(context.conversation_id)
    except (ValueError, TypeError, AttributeError):
        raise AgentChatContractFailure from None

    sender_types = {
        ContextRole.USER: "CLIENT",
        ContextRole.ASSISTANT: "AGENT",
        ContextRole.SUPPORT: "SUPPORT_AGENT",
        ContextRole.SYSTEM: "SYSTEM",
    }
    messages = tuple(
        AgentChatContextMessage(
            message_id=item.message_id,
            sender_type=sender_types[item.role],
            content=item.content,
            truncated=item.truncated,
            original_character_count=item.original_character_count,
        )
        for item in context.messages
    )
    return AgentChatTurn(
        message=context.messages[-1].content,
        conversation_id=conversation_id,
        client_turn_id=turn_id,
        conversation_context=messages,
    )


class AgentChatClient:
    """Call only the existing internal FastAPI ``/chat`` execution boundary."""

    ENDPOINT = "/chat"

    def __init__(self, actor: User) -> None:
        self._actor = actor

    def execute(self, turn: AgentChatTurn) -> AgentChatResponse:
        if (
            not getattr(self._actor, "is_authenticated", False)
            or not self._actor.is_active
            or self._actor.role != User.Role.CLIENT
        ):
            raise AgentChatAuthorizationFailure
        payload = {
            "message": turn.message,
            "user_id": str(self._actor.pk),
            "conversation_id": str(turn.conversation_id),
            "client_turn_id": str(turn.client_turn_id),
            "conversation_context": [item.model_dump() for item in turn.conversation_context],
        }
        response = self._request_with_bounded_retry(payload)
        if response.status_code in {401, 403}:
            raise AgentChatAuthorizationFailure
        if response.status_code == 422:
            raise AgentChatContractFailure
        if response.status_code == 503:
            raise AgentChatUnavailable(retryable=True)
        if response.status_code != 200:
            raise AgentChatUnavailable(retryable=response.status_code >= 500)
        try:
            parsed = AgentChatResponse.model_validate(response.json())
        except (ValidationError, TypeError, ValueError):
            raise AgentChatContractFailure from None
        if (
            parsed.human is not None
            and parsed.human.conversation_id != str(turn.conversation_id)
        ):
            raise AgentChatContractFailure
        return parsed

    def _request_with_bounded_retry(self, payload: dict):
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = request_internal(
                    "POST", self.ENDPOINT, actor=self._actor, ops_authorized=False, json=payload
                )
            except (InternalServiceConfigurationError, InternalServicePrincipalError):
                raise AgentChatUnavailable
            except (httpx.ConnectError, httpx.ConnectTimeout) as error:
                last_error = error
                if attempt == 0:
                    continue
                raise AgentChatUnavailable(retryable=True) from error
            except httpx.ReadTimeout as error:
                # The remote runtime may have completed the turn; a second
                # automatic request could repeat provider work.
                raise AgentChatUnavailable(retryable=True) from error
            except httpx.HTTPError as error:
                raise AgentChatUnavailable(retryable=True) from error
            if response.status_code != 503 or attempt == 1:
                return response
        raise AgentChatUnavailable(retryable=True) from last_error
