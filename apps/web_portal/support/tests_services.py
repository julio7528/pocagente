from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.conversations.services import (
    ConversationNotWritableError,
    IdempotencyConflictError,
    append_client_message,
)
from apps.web_portal.integrations.human_escalation import (
    HumanTransitionConflict,
    TransitionResult,
)
from apps.web_portal.support.models import SupportHandoff
from apps.web_portal.support.services import (
    SupportConversationUnavailable,
    SupportOperationConflict,
    append_assigned_support_message,
    assigned_handoffs,
    claim_handoff,
    finalize_handoff,
    finalized_handoffs,
    get_support_conversation,
    request_human_support,
    waiting_handoffs,
)


PASSWORD = "Phase12SupportTest!7"


def _transition_result(action: str, actor: User, conversation: Conversation) -> TransitionResult:
    state = {"CONFIRM": "WAITING_HUMAN", "ACCEPT": "HUMAN", "RESOLVE": "RESOLVED"}[action]
    return TransitionResult(
        action=action,
        state=state,
        status="TRANSITIONED",
        conversation_id=str(conversation.pk),
        assigned_operator_id=str(actor.pk) if action == "ACCEPT" else None,
        automation_suspended=action == "ACCEPT",
    )


class SupportLifecycleServiceTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username="support.flow.client", password=PASSWORD, role=User.Role.CLIENT
        )
        self.agent_a = User.objects.create_user(
            username="support.flow.a", password=PASSWORD, role=User.Role.SUPPORT_AGENT
        )
        self.agent_b = User.objects.create_user(
            username="support.flow.b", password=PASSWORD, role=User.Role.SUPPORT_AGENT
        )
        self.admin = User.objects.create_user(
            username="support.flow.admin", password=PASSWORD, role=User.Role.ADMIN
        )
        self.conversation = Conversation.objects.create(
            owner=self.client_user,
            title="Protocolo POC-OPS-0004",
            status=Conversation.Status.ACTIVE,
        )
        self.first = Message.objects.create(
            conversation=self.conversation,
            sender_type=Message.SenderType.CLIENT,
            sender_user=self.client_user,
            idempotency_key=uuid.uuid4(),
            body="Como está o protocolo POC-OPS-0004?",
        )

    def test_client_must_explicitly_confirm_and_request_is_idempotent(self):
        with patch("apps.web_portal.support.services.transition_human_escalation") as transition:
            transition.side_effect = lambda **kwargs: _transition_result(
                kwargs["action"], kwargs["actor"], kwargs["conversation"]
            )
            with self.assertRaises(SupportOperationConflict):
                request_human_support(
                    actor=self.client_user,
                    conversation_id=self.conversation.pk,
                    explicit_confirmation=False,
                )
            first = request_human_support(
                actor=self.client_user,
                conversation_id=self.conversation.pk,
                explicit_confirmation=True,
            )
            replay = request_human_support(
                actor=self.client_user,
                conversation_id=self.conversation.pk,
                explicit_confirmation=True,
            )
        self.assertTrue(first.created)
        self.assertFalse(replay.created)
        self.assertEqual(first.conversation.pk, self.conversation.pk)
        self.assertEqual(first.conversation.status, Conversation.Status.WAITING_HUMAN)
        self.assertEqual(first.handoff.status, SupportHandoff.Status.WAITING)
        self.assertEqual(transition.call_count, 1)

    def test_complete_same_thread_waiting_human_closed_lifecycle(self):
        with patch("apps.web_portal.support.services.transition_human_escalation") as transition:
            transition.side_effect = lambda **kwargs: _transition_result(
                kwargs["action"], kwargs["actor"], kwargs["conversation"]
            )
            request_human_support(
                actor=self.client_user, conversation_id=self.conversation.pk, explicit_confirmation=True
            )
            waiting_followup = append_client_message(
                actor=self.client_user,
                conversation=self.conversation.pk,
                body="Ainda estou aguardando.",
                client_turn_key=uuid.uuid4(),
            )
            self.assertEqual(waiting_followup.message.conversation_id, self.conversation.pk)
            self.assertEqual(waiting_handoffs(actor=self.agent_a).count(), 1)
            waiting_detail = get_support_conversation(actor=self.agent_a, conversation_id=self.conversation.pk)
            self.assertEqual(
                list(waiting_detail.messages.order_by("created_at", "id").values_list("body", flat=True)),
                ["Como está o protocolo POC-OPS-0004?", "Ainda estou aguardando."],
            )

            claim = claim_handoff(actor=self.agent_a, conversation_id=self.conversation.pk)
            self.assertEqual(claim.conversation.pk, self.conversation.pk)
            self.assertEqual(claim.conversation.status, Conversation.Status.HUMAN)
            self.assertEqual(claim.handoff.assigned_support_user_id, self.agent_a.pk)
            self.assertEqual(assigned_handoffs(actor=self.agent_a).count(), 1)
            with self.assertRaises(SupportConversationUnavailable):
                get_support_conversation(actor=self.agent_b, conversation_id=self.conversation.pk)
            with self.assertRaises(SupportOperationConflict):
                claim_handoff(actor=self.agent_b, conversation_id=self.conversation.pk)

            support_key = uuid.uuid4()
            reply = append_assigned_support_message(
                actor=self.agent_a,
                conversation_id=self.conversation.pk,
                body="Olá, vou verificar seu caso.",
                support_turn_key=support_key,
            )
            replay = append_assigned_support_message(
                actor=self.agent_a,
                conversation_id=self.conversation.pk,
                body="Olá, vou verificar seu caso.",
                support_turn_key=support_key,
            )
            self.assertTrue(reply.created)
            self.assertFalse(replay.created)
            self.assertEqual(reply.message.pk, replay.message.pk)
            with self.assertRaises(IdempotencyConflictError):
                append_assigned_support_message(
                    actor=self.agent_a,
                    conversation_id=self.conversation.pk,
                    body="Conteúdo diferente.",
                    support_turn_key=support_key,
                )

            client_human_followup = append_client_message(
                actor=self.client_user,
                conversation=self.conversation.pk,
                body="Obrigado.",
                client_turn_key=uuid.uuid4(),
            )
            self.assertEqual(client_human_followup.message.conversation_id, self.conversation.pk)
            transcript = list(
                Message.objects.filter(conversation=self.conversation)
                .order_by("created_at", "id")
                .values_list("sender_type", "body")
            )
            self.assertEqual(len(transcript), 4)
            self.assertEqual(transcript[-2][1], "Olá, vou verificar seu caso.")
            self.assertEqual(transcript[-1][1], "Obrigado.")

            finished = finalize_handoff(actor=self.agent_a, conversation_id=self.conversation.pk)
            replayed_finish = finalize_handoff(actor=self.agent_a, conversation_id=self.conversation.pk)
            self.assertTrue(finished.created)
            self.assertFalse(replayed_finish.created)
            self.assertEqual(finished.conversation.status, Conversation.Status.CLOSED)
            self.assertEqual(finished.handoff.status, SupportHandoff.Status.RESOLVED)
            self.assertEqual(finished.handoff.resolved_by_id, self.agent_a.pk)
            self.assertEqual(finalized_handoffs(actor=self.agent_a).count(), 1)
            self.assertEqual(transition.call_count, 3)

        with self.assertRaises(ConversationNotWritableError):
            append_client_message(
                actor=self.client_user,
                conversation=self.conversation.pk,
                body="Depois de fechar.",
                client_turn_key=uuid.uuid4(),
            )
        with self.assertRaises(SupportConversationUnavailable):
            append_assigned_support_message(
                actor=self.agent_a,
                conversation_id=self.conversation.pk,
                body="Depois de fechar.",
                support_turn_key=uuid.uuid4(),
            )
        with self.assertRaises(SupportOperationConflict):
            request_human_support(
                actor=self.client_user, conversation_id=self.conversation.pk, explicit_confirmation=True
            )

    def test_failed_runtime_transition_does_not_commit_portal_state(self):
        with patch(
            "apps.web_portal.support.services.transition_human_escalation",
            side_effect=HumanTransitionConflict("safe conflict"),
        ):
            with self.assertRaises(SupportOperationConflict):
                request_human_support(
                    actor=self.client_user,
                    conversation_id=self.conversation.pk,
                    explicit_confirmation=True,
                )
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.status, Conversation.Status.ACTIVE)
        self.assertFalse(SupportHandoff.objects.filter(conversation=self.conversation).exists())

    def test_blocked_and_wrong_roles_fail_closed(self):
        with self.assertRaises(PermissionDenied):
            request_human_support(
                actor=self.agent_a, conversation_id=self.conversation.pk, explicit_confirmation=True
            )
        with patch("apps.web_portal.support.services.transition_human_escalation") as transition:
            transition.side_effect = lambda **kwargs: _transition_result(
                kwargs["action"], kwargs["actor"], kwargs["conversation"]
            )
            request_human_support(
                actor=self.client_user, conversation_id=self.conversation.pk, explicit_confirmation=True
            )
            self.conversation.status = Conversation.Status.BLOCKED
            self.conversation.status_before_block = Conversation.Status.WAITING_HUMAN
            self.conversation.save(update_fields={"status", "status_before_block", "updated_at"})
            with self.assertRaises(SupportOperationConflict):
                claim_handoff(actor=self.agent_a, conversation_id=self.conversation.pk)

    def test_admin_block_suspension_freezes_assigned_support_writes(self):
        with patch("apps.web_portal.support.services.transition_human_escalation") as transition:
            transition.side_effect = lambda **kwargs: _transition_result(
                kwargs["action"], kwargs["actor"], kwargs["conversation"]
            )
            request_human_support(
                actor=self.client_user, conversation_id=self.conversation.pk, explicit_confirmation=True
            )
            claim_handoff(actor=self.agent_a, conversation_id=self.conversation.pk)
            self.conversation.refresh_from_db()
            self.conversation.status = Conversation.Status.BLOCKED
            self.conversation.status_before_block = Conversation.Status.HUMAN
            self.conversation.save(update_fields={"status", "status_before_block", "updated_at"})
            with self.assertRaises(SupportConversationUnavailable):
                append_assigned_support_message(
                    actor=self.agent_a,
                    conversation_id=self.conversation.pk,
                    body="Suspenso.",
                    support_turn_key=uuid.uuid4(),
                )


class ConcurrentSupportClaimTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client_user = User.objects.create_user(
            username="support.race.client", password=PASSWORD, role=User.Role.CLIENT
        )
        self.agent_a = User.objects.create_user(
            username="support.race.a", password=PASSWORD, role=User.Role.SUPPORT_AGENT
        )
        self.agent_b = User.objects.create_user(
            username="support.race.b", password=PASSWORD, role=User.Role.SUPPORT_AGENT
        )
        self.conversation = Conversation.objects.create(
            owner=self.client_user,
            title="Claim race",
            status=Conversation.Status.WAITING_HUMAN,
        )
        self.handoff = SupportHandoff.objects.create(conversation=self.conversation)

    def test_postgres_row_lock_allows_exactly_one_concurrent_claim(self):
        barrier = threading.Barrier(2)

        def claim(agent_id):
            close_old_connections()
            agent = User.objects.get(pk=agent_id)
            barrier.wait(timeout=10)
            try:
                claim_handoff(actor=agent, conversation_id=self.conversation.pk)
                return "winner"
            except SupportOperationConflict:
                return "conflict"
            finally:
                close_old_connections()

        def transition(**kwargs):
            return _transition_result(kwargs["action"], kwargs["actor"], kwargs["conversation"])

        with patch("apps.web_portal.support.services.transition_human_escalation", side_effect=transition):
            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(claim, (self.agent_a.pk, self.agent_b.pk)))

        self.assertCountEqual(outcomes, ["winner", "conflict"])
        self.conversation.refresh_from_db()
        self.handoff.refresh_from_db()
        self.assertEqual(self.conversation.status, Conversation.Status.HUMAN)
        self.assertEqual(self.handoff.status, SupportHandoff.Status.ASSIGNED)
        self.assertIn(self.handoff.assigned_support_user_id, {self.agent_a.pk, self.agent_b.pk})
        self.assertEqual(SupportHandoff.objects.filter(conversation=self.conversation).count(), 1)
