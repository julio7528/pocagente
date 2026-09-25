from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.web_portal.conversations.models import Conversation


class SupportHandoff(models.Model):
    class Status(models.TextChoices):
        WAITING = "WAITING", "Waiting"
        ASSIGNED = "ASSIGNED", "Assigned"
        RESOLVED = "RESOLVED", "Resolved"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.OneToOneField(
        Conversation,
        on_delete=models.PROTECT,
        related_name="support_handoff",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.WAITING)
    requested_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    assigned_support_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_support_handoffs",
        null=True,
        blank=True,
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="resolved_support_handoffs",
        null=True,
        blank=True,
    )
    correlation_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "support_handoffs"
        indexes = [
            models.Index(fields=("status", "requested_at"), name="idx_portal_handoffs_queue"),
            models.Index(
                fields=("assigned_support_user", "status", "requested_at"),
                name="idx_portal_handoffs_assigned",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=("WAITING", "ASSIGNED", "RESOLVED", "CANCELLED")),
                name="ck_portal_handoffs__status_allowed",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="WAITING",
                        accepted_at__isnull=True,
                        resolved_at__isnull=True,
                        assigned_support_user__isnull=True,
                        resolved_by__isnull=True,
                    )
                    | Q(
                        status="ASSIGNED",
                        accepted_at__isnull=False,
                        resolved_at__isnull=True,
                        assigned_support_user__isnull=False,
                        resolved_by__isnull=True,
                    )
                    | Q(
                        status="RESOLVED",
                        accepted_at__isnull=False,
                        resolved_at__isnull=False,
                        assigned_support_user__isnull=False,
                        resolved_by__isnull=False,
                    )
                    | Q(status="CANCELLED", resolved_at__isnull=False)
                ),
                name="ck_portal_handoffs__lifecycle_consistent",
            ),
        ]


class PasswordResetRequest(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        RESOLVED = "RESOLVED", "Resolved"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="password_reset_requests",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="resolved_password_reset_requests",
        null=True,
        blank=True,
    )
    admin_note = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        db_table = "password_reset_requests"
        indexes = [
            models.Index(
                fields=("status", "created_at"),
                name="idx_portal_reset_status",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=("OPEN", "RESOLVED", "REJECTED")),
                name="ck_portal_reset_requests__status_allowed",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="OPEN", resolved_at__isnull=True, resolver__isnull=True)
                    | Q(
                        status__in=("RESOLVED", "REJECTED"),
                        resolved_at__isnull=False,
                        resolver__isnull=False,
                    )
                ),
                name="ck_portal_reset_requests__resolution_consistent",
            ),
        ]
