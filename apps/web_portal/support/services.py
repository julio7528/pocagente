"""Transactional support-handoff lifecycle over portal-owned records."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.web_portal.accounts.authorization import require_client, require_support_agent
from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.conversations.services import (
    ConversationNotWritableError,
    IdempotencyConflictError,
    PersistedMessage,
    append_support_message as _append_support_message,
)
from apps.web_portal.integrations.human_escalation import (
    HumanTransitionConflict,
    HumanTransitionUnavailable,
    transition_human_escalation,
)
from apps.web_portal.support.models import SupportHandoff


class SupportOperationConflict(Exception):
    """A valid support action no longer matches the durable portal state."""


class SupportConversationUnavailable(Exception):
    """The conversation is outside the caller's support access scope."""


@dataclass(frozen=True)
class HandoffOperation:
    conversation: Conversation
    handoff: SupportHandoff
    created: bool


def _current_user(actor: User, role: str) -> User:
    try:
        current = User.objects.get(pk=actor.pk)
    except User.DoesNotExist as exc:
        raise PermissionDenied("This action is not permitted.") from exc
    if role == User.Role.CLIENT:
        require_client(current)
    else:
        require_support_agent(current)
    return current


def _locked_conversation(conversation_id: uuid.UUID | str, *, owner_id=None) -> Conversation:
    query = Conversation.objects.select_for_update().filter(pk=conversation_id)
    if owner_id is not None:
        query = query.filter(owner_id=owner_id)
    try:
        return query.get()
    except (Conversation.DoesNotExist, ValueError, ValidationError) as exc:
        raise SupportConversationUnavailable("This conversation is not available.") from exc


def get_support_conversation(*, actor: User, conversation_id: uuid.UUID | str) -> Conversation:
    actor = _current_user(actor, User.Role.SUPPORT_AGENT)
    try:
        conversation = (
            Conversation.objects.select_related("support_handoff", "owner")
            .get(pk=conversation_id)
        )
    except (Conversation.DoesNotExist, ValueError, ValidationError) as exc:
        raise SupportConversationUnavailable("This conversation is not available.") from exc
    try:
        handoff = conversation.support_handoff
    except SupportHandoff.DoesNotExist as exc:
        raise SupportConversationUnavailable("This conversation is not available.") from exc
    if conversation.status == Conversation.Status.WAITING_HUMAN:
        allowed = handoff.status == SupportHandoff.Status.WAITING and handoff.assigned_support_user_id is None
    else:
        allowed = (
            handoff.assigned_support_user_id == actor.pk
            and (
                (conversation.status == Conversation.Status.HUMAN and handoff.status == SupportHandoff.Status.ASSIGNED)
                or (conversation.status == Conversation.Status.CLOSED and handoff.status == SupportHandoff.Status.RESOLVED)
            )
        )
    if not allowed:
        raise SupportConversationUnavailable("This conversation is not available.")
    return conversation


def waiting_handoffs(*, actor: User) -> QuerySet[SupportHandoff]:
    _current_user(actor, User.Role.SUPPORT_AGENT)
    return (
        SupportHandoff.objects.select_related("conversation", "conversation__owner")
        .filter(status=SupportHandoff.Status.WAITING, assigned_support_user__isnull=True,
                conversation__status=Conversation.Status.WAITING_HUMAN)
        .order_by("requested_at", "id")
    )


def assigned_handoffs(*, actor: User) -> QuerySet[SupportHandoff]:
    actor = _current_user(actor, User.Role.SUPPORT_AGENT)
    return (
        SupportHandoff.objects.select_related("conversation", "conversation__owner")
        .filter(status=SupportHandoff.Status.ASSIGNED, assigned_support_user=actor,
                conversation__status=Conversation.Status.HUMAN)
        .order_by("-conversation__updated_at", "id")
    )


def finalized_handoffs(*, actor: User) -> QuerySet[SupportHandoff]:
    actor = _current_user(actor, User.Role.SUPPORT_AGENT)
    return (
        SupportHandoff.objects.select_related("conversation", "conversation__owner")
        .filter(status=SupportHandoff.Status.RESOLVED, assigned_support_user=actor,
                conversation__status=Conversation.Status.CLOSED)
        .order_by("-resolved_at", "id")
    )


@transaction.atomic
def request_human_support(
    *, actor: User, conversation_id: uuid.UUID | str, explicit_confirmation: bool
) -> HandoffOperation:
    """Commit one client-confirmed human handoff in the same conversation."""

    actor = _current_user(actor, User.Role.CLIENT)
    if explicit_confirmation is not True:
        raise SupportOperationConflict("Explicit confirmation is required.")
    conversation = _locked_conversation(conversation_id, owner_id=actor.pk)
    if conversation.owner_id != actor.pk or conversation.status == Conversation.Status.DELETED:
        raise SupportConversationUnavailable("This conversation is not available.")

    existing = SupportHandoff.objects.filter(conversation=conversation).first()
    if existing is not None:
        if conversation.status == Conversation.Status.WAITING_HUMAN and existing.status == SupportHandoff.Status.WAITING:
            return HandoffOperation(conversation, existing, created=False)
        raise SupportOperationConflict("Human support has already started for this conversation.")
    if conversation.status != Conversation.Status.ACTIVE:
        raise ConversationNotWritableError("This conversation cannot be transferred to human support.")

    try:
        result = transition_human_escalation(
            actor=actor, conversation=conversation, action="CONFIRM", current_state="WAITING_CONFIRMATION"
        )
    except HumanTransitionConflict as exc:
        raise SupportOperationConflict("The support request is no longer available.") from exc
    except HumanTransitionUnavailable:
        raise
    if result.state != "WAITING_HUMAN":
        raise SupportOperationConflict("The support request is no longer available.")

    now = timezone.now()
    conversation.status = Conversation.Status.WAITING_HUMAN
    conversation.updated_at = now
    conversation.save(update_fields=("status", "updated_at"))
    handoff = SupportHandoff.objects.create(conversation=conversation, requested_at=now)
    return HandoffOperation(conversation, handoff, created=True)


