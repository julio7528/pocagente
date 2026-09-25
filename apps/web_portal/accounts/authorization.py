"""Reusable server-side identity and object authorization primitives."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied

from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.models import Conversation
from apps.web_portal.support.models import SupportHandoff


def is_active_identity(user) -> bool:
    return bool(
        user is not None
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
    )


def has_role(user, role: str) -> bool:
    return is_active_identity(user) and role in User.Role.values and user.role == role


def user_is_admin(user) -> bool:
    return has_role(user, User.Role.ADMIN)


def user_is_client(user) -> bool:
    return has_role(user, User.Role.CLIENT)


def user_is_support_agent(user) -> bool:
    return has_role(user, User.Role.SUPPORT_AGENT)


def require_role(user, role: str) -> None:
    if not has_role(user, role):
        raise PermissionDenied("This action is not permitted.")


def require_admin(user) -> None:
    require_role(user, User.Role.ADMIN)


def require_client(user) -> None:
    require_role(user, User.Role.CLIENT)


def require_support_agent(user) -> None:
    require_role(user, User.Role.SUPPORT_AGENT)


def client_owns_conversation(user, conversation: Conversation) -> bool:
    return (
        user_is_client(user)
        and conversation.owner_id == user.pk
        and conversation.status != Conversation.Status.DELETED
    )


def support_agent_is_assigned_to_human(
    user,
    conversation: Conversation,
    handoff: SupportHandoff | None = None,
) -> bool:
    if not user_is_support_agent(user) or conversation.status != Conversation.Status.HUMAN:
        return False
    if handoff is None:
        try:
            handoff = conversation.support_handoff
        except SupportHandoff.DoesNotExist:
            return False
    return (
        handoff.status == SupportHandoff.Status.ASSIGNED
        and handoff.assigned_support_user_id == user.pk
        and handoff.conversation_id == conversation.pk
    )


def require_client_conversation(user, conversation: Conversation) -> None:
    if not client_owns_conversation(user, conversation):
        raise PermissionDenied("This conversation is not available.")


def require_assigned_human_conversation(
    user,
    conversation: Conversation,
    handoff: SupportHandoff | None = None,
) -> None:
    if not support_agent_is_assigned_to_human(user, conversation, handoff):
        raise PermissionDenied("This conversation is not available.")
