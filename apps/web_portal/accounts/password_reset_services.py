"""Portal-owned password-reset request workflow services."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.web_portal.accounts.authorization import require_admin
from apps.web_portal.accounts.models import PortalUserManager, User
from apps.web_portal.accounts.services import AccountPolicyError, set_user_password
from apps.web_portal.support.models import PasswordResetRequest


class PasswordResetRequestConflict(Exception):
    """The request is no longer open for the requested operation."""


class PasswordResetRequestUnavailable(Exception):
    """The requested reset item is not available."""


class SubmissionDisposition(StrEnum):
    CREATED = "CREATED"
    REUSED = "REUSED"
    IGNORED = "IGNORED"


@dataclass(frozen=True)
class PasswordResetSubmission:
    disposition: SubmissionDisposition


@dataclass(frozen=True)
class PasswordResetRequestFilters:
    status: str = PasswordResetRequest.Status.OPEN
    query: str = ""


@dataclass(frozen=True)
class PasswordResetMutation:
    request: PasswordResetRequest
    acting_admin_was_requester: bool


def _current_admin(actor: User) -> User:
    require_admin(actor)
    try:
        current = User.objects.only("id", "role", "is_active").get(pk=actor.pk)
    except User.DoesNotExist as exc:
        raise PermissionDenied("This action is not permitted.") from exc
    require_admin(current)
    return current


def _request_identifier(value: uuid.UUID | str) -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise PasswordResetRequestUnavailable from exc


@transaction.atomic
def request_password_reset(identifier: str) -> PasswordResetSubmission:
    """Create or reuse OPEN work only for a known, active account.

    The user row serializes concurrent public submissions for that account.
    The existing OPEN-row lookup remains non-locking so it cannot invert the
    account-service lock order during a concurrent resolve/reject operation.
    """

    normalized = PortalUserManager.normalize_login(identifier or "")
    if not normalized or len(normalized) > 150:
        return PasswordResetSubmission(SubmissionDisposition.IGNORED)

    requester = User.objects.select_for_update().filter(username=normalized).first()
    if requester is None or not requester.is_active:
        return PasswordResetSubmission(SubmissionDisposition.IGNORED)

    existing_open = (
        PasswordResetRequest.objects.filter(
            requester_id=requester.pk,
            status=PasswordResetRequest.Status.OPEN,
        )
        .order_by("created_at", "id")
        .first()
    )
    if existing_open is not None:
        return PasswordResetSubmission(SubmissionDisposition.REUSED)

    PasswordResetRequest.objects.create(requester=requester)
    return PasswordResetSubmission(SubmissionDisposition.CREATED)


def list_password_reset_requests(
    *, actor: User, filters: PasswordResetRequestFilters
) -> QuerySet[PasswordResetRequest]:
    _current_admin(actor)
    if filters.status and filters.status not in PasswordResetRequest.Status.values:
        raise ValidationError("Choose an approved request status.")
    if len(filters.query) > 150:
        raise ValidationError("The search value exceeds the allowed length.")

    requests = PasswordResetRequest.objects.select_related("requester", "resolver").only(
        "id",
        "status",
        "created_at",
        "resolved_at",
        "requester__id",
        "requester__username",
        "requester__role",
        "requester__is_active",
        "resolver__id",
        "resolver__username",
    ).order_by("created_at", "id")
    if filters.status:
        requests = requests.filter(status=filters.status)
    if filters.query:
        requests = requests.filter(requester__username__icontains=filters.query)
    return requests


def get_password_reset_request(
    *, actor: User, request_id: uuid.UUID | str
) -> PasswordResetRequest:
    _current_admin(actor)
    try:
        normalized_id = _request_identifier(request_id)
        return (
            PasswordResetRequest.objects.select_related("requester", "resolver")
            .only(
                "id",
                "status",
                "created_at",
                "resolved_at",
                "requester__id",
                "requester__username",
                "requester__role",
                "requester__is_active",
                "resolver__id",
                "resolver__username",
            )
            .get(pk=normalized_id)
        )
    except (PasswordResetRequest.DoesNotExist, ValueError, TypeError) as exc:
        raise PasswordResetRequestUnavailable from exc


def _locked_request(request_id: uuid.UUID | str) -> PasswordResetRequest:
    try:
        normalized_id = _request_identifier(request_id)
        # Lock only the work item here. set_user_password owns the account
        # advisory-lock -> User-row lock order inside this same transaction.
        return PasswordResetRequest.objects.select_for_update().get(pk=normalized_id)
    except (PasswordResetRequest.DoesNotExist, ValueError, TypeError) as exc:
        raise PasswordResetRequestUnavailable from exc


@transaction.atomic
def resolve_password_reset_request(
    *, actor: User, request_id: uuid.UUID | str, new_password: str
) -> PasswordResetMutation:
    admin = _current_admin(actor)
    reset_request = _locked_request(request_id)
    if reset_request.status != PasswordResetRequest.Status.OPEN:
        raise PasswordResetRequestConflict

    requester_id = reset_request.requester_id
    # This is the Phase 12.4 account operation: it validates with Django,
    # hashes through set_password(), and revokes all target sessions.
    set_user_password(actor=admin, target=requester_id, new_password=new_password)

    reset_request.status = PasswordResetRequest.Status.RESOLVED
    reset_request.resolver = admin
    reset_request.resolved_at = timezone.now()
    reset_request.save(update_fields=("status", "resolver", "resolved_at"))
    return PasswordResetMutation(
        request=reset_request,
        acting_admin_was_requester=requester_id == admin.pk,
    )


@transaction.atomic
def reject_password_reset_request(
    *, actor: User, request_id: uuid.UUID | str
) -> PasswordResetMutation:
    admin = _current_admin(actor)
    reset_request = _locked_request(request_id)
    if reset_request.status != PasswordResetRequest.Status.OPEN:
        raise PasswordResetRequestConflict

    reset_request.status = PasswordResetRequest.Status.REJECTED
    reset_request.resolver = admin
    reset_request.resolved_at = timezone.now()
    reset_request.save(update_fields=("status", "resolver", "resolved_at"))
    return PasswordResetMutation(
        request=reset_request,
        acting_admin_was_requester=reset_request.requester_id == admin.pk,
    )
