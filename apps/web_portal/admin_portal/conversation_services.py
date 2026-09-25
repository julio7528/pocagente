"""ADMIN-only conversation inspection and lifecycle application services."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.web_portal.accounts.authorization import require_admin
from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.support.models import SupportHandoff


class AdminConversationError(Exception):
    """Safe base error for product ADMIN conversation operations."""


class AdminConversationConflict(AdminConversationError):
    """The requested action conflicts with the durable lifecycle state."""


class AdminConversationUnavailable(AdminConversationError):
    """The requested conversation is not available."""


@dataclass(frozen=True)
class ConversationAdminFilters:
    query: str = ""
    owner_username: str = ""
    status: str = ""
    date_from: date | None = None
    date_to: date | None = None


_BLOCKABLE_STATES = {
    Conversation.Status.ACTIVE,
    Conversation.Status.WAITING_HUMAN,
    Conversation.Status.HUMAN,
}
_PRIOR_BLOCK_STATES = _BLOCKABLE_STATES
_ACTIVE_HANDOFF_STATES = {SupportHandoff.Status.WAITING, SupportHandoff.Status.ASSIGNED}


def _current_admin(actor: User, *, lock: bool = False) -> User:
    require_admin(actor)
    query = User.objects
    if lock:
        query = query.select_for_update()
    try:
        current = query.get(pk=actor.pk)
    except User.DoesNotExist as exc:
        raise PermissionDenied("This action is not permitted.") from exc
    require_admin(current)
    return current


def _validated_uuid(value: uuid.UUID | str) -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise AdminConversationUnavailable("This conversation is not available.") from exc


def _locked_conversation(conversation_id: uuid.UUID | str) -> Conversation:
    try:
        return Conversation.objects.select_for_update().get(pk=_validated_uuid(conversation_id))
    except (Conversation.DoesNotExist, ValidationError) as exc:
        raise AdminConversationUnavailable("This conversation is not available.") from exc


def _locked_handoff(conversation: Conversation) -> SupportHandoff | None:
    return (
        SupportHandoff.objects.select_for_update()
        .filter(conversation_id=conversation.pk)
        .first()
    )


def _conversation_queryset() -> QuerySet[Conversation]:
    return (
        Conversation.objects.select_related(
            "owner",
            "deleted_by",
            "support_handoff",
            "support_handoff__assigned_support_user",
            "support_handoff__resolved_by",
        )
        .order_by("-updated_at", "-id")
    )


def list_admin_conversations(
    *, actor: User, filters: ConversationAdminFilters
) -> QuerySet[Conversation]:
    """Return all admin-visible states using one validated canonical filter."""

    _current_admin(actor)
    if len(filters.query) > 100 or len(filters.owner_username) > 150:
        raise ValidationError("Search values exceed the allowed length.")
    if filters.status and filters.status not in Conversation.Status.values:
        raise ValidationError("Choose an approved conversation status.")
    if (filters.date_from is None) != (filters.date_to is None):
        raise ValidationError("Both date range endpoints are required.")
    if filters.date_from and filters.date_to:
        if filters.date_from > filters.date_to:
            raise ValidationError("The date range is invalid.")
        if (filters.date_to - filters.date_from).days > 365:
            raise ValidationError("The date range exceeds 365 days.")

    conversations = _conversation_queryset()
    if filters.query:
        conversations = conversations.filter(
            Q(title__icontains=filters.query)
            | Q(owner__username__icontains=filters.query)
        )
    if filters.owner_username:
        conversations = conversations.filter(
            owner__username__icontains=filters.owner_username
        )
    if filters.status:
        conversations = conversations.filter(status=filters.status)
    if filters.date_from and filters.date_to:
        local_tz = timezone.get_current_timezone()
        lower = timezone.make_aware(datetime.combine(filters.date_from, time.min), local_tz)
        upper_date = filters.date_to + timedelta(days=1)
        upper = timezone.make_aware(datetime.combine(upper_date, time.min), local_tz)
        conversations = conversations.filter(created_at__gte=lower, created_at__lt=upper)
    return conversations


def get_admin_conversation(*, actor: User, conversation_id: uuid.UUID | str) -> Conversation:
    _current_admin(actor)
    try:
        return _conversation_queryset().get(pk=_validated_uuid(conversation_id))
    except (Conversation.DoesNotExist, ValidationError) as exc:
        raise AdminConversationUnavailable("This conversation is not available.") from exc


def get_admin_history(*, actor: User, conversation: Conversation | uuid.UUID | str) -> QuerySet[Message]:
    _current_admin(actor)
    conversation_id = getattr(conversation, "pk", conversation)
    _validated_uuid(conversation_id)
    return Message.objects.filter(conversation_id=conversation_id).order_by("created_at", "id")


def _assert_block_state_consistent(
    conversation: Conversation, handoff: SupportHandoff | None
) -> None:
    if conversation.status == Conversation.Status.ACTIVE:
        if handoff and handoff.status in {
            SupportHandoff.Status.WAITING,
            SupportHandoff.Status.ASSIGNED,
            SupportHandoff.Status.RESOLVED,
        }:
            raise AdminConversationConflict("The conversation lifecycle is inconsistent.")
        return
    if conversation.status == Conversation.Status.WAITING_HUMAN:
        if not handoff or handoff.status != SupportHandoff.Status.WAITING or handoff.assigned_support_user_id:
            raise AdminConversationConflict("The conversation lifecycle is inconsistent.")
        return
    if conversation.status == Conversation.Status.HUMAN:
        if not handoff or handoff.status != SupportHandoff.Status.ASSIGNED or not handoff.assigned_support_user_id:
            raise AdminConversationConflict("The conversation lifecycle is inconsistent.")
        return
    raise AdminConversationConflict("This conversation cannot be blocked in its current state.")


@transaction.atomic
def block_conversation(*, actor: User, conversation_id: uuid.UUID | str) -> Conversation:
    """Freeze an active lifecycle without changing its handoff or assignment."""

    _current_admin(actor, lock=True)
    conversation = _locked_conversation(conversation_id)
    handoff = _locked_handoff(conversation)
    if conversation.status == Conversation.Status.BLOCKED:
        raise AdminConversationConflict("This conversation is already blocked.")
    _assert_block_state_consistent(conversation, handoff)
    now = timezone.now()
    conversation.status_before_block = conversation.status
    conversation.status = Conversation.Status.BLOCKED
    conversation.updated_at = now
    conversation.save(update_fields=("status", "status_before_block", "updated_at"))
    return conversation


def _assert_valid_restoration(prior: str, handoff: SupportHandoff | None) -> None:
    if prior == Conversation.Status.ACTIVE:
        if handoff and handoff.status in {
            SupportHandoff.Status.WAITING,
            SupportHandoff.Status.ASSIGNED,
            SupportHandoff.Status.RESOLVED,
        }:
            raise AdminConversationConflict("The saved state cannot be safely restored.")
        return
    if prior == Conversation.Status.WAITING_HUMAN:
        if not handoff or handoff.status != SupportHandoff.Status.WAITING or handoff.assigned_support_user_id:
            raise AdminConversationConflict("The saved state cannot be safely restored.")
        return
    if prior == Conversation.Status.HUMAN:
        if not handoff or handoff.status != SupportHandoff.Status.ASSIGNED or not handoff.assigned_support_user_id:
            raise AdminConversationConflict("The saved state cannot be safely restored.")
        assigned_user = (
            User.objects.select_for_update()
            .filter(pk=handoff.assigned_support_user_id)
            .only("role", "is_active")
            .first()
        )
        if (
            assigned_user is None
            or assigned_user.role != User.Role.SUPPORT_AGENT
            or not assigned_user.is_active
        ):
            raise AdminConversationConflict("The saved state cannot be safely restored.")
        return
    raise AdminConversationConflict("The saved state cannot be safely restored.")


@transaction.atomic
def unblock_conversation(*, actor: User, conversation_id: uuid.UUID | str) -> Conversation:
    """Restore only the service-recorded, still-valid pre-block state."""

    _current_admin(actor, lock=True)
    conversation = _locked_conversation(conversation_id)
    handoff = _locked_handoff(conversation)
    if conversation.status != Conversation.Status.BLOCKED:
        raise AdminConversationConflict("This conversation is not blocked.")
    prior = conversation.status_before_block
    if prior not in _PRIOR_BLOCK_STATES:
        raise AdminConversationConflict("The saved state cannot be safely restored.")
    _assert_valid_restoration(prior, handoff)
    conversation.status = prior
    conversation.status_before_block = None
    conversation.updated_at = timezone.now()
    conversation.save(update_fields=("status", "status_before_block", "updated_at"))
    return conversation


@transaction.atomic
def soft_delete_conversation(*, actor: User, conversation_id: uuid.UUID | str) -> Conversation:
    """Write a retained tombstone; active support handoffs must first be resolved."""

    admin = _current_admin(actor, lock=True)
    conversation = _locked_conversation(conversation_id)
    handoff = _locked_handoff(conversation)
    if conversation.status == Conversation.Status.DELETED:
        raise AdminConversationConflict("This conversation is already deleted.")
    if handoff and handoff.status in _ACTIVE_HANDOFF_STATES:
        raise AdminConversationConflict(
            "A conversa possui um atendimento humano ativo e não pode ser apagada."
        )
    conversation.status = Conversation.Status.DELETED
    conversation.status_before_block = None
    conversation.deleted_at = timezone.now()
    conversation.deleted_by = admin
    conversation.updated_at = conversation.deleted_at
    conversation.save(
        update_fields=(
            "status",
            "status_before_block",
            "deleted_at",
            "deleted_by",
            "updated_at",
        )
    )
    return conversation
