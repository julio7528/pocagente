from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

from django.db import close_old_connections, connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.web_portal.accounts.models import User
from apps.web_portal.admin_portal.conversation_services import (
    AdminConversationConflict,
    block_conversation,
)
from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.conversations.services import (
    ConversationNotWritableError,
    append_client_message,
)
from apps.web_portal.support.models import SupportHandoff
from apps.web_portal.support.services import (
    SupportConversationUnavailable,
    SupportOperationConflict,
    append_assigned_support_message,
    finalize_handoff,
)


PASSWORD = "Race-test-Conversation-552!"


@override_settings(PASSWORD_HASHERS=("django.contrib.auth.hashers.MD5PasswordHasher",))
class AdminConversationConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.admin = User.objects.create_user(
            username="race.admin", password=PASSWORD, role=User.Role.ADMIN
        )
        self.client_user = User.objects.create_user(
            username="race.client", password=PASSWORD, role=User.Role.CLIENT
        )
        self.support = User.objects.create_user(
            username="race.support", password=PASSWORD, role=User.Role.SUPPORT_AGENT
        )

    def conversation(self, status=Conversation.Status.ACTIVE):
        return Conversation.objects.create(
            owner=self.client_user, title="Serialized lifecycle", status=status
        )

    def assigned_handoff(self, conversation):
        return SupportHandoff.objects.create(
            conversation=conversation,
            status=SupportHandoff.Status.ASSIGNED,
            assigned_support_user=self.support,
            accepted_at=timezone.now(),
        )

    def race(self, first, second):
        barrier = threading.Barrier(2)

        def invoke(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                operation()
                return "success"
            except Exception as exc:
                return type(exc)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = (pool.submit(invoke, first), pool.submit(invoke, second))
            return tuple(future.result(timeout=15) for future in futures)

    def test_admin_block_races_client_write_without_a_write_after_block(self):
        conversation = self.conversation()

        def block():
            block_conversation(actor=self.admin, conversation_id=conversation.pk)

        def client_write():
            append_client_message(
                actor=self.client_user,
                conversation=conversation.pk,
                body="Race client turn",
                client_turn_key=uuid.uuid4(),
            )

        outcomes = self.race(block, client_write)
        self.assertIn("success", outcomes)
        self.assertIn(
            outcomes[0] if outcomes[1] == "success" else outcomes[1],
            {"success", ConversationNotWritableError},
        )
        conversation.refresh_from_db()
        self.assertEqual(conversation.status, Conversation.Status.BLOCKED)
        self.assertEqual(conversation.status_before_block, Conversation.Status.ACTIVE)
        messages = list(Message.objects.filter(conversation=conversation))
        self.assertLessEqual(len(messages), 1)
        if messages:
            self.assertLessEqual(messages[0].created_at, conversation.updated_at)

    def test_admin_block_races_assigned_support_write_without_orphaning(self):
        conversation = self.conversation(Conversation.Status.HUMAN)
        handoff = self.assigned_handoff(conversation)

        def block():
            block_conversation(actor=self.admin, conversation_id=conversation.pk)

        def support_write():
            append_assigned_support_message(
                actor=self.support,
                conversation_id=conversation.pk,
                body="Race support reply",
                support_turn_key=uuid.uuid4(),
            )

        outcomes = self.race(block, support_write)
        self.assertIn("success", outcomes)
        other = outcomes[0] if outcomes[1] == "success" else outcomes[1]
        self.assertIn(other, {"success", SupportConversationUnavailable})
        conversation.refresh_from_db()
        handoff.refresh_from_db()
        self.assertEqual(conversation.status, Conversation.Status.BLOCKED)
        self.assertEqual(conversation.status_before_block, Conversation.Status.HUMAN)
        self.assertEqual(handoff.status, SupportHandoff.Status.ASSIGNED)
        self.assertEqual(handoff.assigned_support_user_id, self.support.pk)
        messages = list(Message.objects.filter(conversation=conversation))
        self.assertLessEqual(len(messages), 1)
        if messages:
            self.assertEqual(messages[0].sender_type, Message.SenderType.SUPPORT_AGENT)
            self.assertLessEqual(messages[0].created_at, conversation.updated_at)

    def test_admin_block_races_finalization_in_one_serializable_valid_outcome(self):
        conversation = self.conversation(Conversation.Status.HUMAN)
        handoff = self.assigned_handoff(conversation)
        finalize_entered = threading.Event()

        def runtime_resolution(**_kwargs):
            finalize_entered.set()
            time.sleep(0.05)
            return SimpleNamespace(
                state="RESOLVED",
                assigned_operator_id=None,
                automation_suspended=False,
            )

        def block():
            block_conversation(actor=self.admin, conversation_id=conversation.pk)

        def finalize():
            finalize_handoff(actor=self.support, conversation_id=conversation.pk)

        with patch(
            "apps.web_portal.support.services.transition_human_escalation",
            side_effect=runtime_resolution,
        ):
            outcomes = self.race(block, finalize)

        conversation.refresh_from_db()
        handoff.refresh_from_db()
        if conversation.status == Conversation.Status.CLOSED:
            self.assertEqual(conversation.status_before_block, None)
            self.assertEqual(handoff.status, SupportHandoff.Status.RESOLVED)
            self.assertIn("success", outcomes)
            self.assertIn(AdminConversationConflict, outcomes)
        else:
            self.assertEqual(conversation.status, Conversation.Status.BLOCKED)
            self.assertEqual(conversation.status_before_block, Conversation.Status.HUMAN)
            self.assertEqual(handoff.status, SupportHandoff.Status.ASSIGNED)
            self.assertEqual(handoff.assigned_support_user_id, self.support.pk)
            self.assertIn("success", outcomes)
            self.assertTrue(
                any(result in (SupportOperationConflict, SupportConversationUnavailable) for result in outcomes)
            )
