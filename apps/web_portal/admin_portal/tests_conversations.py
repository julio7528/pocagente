from __future__ import annotations

import uuid

from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.web_portal.accounts.models import User
from apps.web_portal.admin_portal.conversation_services import (
    AdminConversationConflict,
    ConversationAdminFilters,
    block_conversation,
    get_admin_conversation,
    get_admin_history,
    list_admin_conversations,
    soft_delete_conversation,
    unblock_conversation,
)
from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.support.models import SupportHandoff


PASSWORD = "Test-only-Conversation-Admin-981!"


@override_settings(PASSWORD_HASHERS=("django.contrib.auth.hashers.MD5PasswordHasher",))
class AdminConversationServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="conv.admin", password=PASSWORD, role=User.Role.ADMIN
        )
        self.client_user = User.objects.create_user(
            username="conv.client", password=PASSWORD, role=User.Role.CLIENT
        )
        self.other_client = User.objects.create_user(
            username="other.client", password=PASSWORD, role=User.Role.CLIENT
        )
        self.support = User.objects.create_user(
            username="conv.support", password=PASSWORD, role=User.Role.SUPPORT_AGENT
        )

    def conversation(self, title, *, owner=None, status=Conversation.Status.ACTIVE, **kwargs):
        created_at = kwargs.pop("created_at", None)
        conversation = Conversation.objects.create(
            owner=owner or self.client_user, title=title, status=status, **kwargs
        )
        if created_at is not None:
            Conversation.objects.filter(pk=conversation.pk).update(created_at=created_at)
            conversation.created_at = created_at
        return conversation

    def handoff(self, conversation, status, *, assigned=None):
        values = {"conversation": conversation, "status": status}
        if status in (SupportHandoff.Status.ASSIGNED, SupportHandoff.Status.RESOLVED):
            values["assigned_support_user"] = assigned or self.support
            values["accepted_at"] = timezone.now()
        if status == SupportHandoff.Status.RESOLVED:
            values["resolved_at"] = timezone.now()
            values["resolved_by"] = assigned or self.support
        if status == SupportHandoff.Status.CANCELLED:
            values["resolved_at"] = timezone.now()
        return SupportHandoff.objects.create(**values)

    def test_admin_list_search_owner_status_combined_and_dates(self):
        old = self.conversation("Older invoice", created_at=timezone.now() - timedelta(days=4))
        match = self.conversation("Invoice review", created_at=timezone.now() - timedelta(days=1))
        waiting = self.conversation(
            "Invoice waiting", status=Conversation.Status.WAITING_HUMAN
        )
        self.handoff(waiting, SupportHandoff.Status.WAITING)
        other = self.conversation("Different", owner=self.other_client)

        filters = ConversationAdminFilters(
            query="Invoice", owner_username="conv.client",
            status=Conversation.Status.ACTIVE,
            date_from=timezone.localdate() - timedelta(days=2),
            date_to=timezone.localdate(),
        )
        rows = list(list_admin_conversations(actor=self.admin, filters=filters))
        self.assertEqual([row.pk for row in rows], [match.pk])
        self.assertNotIn(old.pk, [row.pk for row in rows])
        self.assertNotIn(waiting.pk, [row.pk for row in rows])
        self.assertNotIn(other.pk, [row.pk for row in rows])

    def test_list_includes_deleted_tombstones_and_stable_updated_at_id_order(self):
        first = self.conversation("One")
        second = self.conversation("Two")
        same_time = timezone.now()
        Conversation.objects.filter(pk__in=(first.pk, second.pk)).update(updated_at=same_time)
        deleted = self.conversation(
            "Retained", status=Conversation.Status.DELETED,
            deleted_at=timezone.now(), deleted_by=self.admin,
        )
        rows = list(list_admin_conversations(
            actor=self.admin, filters=ConversationAdminFilters(status=Conversation.Status.DELETED)
        ))
        self.assertEqual([row.pk for row in rows], [deleted.pk])
        all_rows = list(list_admin_conversations(
            actor=self.admin, filters=ConversationAdminFilters()
        ))
        visible_pair = [row.pk for row in all_rows if row.pk in {first.pk, second.pk}]
        self.assertEqual(visible_pair, sorted((first.pk, second.pk), key=str, reverse=True))

    def test_filter_validation_rejects_invalid_unbounded_and_overlong_values(self):
        for filters in (
            ConversationAdminFilters(status="ROOT"),
            ConversationAdminFilters(date_from=date(2026, 1, 1)),
            ConversationAdminFilters(date_from=date(2025, 1, 1), date_to=date(2026, 1, 2)),
            ConversationAdminFilters(query="x" * 101),
            ConversationAdminFilters(date_from=date(2026, 2, 2), date_to=date(2026, 2, 1)),
        ):
            with self.subTest(filters=filters), self.assertRaises(ValidationError):
                list_admin_conversations(actor=self.admin, filters=filters)

    def test_date_range_includes_local_start_and_end_days_without_boundary_leak(self):
        selected = date(2026, 1, 1)
        start = timezone.make_aware(
            datetime.combine(selected, time.min), timezone.get_current_timezone()
        )
        before = self.conversation("Before start")
        at_start = self.conversation("At start")
        at_end = self.conversation("At end")
        after = self.conversation("After end")
        for conversation, created_at in (
            (before, start - timedelta(microseconds=1)),
            (at_start, start),
            (at_end, start + timedelta(days=1) - timedelta(microseconds=1)),
            (after, start + timedelta(days=1)),
        ):
            Conversation.objects.filter(pk=conversation.pk).update(created_at=created_at)
        filters = ConversationAdminFilters(date_from=selected, date_to=selected)
        found = {row.pk for row in list_admin_conversations(actor=self.admin, filters=filters)}
        self.assertEqual(found, {at_start.pk, at_end.pk})

    def test_only_database_current_active_admin_can_use_service(self):
        client = User.objects.create_user(
            username="not.admin", password=PASSWORD, role=User.Role.CLIENT
        )
        with self.assertRaises(PermissionDenied):
            list_admin_conversations(actor=client, filters=ConversationAdminFilters())
        stale_admin = User.objects.get(pk=self.admin.pk)
        User.objects.filter(pk=self.admin.pk).update(role=User.Role.CLIENT)
        with self.assertRaises(PermissionDenied):
            block_conversation(actor=stale_admin, conversation_id=self.conversation("No access").pk)

    def test_active_block_and_unblock_preserve_same_conversation_and_history(self):
        conversation = self.conversation("Active case")
        message = Message.objects.create(
            conversation=conversation, sender_type=Message.SenderType.CLIENT,
            sender_user=self.client_user, body="Keep this history.",
            idempotency_key=uuid.uuid4(),
        )
        blocked = block_conversation(actor=self.admin, conversation_id=conversation.pk)
        self.assertEqual(blocked.status, Conversation.Status.BLOCKED)
        self.assertEqual(blocked.status_before_block, Conversation.Status.ACTIVE)
        restored = unblock_conversation(actor=self.admin, conversation_id=conversation.pk)
        self.assertEqual(restored.status, Conversation.Status.ACTIVE)
        self.assertIsNone(restored.status_before_block)
        self.assertEqual(Message.objects.get(pk=message.pk).body, "Keep this history.")

    def test_waiting_human_block_unblock_preserves_waiting_handoff(self):
        conversation = self.conversation("Waiting", status=Conversation.Status.WAITING_HUMAN)
        handoff = self.handoff(conversation, SupportHandoff.Status.WAITING)
        block_conversation(actor=self.admin, conversation_id=conversation.pk)
        handoff.refresh_from_db()
        self.assertEqual(handoff.status, SupportHandoff.Status.WAITING)
        restored = unblock_conversation(actor=self.admin, conversation_id=conversation.pk)
        handoff.refresh_from_db()
        self.assertEqual(restored.status, Conversation.Status.WAITING_HUMAN)
        self.assertEqual(handoff.status, SupportHandoff.Status.WAITING)
        self.assertIsNone(handoff.assigned_support_user_id)

    def test_human_block_unblock_preserves_exact_support_assignment(self):
        conversation = self.conversation("Human", status=Conversation.Status.HUMAN)
        handoff = self.handoff(conversation, SupportHandoff.Status.ASSIGNED, assigned=self.support)
        block_conversation(actor=self.admin, conversation_id=conversation.pk)
        handoff.refresh_from_db()
        self.assertEqual(handoff.status, SupportHandoff.Status.ASSIGNED)
        self.assertEqual(handoff.assigned_support_user_id, self.support.pk)
        restored = unblock_conversation(actor=self.admin, conversation_id=conversation.pk)
        handoff.refresh_from_db()
        self.assertEqual(restored.status, Conversation.Status.HUMAN)
        self.assertEqual(handoff.assigned_support_user_id, self.support.pk)

    def test_block_unblock_reject_closed_deleted_and_invalid_saved_state(self):
        closed = self.conversation("Closed", status=Conversation.Status.CLOSED)
        with self.assertRaises(AdminConversationConflict):
            block_conversation(actor=self.admin, conversation_id=closed.pk)
        blocked = self.conversation(
            "Blocked", status=Conversation.Status.BLOCKED,
            status_before_block=Conversation.Status.ACTIVE,
        )
        blocked.status_before_block = Conversation.Status.CLOSED
        with patch(
            "apps.web_portal.admin_portal.conversation_services._locked_conversation",
            return_value=blocked,
        ), self.assertRaises(AdminConversationConflict):
            unblock_conversation(actor=self.admin, conversation_id=blocked.pk)
        with self.assertRaises(AdminConversationConflict):
            unblock_conversation(actor=self.admin, conversation_id=closed.pk)

    def test_human_restore_rejects_inactive_or_changed_assignee_without_fallback(self):
        conversation = self.conversation(
            "Blocked human", status=Conversation.Status.BLOCKED,
            status_before_block=Conversation.Status.HUMAN,
        )
        handoff = self.handoff(
            conversation, SupportHandoff.Status.ASSIGNED, assigned=self.support
        )
        User.objects.filter(pk=self.support.pk).update(is_active=False)
        with self.assertRaises(AdminConversationConflict):
            unblock_conversation(actor=self.admin, conversation_id=conversation.pk)
        conversation.refresh_from_db()
        handoff.refresh_from_db()
        self.assertEqual(conversation.status, Conversation.Status.BLOCKED)
        self.assertEqual(conversation.status_before_block, Conversation.Status.HUMAN)
        self.assertEqual(handoff.assigned_support_user_id, self.support.pk)
        self.assertEqual(handoff.status, SupportHandoff.Status.ASSIGNED)

    def test_soft_delete_retains_conversation_messages_and_resolved_handoff(self):
        conversation = self.conversation("Retain this")
        message = Message.objects.create(
            conversation=conversation, sender_type=Message.SenderType.CLIENT,
            sender_user=self.client_user, body="History is retained.",
            idempotency_key=uuid.uuid4(),
        )
        closed = self.conversation("Finalized", status=Conversation.Status.CLOSED)
        handoff = self.handoff(closed, SupportHandoff.Status.RESOLVED)
        deleted = soft_delete_conversation(actor=self.admin, conversation_id=closed.pk)
        self.assertEqual(deleted.status, Conversation.Status.DELETED)
        self.assertIsNotNone(deleted.deleted_at)
        self.assertEqual(deleted.deleted_by_id, self.admin.pk)
        self.assertTrue(Conversation.objects.filter(pk=closed.pk).exists())
        self.assertTrue(SupportHandoff.objects.filter(pk=handoff.pk).exists())
        self.assertEqual(Message.objects.get(pk=message.pk).body, "History is retained.")

    def test_soft_delete_rejects_waiting_assigned_and_blocked_active_handoff(self):
        waiting = self.conversation("Waiting", status=Conversation.Status.WAITING_HUMAN)
        self.handoff(waiting, SupportHandoff.Status.WAITING)
        human = self.conversation("Human", status=Conversation.Status.HUMAN)
        self.handoff(human, SupportHandoff.Status.ASSIGNED)
        blocked_human = self.conversation(
            "Blocked human", status=Conversation.Status.BLOCKED,
            status_before_block=Conversation.Status.HUMAN,
        )
        self.handoff(blocked_human, SupportHandoff.Status.ASSIGNED)
        for conversation in (waiting, human, blocked_human):
            with self.subTest(conversation=conversation.title), self.assertRaises(AdminConversationConflict):
                soft_delete_conversation(actor=self.admin, conversation_id=conversation.pk)
            conversation.refresh_from_db()
            self.assertNotEqual(conversation.status, Conversation.Status.DELETED)

    def test_history_reads_every_sender_in_stable_chronological_order(self):
        conversation = self.conversation("Transcript")
        created = timezone.now()
        messages = [
            Message.objects.create(
                conversation=conversation, sender_type=sender, sender_user=user,
                body=body, idempotency_key=key,
            )
            for sender, user, body, key in (
                (Message.SenderType.CLIENT, self.client_user, "client", uuid.uuid4()),
                (Message.SenderType.AGENT, None, "agent", None),
                (Message.SenderType.SYSTEM, None, "system", None),
                (Message.SenderType.SUPPORT_AGENT, self.support, "support", None),
            )
        ]
        Message.objects.filter(pk__in=[item.pk for item in messages]).update(created_at=created)
        detail = get_admin_conversation(actor=self.admin, conversation_id=conversation.pk)
        history = list(get_admin_history(actor=self.admin, conversation=detail))
        self.assertEqual([item.pk for item in history], sorted([item.pk for item in messages], key=str))

    def test_soft_delete_records_actor_and_retains_zero_or_more_messages(self):
        conversation = self.conversation("No active handoff")
        soft_delete_conversation(actor=self.admin, conversation_id=conversation.pk)
        conversation.refresh_from_db()
        self.assertEqual(conversation.status, Conversation.Status.DELETED)
        self.assertEqual(conversation.deleted_by_id, self.admin.pk)


__all__ = ["AdminConversationServiceTests"]
