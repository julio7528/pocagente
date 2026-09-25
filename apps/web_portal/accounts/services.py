"""ADMIN-authorized identity mutations and session revocation."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass

from django.contrib.auth import password_validation
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.web_portal.accounts.authorization import require_admin
from apps.web_portal.accounts.models import ROLE_VALUES, User
from apps.web_portal.support.models import SupportHandoff


class AccountPolicyError(Exception):
    """A safe, domain-level rejection of an account operation."""


class LastActiveAdminError(AccountPolicyError):
    pass


class ActiveSupportAssignmentError(AccountPolicyError):
    pass


class AdminAlreadyBootstrappedError(AccountPolicyError):
    pass


@dataclass(frozen=True)
class AccountMutation:
    user: User
    action: str


# One fixed lock key serializes operations that can affect administrator
# availability. PostgreSQL advisory locks are transaction-scoped and require
# no schema object or migration.
_IDENTITY_LOCK_KEY = 1_381_209_804_120_412


@contextmanager
def _identity_transaction():
    with transaction.atomic():
        if connection.vendor != "postgresql":
            raise RuntimeError("Portal identity policy requires PostgreSQL.")
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [_IDENTITY_LOCK_KEY])
        yield


def _current_admin(actor: User) -> User:
    require_admin(actor)
    try:
        current = User.objects.get(pk=actor.pk)
    except User.DoesNotExist as exc:
        raise PermissionDenied("This action is not permitted.") from exc
    require_admin(current)
    return current


def _validate_role(role: str) -> str:
    if role not in ROLE_VALUES:
        raise AccountPolicyError("Choose one of the approved application roles.")
    return role


def _load_target(user: User | str) -> User:
    try:
        return User.objects.select_for_update().get(pk=getattr(user, "pk", user))
    except User.DoesNotExist as exc:
        raise AccountPolicyError("The user is not available.") from exc


def _active_admin_count() -> int:
    return User.objects.filter(role=User.Role.ADMIN, is_active=True).count()


def _protect_last_admin(target: User, *, new_role: str | None = None, active: bool | None = None) -> None:
    removes_admin = target.role == User.Role.ADMIN and target.is_active and (
        new_role not in (None, User.Role.ADMIN) or active is False
    )
    if removes_admin and _active_admin_count() <= 1:
        raise LastActiveAdminError("At least one active ADMIN account must remain.")


def _has_active_human_assignment(user: User) -> bool:
    return SupportHandoff.objects.filter(
        assigned_support_user=user,
        status=SupportHandoff.Status.ASSIGNED,
        conversation__status="HUMAN",
    ).exists()


def invalidate_user_sessions(user_id) -> int:
    """Delete DB-backed sessions belonging to one user without exposing keys."""
    matching_keys: list[str] = []
    sessions = Session.objects.filter(expire_date__gt=timezone.now()).only(
        "session_key", "session_data"
    )
    for session in sessions.iterator(chunk_size=500):
        data = session.get_decoded()
        if str(data.get("_auth_user_id", "")) == str(user_id):
            matching_keys.append(session.session_key)
    if not matching_keys:
        return 0
    deleted, _ = Session.objects.filter(session_key__in=matching_keys).delete()
    return deleted


def create_user(
    *,
    actor: User,
    username: str,
    password: str,
    role: str,
    is_active: bool,
    email: str = "",
) -> AccountMutation:
    role = _validate_role(role)
    if not isinstance(is_active, bool):
        raise AccountPolicyError("Account activation must be explicit.")
    if not username or not username.strip():
        raise AccountPolicyError("A non-empty username is required.")
    with _identity_transaction():
        _current_admin(actor)
        user = User(username=username, email=email, role=role, is_active=is_active)
        password_validation.validate_password(password, user=user)
        user.set_password(password)
        try:
            user.save(force_insert=True)
        except Exception as exc:
            # Do not disclose database details (including constraint names) to
            # future views; preserve the underlying exception as the cause.
            if isinstance(exc, IntegrityError):
                raise AccountPolicyError("A user with that login already exists.") from exc
            raise
        return AccountMutation(user=user, action="CREATED")


def activate_user(*, actor: User, target: User | str) -> AccountMutation:
    with _identity_transaction():
        _current_admin(actor)
        user = _load_target(target)
        if user.is_active:
            return AccountMutation(user=user, action="UNCHANGED")
        if user.role == User.Role.SUPPORT_AGENT and _has_active_human_assignment(user):
            raise ActiveSupportAssignmentError("Resolve active HUMAN assignments before changing this account.")
        user.is_active = True
        user.save(update_fields={"is_active", "updated_at"})
        return AccountMutation(user=user, action="ACTIVATED")


def deactivate_user(*, actor: User, target: User | str) -> AccountMutation:
    with _identity_transaction():
        _current_admin(actor)
        user = _load_target(target)
        if not user.is_active:
            return AccountMutation(user=user, action="UNCHANGED")
        _protect_last_admin(user, active=False)
        if user.role == User.Role.SUPPORT_AGENT and _has_active_human_assignment(user):
            raise ActiveSupportAssignmentError("Resolve active HUMAN assignments before deactivating this account.")
        user.is_active = False
        user.save(update_fields={"is_active", "updated_at"})
        invalidate_user_sessions(user.pk)
        return AccountMutation(user=user, action="DEACTIVATED")


def change_role(*, actor: User, target: User | str, new_role: str) -> AccountMutation:
    new_role = _validate_role(new_role)
    with _identity_transaction():
        _current_admin(actor)
        user = _load_target(target)
        if user.role == new_role:
            return AccountMutation(user=user, action="UNCHANGED")
        _protect_last_admin(user, new_role=new_role)
        if (
            user.role == User.Role.SUPPORT_AGENT
            and new_role != User.Role.SUPPORT_AGENT
            and _has_active_human_assignment(user)
        ):
            raise ActiveSupportAssignmentError("Resolve active HUMAN assignments before changing this role.")
        user.role = new_role
        user.save(update_fields={"role", "is_staff", "is_superuser", "updated_at"})
        invalidate_user_sessions(user.pk)
        return AccountMutation(user=user, action="ROLE_CHANGED")


def set_user_password(*, actor: User, target: User | str, new_password: str) -> AccountMutation:
    with _identity_transaction():
        _current_admin(actor)
        user = _load_target(target)
        password_validation.validate_password(new_password, user=user)
        user.set_password(new_password)
        user.save(update_fields={"password", "updated_at"})
        invalidate_user_sessions(user.pk)
        return AccountMutation(user=user, action="PASSWORD_CHANGED")


def bootstrap_first_admin(*, username: str, password: str) -> AccountMutation:
    """Create the first active ADMIN; interactive credential collection is in the command."""
    if not username or not username.strip():
        raise AccountPolicyError("A non-empty username is required.")
    with _identity_transaction():
        if User.objects.filter(role=User.Role.ADMIN).exists():
            raise AdminAlreadyBootstrappedError("An ADMIN account already exists; bootstrap was refused.")
        user = User(username=username, role=User.Role.ADMIN, is_active=True)
        password_validation.validate_password(password, user=user)
        user.set_password(password)
        try:
            user.save(force_insert=True)
        except Exception as exc:
            if isinstance(exc, IntegrityError):
                raise AccountPolicyError("The requested login is already in use.") from exc
            raise
        return AccountMutation(user=user, action="BOOTSTRAPPED")
