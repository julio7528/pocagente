"""Portal-owned conversation and immutable transcript application services."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.web_portal.accounts.authorization import (
    require_assigned_human_conversation,
    require_client,
    require_client_conversation,
)
from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.conversations.titles import conversation_title_from_first_message


class ConversationPolicyError(Exception):
    """Safe rejection of a portal conversation operation."""


class ConversationNotWritableError(ConversationPolicyError):
    pass


class IdempotencyConflictError(ConversationPolicyError):
    pass


@dataclass(frozen=True)
class PersistedMessage:
    message: Message
    created: bool


@dataclass(frozen=True)
class CreatedConversation:
    conversation: Conversation
    first_message: Message
    created: bool = True


def _validated_body(body: str) -> str:
    if not isinstance(body, str) or not body.strip():
        raise ValidationError("Message content must not be blank.")
    return body


def _validated_turn_key(turn_key: uuid.UUID | str) -> uuid.UUID:
    try:
        return turn_key if isinstance(turn_key, uuid.UUID) else uuid.UUID(str(turn_key))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValidationError("A valid client turn key is required.") from exc


def _current_client(user: User) -> User:
    try:
        current = User.objects.get(pk=user.pk)
    except User.DoesNotExist as exc:
        raise PermissionDenied("This action is not permitted.") from exc
    require_client(current)
    return current


def _locked_conversation(conversation: Conversation | uuid.UUID) -> Conversation:
    conversation_id = getattr(conversation, "pk", conversation)
    try:
        return Conversation.objects.select_for_update().get(pk=conversation_id)
    except Conversation.DoesNotExist as exc:
        raise ConversationPolicyError("The conversation is not available.") from exc


def _touch(conversation: Conversation) -> None:
    timestamp = timezone.now()
    Conversation.objects.filter(pk=conversation.pk).update(updated_at=timestamp)
    conversation.updated_at = timestamp


def _assert_client_writable(conversation: Conversation) -> None:
    if conversation.status not in {
        Conversation.Status.ACTIVE,
        Conversation.Status.WAITING_HUMAN,
        Conversation.Status.HUMAN,
    }:
        raise ConversationNotWritableError("This conversation is read-only.")


def _assert_agent_writable(conversation: Conversation) -> None:
    if conversation.status != Conversation.Status.ACTIVE:
        raise ConversationNotWritableError("Automated responses are unavailable in this state.")


def _assert_normal_writable(conversation: Conversation) -> None:
    if conversation.status in {
        Conversation.Status.CLOSED,
        Conversation.Status.BLOCKED,
        Conversation.Status.DELETED,
    }:
        raise ConversationNotWritableError("This conversation is read-only.")


@transaction.atomic
def create_conversation(
    *, owner: User, first_message: str, client_turn_key: uuid.UUID | str
) -> CreatedConversation:
    owner = _current_client(owner)
    body = _validated_body(first_message)
    turn_key = _validated_turn_key(client_turn_key)
    conversation = Conversation.objects.create(
        owner=owner,
        status=Conversation.Status.ACTIVE,
        title=conversation_title_from_first_message(body),
    )
    message = Message.objects.create(
        conversation=conversation,
        sender_type=Message.SenderType.CLIENT,
        sender_user=owner,
        body=body,
        idempotency_key=turn_key,
        processing_status=Message.ProcessingStatus.PENDING,
    )
    _touch(conversation)
    return CreatedConversation(conversation=conversation, first_message=message)


@transaction.atomic
def create_conversation_once(
    *, owner: User, first_message: str, client_turn_key: uuid.UUID | str
) -> CreatedConversation:
    """Make a replayed first-message form resolve to its existing thread."""
    body = _validated_body(first_message)
    turn_key = _validated_turn_key(client_turn_key)
    try:
        current_owner = User.objects.select_for_update().get(pk=owner.pk)
    except User.DoesNotExist as exc:
        raise PermissionDenied("This action is not permitted.") from exc
    require_client(current_owner)
    existing = (
        Message.objects.select_related("conversation")
        .filter(
            sender_type=Message.SenderType.CLIENT,
            sender_user=current_owner,
            idempotency_key=turn_key,
            conversation__owner=current_owner,
        )
        .first()
    )
    if existing is not None:
        first_message_id = (
            Message.objects.filter(conversation=existing.conversation)
            .order_by("created_at", "id")
            .values_list("id", flat=True)
            .first()
        )
        if (
            existing.body != body
            or existing.id != first_message_id
            or existing.conversation.status == Conversation.Status.DELETED
        ):
            raise IdempotencyConflictError("The client turn key is already in use.")
        return CreatedConversation(
            conversation=existing.conversation, first_message=existing, created=False
        )
    return create_conversation(
        owner=current_owner, first_message=body, client_turn_key=turn_key
    )


def list_owned_conversations(*, owner: User) -> QuerySet[Conversation]:
    owner = _current_client(owner)
    return Conversation.objects.filter(owner=owner).exclude(
        status=Conversation.Status.DELETED
    ).order_by("-updated_at", "id")


def get_owned_conversation(*, owner: User, conversation_id: uuid.UUID | str) -> Conversation:
    owner = _current_client(owner)
    try:
        conversation = Conversation.objects.get(pk=conversation_id, owner=owner)
    except (Conversation.DoesNotExist, ValidationError, ValueError) as exc:
        raise PermissionDenied("This conversation is not available.") from exc
    require_client_conversation(owner, conversation)
    return conversation


def get_conversation_history(*, owner: User, conversation_id: uuid.UUID | str) -> QuerySet[Message]:
    conversation = get_owned_conversation(owner=owner, conversation_id=conversation_id)
    return Message.objects.filter(conversation=conversation).order_by("created_at", "id")


@transaction.atomic
def append_client_message(
    *, actor: User, conversation: Conversation | uuid.UUID, body: str,
    client_turn_key: uuid.UUID | str,
) -> PersistedMessage:
    actor = _current_client(actor)
    content = _validated_body(body)
    turn_key = _validated_turn_key(client_turn_key)
    locked = _locked_conversation(conversation)
    require_client_conversation(actor, locked)
    _assert_client_writable(locked)
    existing = Message.objects.filter(
        conversation=locked,
        sender_type=Message.SenderType.CLIENT,
        idempotency_key=turn_key,
    ).first()
    if existing is not None:
        if existing.sender_user_id != actor.pk or existing.body != content:
            raise IdempotencyConflictError("The client turn key is already in use.")
        return PersistedMessage(message=existing, created=False)
    message = Message.objects.create(
        conversation=locked,
        sender_type=Message.SenderType.CLIENT,
        sender_user=actor,
        body=content,
        idempotency_key=turn_key,
        processing_status=Message.ProcessingStatus.PENDING,
    )
    _touch(locked)
    return PersistedMessage(message=message, created=True)


def _agent_response_id(client_message_id: uuid.UUID) -> uuid.UUID:
    return uuid.uuid5(client_message_id, "portal-agent-response")


def get_agent_response_for_turn(
    *, conversation: Conversation | uuid.UUID, client_message: Message | uuid.UUID
) -> Message | None:
    """Return the deterministic AGENT row for a persisted CLIENT turn, if present."""

    conversation_id = getattr(conversation, "pk", conversation)
    client_message_id = getattr(client_message, "pk", client_message)
    return Message.objects.filter(
        pk=_agent_response_id(client_message_id),
        conversation_id=conversation_id,
        sender_type=Message.SenderType.AGENT,
        sender_user__isnull=True,
    ).first()


@transaction.atomic
def append_agent_message(
    *, conversation: Conversation | uuid.UUID, client_message: Message | uuid.UUID,
    body: str,
) -> PersistedMessage:
    content = _validated_body(body)
    locked = _locked_conversation(conversation)
    _assert_agent_writable(locked)
    client_message_id = getattr(client_message, "pk", client_message)
    try:
        turn = Message.objects.select_for_update().get(
            pk=client_message_id,
            conversation=locked,
            sender_type=Message.SenderType.CLIENT,
        )
    except Message.DoesNotExist as exc:
        raise ConversationPolicyError("The client turn is not available.") from exc
    response_id = _agent_response_id(turn.id)
    existing = Message.objects.filter(pk=response_id).first()
    if existing is not None:
        if existing.conversation_id != locked.pk or existing.body != content:
            raise IdempotencyConflictError("An agent result already exists for this turn.")
        return PersistedMessage(message=existing, created=False)
    response = Message.objects.create(
        id=response_id,
        conversation=locked,
        sender_type=Message.SenderType.AGENT,
        sender_user=None,
        body=content,
        processing_status=Message.ProcessingStatus.COMPLETED,
    )
    Message.objects.filter(pk=turn.pk).update(processing_status=Message.ProcessingStatus.COMPLETED)
    turn.processing_status = Message.ProcessingStatus.COMPLETED
    _touch(locked)
    return PersistedMessage(message=response, created=True)


@transaction.atomic
def mark_client_turn_failed(
    *, conversation: Conversation | uuid.UUID, client_message: Message | uuid.UUID
) -> Message:
    locked = _locked_conversation(conversation)
    client_message_id = getattr(client_message, "pk", client_message)
    try:
        turn = Message.objects.select_for_update().get(
            pk=client_message_id,
            conversation=locked,
            sender_type=Message.SenderType.CLIENT,
        )
    except Message.DoesNotExist as exc:
        raise ConversationPolicyError("The client turn is not available.") from exc
    existing_response = Message.objects.filter(pk=_agent_response_id(turn.id)).first()
    if existing_response is not None:
        # A competing request may already have committed the one allowed result.
        return turn
    Message.objects.filter(pk=turn.pk).update(processing_status=Message.ProcessingStatus.FAILED)
    turn.processing_status = Message.ProcessingStatus.FAILED
    return turn


@transaction.atomic
def append_system_message(
    *, conversation: Conversation | uuid.UUID, body: str
) -> PersistedMessage:
    content = _validated_body(body)
    locked = _locked_conversation(conversation)
    _assert_normal_writable(locked)
    message = Message.objects.create(
        conversation=locked,
        sender_type=Message.SenderType.SYSTEM,
        sender_user=None,
        body=content,
        processing_status=Message.ProcessingStatus.COMPLETED,
    )
    _touch(locked)
    return PersistedMessage(message=message, created=True)


@transaction.atomic
def append_support_message(
    *, actor: User, conversation: Conversation | uuid.UUID, body: str,
    support_turn_key: uuid.UUID | str | None = None,
) -> PersistedMessage:
    content = _validated_body(body)
    turn_key = _validated_turn_key(support_turn_key or uuid.uuid4())
    locked = _locked_conversation(conversation)
    _assert_normal_writable(locked)
    if locked.status != Conversation.Status.HUMAN:
        raise ConversationNotWritableError("Human support is not active for this conversation.")
    require_assigned_human_conversation(actor, locked)
    message_id = uuid.uuid5(locked.pk, f"support:{actor.pk}:{turn_key}")
    existing = Message.objects.filter(pk=message_id).first()
    if existing is not None:
        if (
            existing.conversation_id != locked.pk
            or existing.sender_type != Message.SenderType.SUPPORT_AGENT
            or existing.sender_user_id != actor.pk
            or existing.body != content
        ):
            raise IdempotencyConflictError("The support turn key is already in use.")
        return PersistedMessage(message=existing, created=False)
    message = Message.objects.create(
        id=message_id,
        conversation=locked,
        sender_type=Message.SenderType.SUPPORT_AGENT,
        sender_user=actor,
        body=content,
        processing_status=Message.ProcessingStatus.COMPLETED,
    )
    _touch(locked)
    return PersistedMessage(message=message, created=True)
