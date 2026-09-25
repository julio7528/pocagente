"""Portal orchestration for one CLIENT turn and its private agent execution."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.web_portal.accounts.authorization import require_client, require_client_conversation
from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.context import build_agent_context
from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.conversations.services import (
    ConversationNotWritableError,
    IdempotencyConflictError,
    append_agent_message,
    get_agent_response_for_turn,
    mark_client_turn_failed,
)
from apps.web_portal.integrations.agent_chat import (
    AgentChatClient,
    AgentChatResponse,
    AgentChatTurn,
    build_agent_chat_turn,
)


@dataclass(frozen=True)
class AgentTurnResult:
    outcome: Literal["COMPLETED", "ALREADY_COMPLETED", "NO_ANSWER", "SUSPENDED"]
    response_message: Message | None = None
    response: AgentChatResponse | None = None


def _safe_citation_url(value: str | None) -> str | None:
    if not value or any(ord(char) < 0x20 or char.isspace() for char in value):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return None
        _ = parsed.port
    except ValueError:
        return None
    return value


def _single_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _transcript_answer(response: AgentChatResponse) -> str:
    answer = (response.answer or "").strip()
    if not answer:
        return ""
    citations: list[str] = []
    seen: set[str] = set()
    for citation in response.citations:
        if citation.id in seen:
            continue
        seen.add(citation.id)
        label = _single_line(citation.label)
        attribution = _single_line(citation.attribution)
        url = _safe_citation_url(citation.source_url)
        line = f"[{citation.id}] {label} — {attribution}"
        if url is not None:
            line += f" — {url}"
        citations.append(line)
    if citations:
        answer += "\n\nFontes:\n" + "\n".join(citations)
    return answer


@transaction.atomic
def _prepare_turn(
    *, actor: User, conversation_id: uuid.UUID | str, client_message_id: uuid.UUID | str,
    retry: bool,
) -> tuple[User, Conversation, Message, AgentChatTurn] | AgentTurnResult:
    """Authorize and build context in a short transaction before HTTP begins."""

    try:
        current_actor = User.objects.get(pk=actor.pk)
    except User.DoesNotExist as exc:
        raise PermissionDenied("This action is not permitted.") from exc
    require_client(current_actor)
    if not current_actor.is_active:
        raise PermissionDenied("This action is not permitted.")

    conversation = (
        Conversation.objects.select_for_update()
        .filter(pk=conversation_id, owner_id=current_actor.pk)
        .first()
    )
    if conversation is None:
        raise PermissionDenied("This conversation is not available.")
    require_client_conversation(current_actor, conversation)
    if conversation.status != Conversation.Status.ACTIVE:
        return AgentTurnResult(outcome="SUSPENDED")

    try:
        client_message = Message.objects.select_for_update().get(
            pk=client_message_id,
            conversation=conversation,
            sender_type=Message.SenderType.CLIENT,
            sender_user=current_actor,
        )
    except Message.DoesNotExist as exc:
        raise PermissionDenied("This message is not available.") from exc

    existing = get_agent_response_for_turn(
        conversation=conversation, client_message=client_message
    )
    if existing is not None:
        return AgentTurnResult(outcome="ALREADY_COMPLETED", response_message=existing)
    if client_message.idempotency_key is None:
        raise PermissionDenied("This message is not available.")
    if retry:
        if client_message.processing_status not in {
            Message.ProcessingStatus.PENDING,
            Message.ProcessingStatus.FAILED,
        }:
            return AgentTurnResult(outcome="SUSPENDED")
    elif client_message.processing_status != Message.ProcessingStatus.PENDING:
        return AgentTurnResult(outcome="SUSPENDED")

    context = build_agent_context(current_message=client_message)
    turn = build_agent_chat_turn(
        context=context, client_turn_id=client_message.idempotency_key
    )
    return current_actor, conversation, client_message, turn


def execute_agent_turn(
    *, actor: User, conversation_id: uuid.UUID | str,
    client_message_id: uuid.UUID | str, retry: bool = False,
) -> AgentTurnResult:
    """Run one authorized turn without holding a portal DB transaction over HTTP."""

    prepared = _prepare_turn(
        actor=actor,
        conversation_id=conversation_id,
        client_message_id=client_message_id,
        retry=retry,
    )
    if isinstance(prepared, AgentTurnResult):
        return prepared
    current_actor, conversation, client_message, turn = prepared
    response = AgentChatClient(current_actor).execute(turn)
    body = _transcript_answer(response)
    if not body:
        mark_client_turn_failed(
            conversation=conversation, client_message=client_message
        )
        return AgentTurnResult(outcome="NO_ANSWER", response=response)
    try:
        persisted = append_agent_message(
            conversation=conversation,
            client_message=client_message,
            body=body,
        )
    except ConversationNotWritableError:
        # BLOCKED, WAITING_HUMAN, HUMAN, CLOSED, or DELETED won the race while
        # FastAPI was processing. Do not append automated output after suspension.
        mark_client_turn_failed(
            conversation=conversation, client_message=client_message
        )
        return AgentTurnResult(outcome="SUSPENDED", response=response)
    except IdempotencyConflictError:
        existing = get_agent_response_for_turn(
            conversation=conversation, client_message=client_message
        )
        if existing is not None:
            return AgentTurnResult(
                outcome="ALREADY_COMPLETED", response_message=existing, response=response
            )
        mark_client_turn_failed(
            conversation=conversation, client_message=client_message
        )
        return AgentTurnResult(outcome="NO_ANSWER", response=response)
    return AgentTurnResult(
        outcome="COMPLETED", response_message=persisted.message, response=response
    )
