from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


CONVERSATION_STATUSES = (
    "ACTIVE",
    "WAITING_HUMAN",
    "HUMAN",
    "CLOSED",
    "BLOCKED",
    "DELETED",
)


class ImmutableMessageQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "body" in kwargs:
            raise ValidationError("Historical message bodies are immutable.")
        return super().update(**kwargs)

    def delete(self):
        raise ValidationError("Historical messages cannot be physically deleted.")


class ImmutableMessageManager(models.Manager.from_queryset(ImmutableMessageQuerySet)):
    pass


class Conversation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        WAITING_HUMAN = "WAITING_HUMAN", "Waiting for human support"
        HUMAN = "HUMAN", "Human support"
        CLOSED = "CLOSED", "Closed"
        BLOCKED = "BLOCKED", "Blocked"
        DELETED = "DELETED", "Deleted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="conversations",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    status_before_block = models.CharField(max_length=20, null=True, blank=True)
    title = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="deleted_conversations",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "conversations"
        ordering = ("-updated_at", "id")
        indexes = [
            models.Index(
                fields=("owner", "status", "-updated_at"),
                name="idx_portal_conv_owner_status",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=CONVERSATION_STATUSES),
                name="ck_portal_conversations__status_allowed",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="BLOCKED",
                        status_before_block__isnull=False,
                        status_before_block__in=("ACTIVE", "WAITING_HUMAN", "HUMAN"),
                    )
                    | (~Q(status="BLOCKED") & Q(status_before_block__isnull=True))
                ),
                name="ck_portal_conversations__block_state_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="DELETED", deleted_at__isnull=False, deleted_by__isnull=False)
                    | (~Q(status="DELETED") & Q(deleted_at__isnull=True, deleted_by__isnull=True))
                ),
                name="ck_portal_conversations__deletion_consistent",
            ),
            models.CheckConstraint(
                condition=~Q(title=""),
                name="ck_portal_conversations__title_nonblank",
            ),
        ]


class Message(models.Model):
    class SenderType(models.TextChoices):
        CLIENT = "CLIENT", "Client"
        AGENT = "AGENT", "Agent"
        SUPPORT_AGENT = "SUPPORT_AGENT", "Support agent"
        SYSTEM = "SYSTEM", "System"

    class ProcessingStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.PROTECT,
        related_name="messages",
    )
    sender_type = models.CharField(max_length=20, choices=SenderType.choices)
    sender_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sent_portal_messages",
        null=True,
        blank=True,
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    idempotency_key = models.UUIDField(null=True, blank=True)
    processing_status = models.CharField(
        max_length=12,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.COMPLETED,
    )
    objects = ImmutableMessageManager()

    class Meta:
        db_table = "messages"
        ordering = ("created_at", "id")
        indexes = [
            models.Index(
                fields=("conversation", "created_at", "id"),
                name="idx_portal_messages_conv_order",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(sender_type__in=("CLIENT", "AGENT", "SUPPORT_AGENT", "SYSTEM")),
                name="ck_portal_messages__sender_allowed",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        sender_type="CLIENT",
                        sender_user__isnull=False,
                        idempotency_key__isnull=False,
                    )
                    | Q(
                        sender_type="SUPPORT_AGENT",
                        sender_user__isnull=False,
                        idempotency_key__isnull=True,
                    )
                    | Q(
                        sender_type__in=("AGENT", "SYSTEM"),
                        sender_user__isnull=True,
                        idempotency_key__isnull=True,
                    )
                ),
                name="ck_portal_messages__sender_fields_consistent",
            ),
            models.CheckConstraint(
                condition=Q(processing_status__in=("PENDING", "COMPLETED", "FAILED")),
                name="ck_portal_messages__processing_status_allowed",
            ),
            models.CheckConstraint(
                condition=~Q(body=""),
                name="ck_portal_messages__body_nonblank",
            ),
            models.UniqueConstraint(
                fields=("conversation", "idempotency_key"),
                condition=Q(sender_type="CLIENT", idempotency_key__isnull=False),
                name="uq_portal_messages__client_turn_idempotency",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            previous_body = (
                type(self).objects.using(kwargs.get("using") or self._state.db)
                .filter(pk=self.pk)
                .values_list("body", flat=True)
                .first()
            )
            if previous_body is not None and previous_body != self.body:
                raise ValidationError("Historical message bodies are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Historical messages cannot be physically deleted.")