@transaction.atomic
def claim_handoff(*, actor: User, conversation_id: uuid.UUID | str) -> HandoffOperation:
    """Serialize claimants and persist only the operator returned by the agent."""

    actor = _current_user(actor, User.Role.SUPPORT_AGENT)
    conversation = _locked_conversation(conversation_id)
    try:
        handoff = SupportHandoff.objects.select_for_update().get(conversation=conversation)
    except SupportHandoff.DoesNotExist as exc:
        raise SupportConversationUnavailable("This conversation is not available.") from exc

    if (
        conversation.status == Conversation.Status.HUMAN
        and handoff.status == SupportHandoff.Status.ASSIGNED
        and handoff.assigned_support_user_id == actor.pk
    ):
        return HandoffOperation(conversation, handoff, created=False)
    if conversation.status != Conversation.Status.WAITING_HUMAN or handoff.status != SupportHandoff.Status.WAITING:
        raise SupportOperationConflict("This waiting conversation has already been claimed.")

    try:
        result = transition_human_escalation(
            actor=actor, conversation=conversation, action="ACCEPT", current_state="WAITING_HUMAN"
        )
    except HumanTransitionConflict as exc:
        raise SupportOperationConflict("This waiting conversation has already been claimed.") from exc
    except HumanTransitionUnavailable:
        raise
    if (
        result.state != "HUMAN"
        or result.assigned_operator_id != str(actor.pk)
        or not result.automation_suspended
    ):
        raise HumanTransitionUnavailable("Human support is temporarily unavailable.")

    now = timezone.now()
    handoff.status = SupportHandoff.Status.ASSIGNED
    handoff.assigned_support_user = actor
    handoff.accepted_at = now
    handoff.save(update_fields=("status", "assigned_support_user", "accepted_at"))
    conversation.status = Conversation.Status.HUMAN
    conversation.updated_at = now
    conversation.save(update_fields=("status", "updated_at"))
    return HandoffOperation(conversation, handoff, created=True)


@transaction.atomic
def append_assigned_support_message(
    *, actor: User, conversation_id: uuid.UUID | str, body: str, support_turn_key: uuid.UUID | str
) -> PersistedMessage:
    actor = _current_user(actor, User.Role.SUPPORT_AGENT)
    conversation = _locked_conversation(conversation_id)
    try:
        handoff = SupportHandoff.objects.select_for_update().get(conversation=conversation)
    except SupportHandoff.DoesNotExist as exc:
        raise SupportConversationUnavailable("This conversation is not available.") from exc
    if (
        conversation.status != Conversation.Status.HUMAN
        or handoff.status != SupportHandoff.Status.ASSIGNED
        or handoff.assigned_support_user_id != actor.pk
    ):
        raise SupportConversationUnavailable("This conversation is not available.")
    return _append_support_message(
        actor=actor,
        conversation=conversation,
        body=body,
        support_turn_key=support_turn_key,
    )


@transaction.atomic
def finalize_handoff(*, actor: User, conversation_id: uuid.UUID | str) -> HandoffOperation:
    actor = _current_user(actor, User.Role.SUPPORT_AGENT)
    conversation = _locked_conversation(conversation_id)
    try:
        handoff = SupportHandoff.objects.select_for_update().get(conversation=conversation)
    except SupportHandoff.DoesNotExist as exc:
        raise SupportConversationUnavailable("This conversation is not available.") from exc

    if (
        conversation.status == Conversation.Status.CLOSED
        and handoff.status == SupportHandoff.Status.RESOLVED
        and handoff.resolved_by_id == actor.pk
    ):
        return HandoffOperation(conversation, handoff, created=False)
    if (
        conversation.status != Conversation.Status.HUMAN
        or handoff.status != SupportHandoff.Status.ASSIGNED
        or handoff.assigned_support_user_id != actor.pk
    ):
        raise SupportConversationUnavailable("This conversation is not available.")

    try:
        result = transition_human_escalation(
            actor=actor,
            conversation=conversation,
            action="RESOLVE",
            current_state="HUMAN",
            active_operator_id=str(handoff.assigned_support_user_id),
        )
    except HumanTransitionConflict as exc:
        raise SupportOperationConflict("The support interaction could not be finalized.") from exc
    except HumanTransitionUnavailable:
        raise
    if result.state != "RESOLVED" or result.assigned_operator_id is not None or result.automation_suspended:
        raise HumanTransitionUnavailable("Human support is temporarily unavailable.")

    now = timezone.now()
    handoff.status = SupportHandoff.Status.RESOLVED
    handoff.resolved_at = now
    handoff.resolved_by = actor
    handoff.save(update_fields=("status", "resolved_at", "resolved_by"))
    conversation.status = Conversation.Status.CLOSED
    conversation.updated_at = now
    conversation.save(update_fields=("status", "updated_at"))
    return HandoffOperation(conversation, handoff, created=True)


def conversation_message_version(conversation: Conversation) -> str:
    latest = conversation.messages.order_by("-created_at", "-id").values_list("id", flat=True).first()
    return f"{conversation.status}:{conversation.updated_at.isoformat()}:{latest or ''}"
