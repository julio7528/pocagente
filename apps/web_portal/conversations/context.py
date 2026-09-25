"""Provider-neutral, same-conversation context selection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from django.db.models import Q

from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.conversations.services import ConversationNotWritableError


MAX_PRIOR_MESSAGES = 12
MAX_CONTEXT_CHARACTERS = 6_000


class ContextRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SUPPORT = "support"
    SYSTEM = "system"


SENDER_CONTEXT_ROLE = {
    Message.SenderType.CLIENT: ContextRole.USER,
    Message.SenderType.AGENT: ContextRole.ASSISTANT,
    Message.SenderType.SUPPORT_AGENT: ContextRole.SUPPORT,
    Message.SenderType.SYSTEM: ContextRole.SYSTEM,
}


@dataclass(frozen=True)
class ContextMessage:
    message_id: str
    role: ContextRole
    content: str
    truncated: bool = False
    original_character_count: int | None = None


@dataclass(frozen=True)
class ConversationContext:
    conversation_id: str
    messages: tuple[ContextMessage, ...]
    character_count: int


def _as_context_message(message: Message) -> ContextMessage:
    return ContextMessage(
        message_id=str(message.id),
        role=SENDER_CONTEXT_ROLE[message.sender_type],
        content=message.body,
    )


def build_agent_context(*, current_message: Message) -> ConversationContext:
    """Build an actionable AI context for one persisted ACTIVE client turn."""
    if current_message.sender_type != Message.SenderType.CLIENT:
        raise ValueError("The current context message must be a CLIENT turn.")
    conversation = Conversation.objects.get(pk=current_message.conversation_id)
    if conversation.status != Conversation.Status.ACTIVE:
        raise ConversationNotWritableError("Automated context is unavailable in this state.")

    current_body = current_message.body
    if len(current_body) > MAX_CONTEXT_CHARACTERS:
        current = ContextMessage(
            message_id=str(current_message.id),
            role=ContextRole.USER,
            content=current_body[:MAX_CONTEXT_CHARACTERS],
            truncated=True,
            original_character_count=len(current_body),
        )
        return ConversationContext(
            conversation_id=str(conversation.id),
            messages=(current,),
            character_count=MAX_CONTEXT_CHARACTERS,
        )

    prior_query = Message.objects.filter(conversation=conversation).filter(
        Q(created_at__lt=current_message.created_at)
        | Q(created_at=current_message.created_at, id__lt=current_message.id)
    )
    newest_prior = list(prior_query.order_by("-created_at", "-id")[:MAX_PRIOR_MESSAGES])
    selected = list(reversed(newest_prior))
    total = len(current_body) + sum(len(message.body) for message in selected)
    while selected and total > MAX_CONTEXT_CHARACTERS:
        total -= len(selected.pop(0).body)

    context_messages = tuple(_as_context_message(message) for message in selected) + (
        _as_context_message(current_message),
    )
    return ConversationContext(
        conversation_id=str(conversation.id),
        messages=context_messages,
        character_count=total,
    )
