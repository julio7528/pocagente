from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.context import (
    MAX_CONTEXT_CHARACTERS,
    MAX_PRIOR_MESSAGES,
    ContextRole,
    build_agent_context,
)
from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.conversations.services import (
    ConversationNotWritableError,
    IdempotencyConflictError,
    append_agent_message,
    append_client_message,
    append_support_message,
    append_system_message,
    create_conversation,
    get_conversation_history,
    get_owned_conversation,
    list_owned_conversations,
    mark_client_turn_failed,
)
from apps.web_portal.support.models import SupportHandoff


PASSWORD = "synthetic-phase12-password"


class ConversationServiceTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username="phase126-client", password=PASSWORD, role=User.Role.CLIENT
        )
        self.other_client = User.objects.create_user(
            username="phase126-other", password=PASSWORD, role=User.Role.CLIENT
        )
        self.support_user = User.objects.create_user(
            username="phase126-support", password=PASSWORD, role=User.Role.SUPPORT_AGENT
        )
        self.admin_user = User.objects.create_user(
            username="phase126-admin", password=PASSWORD, role=User.Role.ADMIN
        )

    def create_thread(self, body="Primeira mensagem", key=None):
        return create_conversation(
            owner=self.client_user,
            first_message=body,
            client_turn_key=key or uuid.uuid4(),
        )

    def test_create_conversation_is_active_owned_uuid_and_atomic(self):
        created = self.create_thread("  Como   funciona\no Link?  ")
        self.assertIsInstance(created.conversation.id, uuid.UUID)
        self.assertEqual(created.conversation.status, Conversation.Status.ACTIVE)
        self.assertEqual(created.conversation.owner, self.client_user)
        self.assertEqual(created.conversation.title, "Como funciona o Link?")
        self.assertEqual(created.first_message.body, "  Como   funciona\no Link?  ")
        self.assertEqual(created.first_message.processing_status, Message.ProcessingStatus.PENDING)
        self.assertFalse(SupportHandoff.objects.filter(conversation=created.conversation).exists())

        with patch.object(Message.objects, "create", side_effect=RuntimeError("synthetic failure")):
            with self.assertRaises(RuntimeError):
                self.create_thread("Atomic rollback")
        self.assertFalse(Conversation.objects.filter(title="Atomic rollback").exists())

    def test_non_client_and_inactive_client_cannot_create(self):
        for user in (self.admin_user, self.support_user):
            with self.subTest(role=user.role), self.assertRaises(PermissionDenied):
                create_conversation(owner=user, first_message="Denied", client_turn_key=uuid.uuid4())
        self.client_user.is_active = False
        self.client_user.save(update_fields={"is_active", "updated_at"})
        with self.assertRaises(PermissionDenied):
            self.create_thread("Inactive")

    def test_title_is_created_once_and_later_messages_only_touch_recency(self):
        created = self.create_thread("a" * 51)
        original_title = created.conversation.title
        original_updated_at = created.conversation.updated_at
        result = append_client_message(
            actor=self.client_user,
            conversation=created.conversation,
            body="Uma mensagem posterior que nunca muda o título",
            client_turn_key=uuid.uuid4(),
        )
        created.conversation.refresh_from_db()
        self.assertTrue(result.created)
        self.assertEqual(original_title, "a" * 47 + "...")
        self.assertEqual(created.conversation.title, original_title)
        self.assertGreater(created.conversation.updated_at, original_updated_at)

    def test_client_turn_replay_reuses_message_and_conflict_is_rejected(self):
        created = self.create_thread()
        key = uuid.uuid4()
        first = append_client_message(
            actor=self.client_user, conversation=created.conversation,
            body="Turno estável", client_turn_key=key,
        )
        replay = append_client_message(
            actor=self.client_user, conversation=created.conversation,
            body="Turno estável", client_turn_key=key,
        )
        self.assertTrue(first.created)
        self.assertFalse(replay.created)
        self.assertEqual(first.message.id, replay.message.id)
        self.assertEqual(
            Message.objects.filter(conversation=created.conversation, idempotency_key=key).count(), 1
        )
        with self.assertRaises(IdempotencyConflictError):
            append_client_message(
                actor=self.client_user, conversation=created.conversation,
                body="Outro conteúdo", client_turn_key=key,
            )

    def test_same_turn_key_is_independent_between_conversations(self):
        key = uuid.uuid4()
        first = self.create_thread("A", key=key)
        second = self.create_thread("B", key=key)
        self.assertNotEqual(first.first_message.id, second.first_message.id)

    def test_agent_response_is_at_most_once_and_completes_client_turn(self):
        created = self.create_thread()
        first = append_agent_message(
            conversation=created.conversation,
            client_message=created.first_message,
            body="Resposta persistida",
        )
        replay = append_agent_message(
            conversation=created.conversation,
            client_message=created.first_message,
            body="Resposta persistida",
        )
        created.first_message.refresh_from_db()
        self.assertTrue(first.created)
        self.assertFalse(replay.created)
        self.assertEqual(first.message.id, replay.message.id)
        self.assertEqual(created.first_message.processing_status, Message.ProcessingStatus.COMPLETED)
        with self.assertRaises(IdempotencyConflictError):
            append_agent_message(
                conversation=created.conversation,
                client_message=created.first_message,
                body="Resposta conflitante",
            )

    def test_failed_turn_preserves_complete_client_body(self):
        body = "Mensagem preservada durante falha controlada"
        created = self.create_thread(body)
        mark_client_turn_failed(
            conversation=created.conversation, client_message=created.first_message
        )
        created.first_message.refresh_from_db()
        self.assertEqual(created.first_message.body, body)
        self.assertEqual(created.first_message.processing_status, Message.ProcessingStatus.FAILED)

    def test_sender_contract_and_support_assignment_boundary(self):
        created = self.create_thread()
        system = append_system_message(conversation=created.conversation, body="Aviso")
        self.assertIsNone(system.message.sender_user)
        self.assertEqual(system.message.sender_type, Message.SenderType.SYSTEM)

        created.conversation.status = Conversation.Status.HUMAN
        created.conversation.save(update_fields={"status", "updated_at"})
        SupportHandoff.objects.create(
            conversation=created.conversation,
            status=SupportHandoff.Status.ASSIGNED,
            accepted_at=timezone.now(),
            assigned_support_user=self.support_user,
        )
        support = append_support_message(
            actor=self.support_user, conversation=created.conversation, body="Atendimento humano"
        )
        self.assertEqual(support.message.sender_user, self.support_user)
        self.assertEqual(support.message.sender_type, Message.SenderType.SUPPORT_AGENT)
        with self.assertRaises(PermissionDenied):
            append_support_message(
                actor=self.admin_user, conversation=created.conversation, body="Sem atribuição"
            )

    def test_state_write_policy(self):
        expected_client = {
            Conversation.Status.ACTIVE: True,
            Conversation.Status.WAITING_HUMAN: True,
            Conversation.Status.HUMAN: True,
            Conversation.Status.CLOSED: False,
            Conversation.Status.BLOCKED: False,
            Conversation.Status.DELETED: False,
        }
        for status, allowed in expected_client.items():
            with self.subTest(status=status):
                created = self.create_thread(f"State {status}")
                conversation = created.conversation
                conversation.status = status
                if status == Conversation.Status.BLOCKED:
                    conversation.status_before_block = Conversation.Status.ACTIVE
                if status == Conversation.Status.DELETED:
                    conversation.deleted_at = timezone.now()
                    conversation.deleted_by = self.admin_user
                conversation.save()
                operation = lambda: append_client_message(
                    actor=self.client_user, conversation=conversation,
                    body="Follow-up", client_turn_key=uuid.uuid4(),
                )
                if allowed:
                    operation()
                elif status == Conversation.Status.DELETED:
                    with self.assertRaises(PermissionDenied):
                        operation()
                else:
                    with self.assertRaises(ConversationNotWritableError):
                        operation()

    def test_automated_response_only_allowed_while_active(self):
        for status in (
            Conversation.Status.WAITING_HUMAN,
            Conversation.Status.HUMAN,
            Conversation.Status.CLOSED,
            Conversation.Status.BLOCKED,
            Conversation.Status.DELETED,
        ):
            with self.subTest(status=status):
                created = self.create_thread(f"Agent state {status}")
                conversation = created.conversation
                conversation.status = status
                if status == Conversation.Status.BLOCKED:
                    conversation.status_before_block = Conversation.Status.ACTIVE
                if status == Conversation.Status.DELETED:
                    conversation.deleted_at = timezone.now()
                    conversation.deleted_by = self.admin_user
                conversation.save()
                with self.assertRaises(ConversationNotWritableError):
                    append_agent_message(
                        conversation=conversation,
                        client_message=created.first_message,
                        body="Must not persist",
                    )

    def test_owned_queries_hide_deleted_and_deny_cross_client_access(self):
        active = self.create_thread("Visible").conversation
        blocked = self.create_thread("Blocked readable").conversation
        blocked.status = Conversation.Status.BLOCKED
        blocked.status_before_block = Conversation.Status.ACTIVE
        blocked.save()
        closed = self.create_thread("Closed readable").conversation
        closed.status = Conversation.Status.CLOSED
        closed.save()
        deleted = self.create_thread("Hidden").conversation
        deleted.status = Conversation.Status.DELETED
        deleted.deleted_at = timezone.now()
        deleted.deleted_by = self.admin_user
        deleted.save()

        ids = set(list_owned_conversations(owner=self.client_user).values_list("id", flat=True))
        self.assertEqual(ids, {active.id, blocked.id, closed.id})
        self.assertEqual(get_owned_conversation(owner=self.client_user, conversation_id=blocked.id), blocked)
        self.assertEqual(list(get_conversation_history(owner=self.client_user, conversation_id=closed.id))[0].body, "Closed readable")
        for conversation in (active, deleted):
            with self.assertRaises(PermissionDenied):
                get_owned_conversation(owner=self.other_client, conversation_id=conversation.id)
        with self.assertRaises(PermissionDenied):
            get_owned_conversation(owner=self.client_user, conversation_id=deleted.id)

    def test_message_history_is_stably_ordered_and_body_is_immutable(self):
        created = self.create_thread()
        agent = append_agent_message(
            conversation=created.conversation,
            client_message=created.first_message,
            body="Resposta",
        ).message
        same_time = timezone.now()
        Message.objects.filter(pk__in=(created.first_message.id, agent.id)).update(created_at=same_time)
        expected = sorted((created.first_message.id, agent.id))
        actual = list(
            get_conversation_history(
                owner=self.client_user, conversation_id=created.conversation.id
            ).values_list("id", flat=True)
        )
        self.assertEqual(actual, expected)
        agent.body = "Edição proibida"
        with self.assertRaises(ValidationError):
            agent.save()
        self.assertFalse(hasattr(__import__("apps.web_portal.conversations.services", fromlist=["x"]), "update_message"))


class ConversationContextTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="context-client", password=PASSWORD, role=User.Role.CLIENT
        )

    def new_thread(self, body="Initial"):
        return create_conversation(
            owner=self.user, first_message=body, client_turn_key=uuid.uuid4()
        )

    def next_client(self, conversation, body):
        return append_client_message(
            actor=self.user, conversation=conversation, body=body,
            client_turn_key=uuid.uuid4(),
        ).message

    def test_protocol_reference_context_is_ordered_and_present(self):
        created = self.new_thread("Qual foi o resultado do protocolo POC-OPS-0004?")
        append_agent_message(
            conversation=created.conversation, client_message=created.first_message,
            body="O protocolo foi concluído.",
        )
        current = self.next_client(created.conversation, "E quando ele foi executado?")
        context = build_agent_context(current_message=current)
        self.assertEqual(
            [item.content for item in context.messages],
            [
                "Qual foi o resultado do protocolo POC-OPS-0004?",
                "O protocolo foi concluído.",
                "E quando ele foi executado?",
            ],
        )
        self.assertEqual([item.role for item in context.messages], [ContextRole.USER, ContextRole.ASSISTANT, ContextRole.USER])

    def test_get_smart_reference_is_preserved(self):
        created = self.new_thread("Me fale sobre a Get Smart.")
        append_agent_message(
            conversation=created.conversation, client_message=created.first_message,
            body="A Get Smart é uma maquininha Getnet.",
        )
        current = self.next_client(created.conversation, "E quanto ela custa?")
        context = build_agent_context(current_message=current)
        self.assertIn("Me fale sobre a Get Smart.", [item.content for item in context.messages])
        self.assertEqual(context.messages[-1].content, "E quanto ela custa?")

    def test_context_is_isolated_by_conversation_uuid(self):
        first = self.new_thread("Estamos falando do POC-OPS-0004")
        second = self.new_thread("Ele falhou?")
        context = build_agent_context(current_message=second.first_message)
        self.assertEqual([item.content for item in context.messages], ["Ele falhou?"])
        self.assertNotEqual(context.conversation_id, str(first.conversation.id))

    def test_context_keeps_only_twelve_newest_prior_messages(self):
        created = self.new_thread("prior-00")
        previous = created.first_message
        for number in range(1, 15):
            if number % 2:
                previous = append_agent_message(
                    conversation=created.conversation, client_message=previous,
                    body=f"prior-{number:02d}",
                ).message
            else:
                previous = self.next_client(created.conversation, f"prior-{number:02d}")
        current = self.next_client(created.conversation, "current")
        context = build_agent_context(current_message=current)
        self.assertEqual(len(context.messages) - 1, MAX_PRIOR_MESSAGES)
        self.assertEqual(context.messages[0].content, "prior-03")
        self.assertEqual(context.messages[-2].content, "prior-14")
        self.assertEqual(context.messages[-1].content, "current")

    def test_character_limit_drops_oldest_whole_messages_first(self):
        created = self.new_thread("a" * 2_000)
        append_agent_message(
            conversation=created.conversation, client_message=created.first_message,
            body="b" * 2_000,
        )
        previous = self.next_client(created.conversation, "c" * 2_000)
        append_agent_message(
            conversation=created.conversation, client_message=previous, body="d" * 2_000
        )
        current = self.next_client(created.conversation, "z" * 1_500)
        context = build_agent_context(current_message=current)
        self.assertLessEqual(context.character_count, MAX_CONTEXT_CHARACTERS)
        self.assertEqual([item.content[0] for item in context.messages], ["c", "d", "z"])
        self.assertEqual(context.messages[-1].content, "z" * 1_500)

    def test_oversized_current_is_fully_persisted_but_context_copy_is_marked(self):
        complete_body = "ç" * 6_001
        created = self.new_thread(complete_body)
        context = build_agent_context(current_message=created.first_message)
        created.first_message.refresh_from_db()
        self.assertEqual(created.first_message.body, complete_body)
        self.assertEqual(context.character_count, MAX_CONTEXT_CHARACTERS)
        self.assertEqual(len(context.messages[0].content), MAX_CONTEXT_CHARACTERS)
        self.assertTrue(context.messages[0].truncated)
        self.assertEqual(context.messages[0].original_character_count, 6_001)

    def test_non_active_conversation_cannot_build_actionable_agent_context(self):
        for status in (Conversation.Status.BLOCKED, Conversation.Status.CLOSED, Conversation.Status.DELETED):
            with self.subTest(status=status):
                created = self.new_thread(f"Context {status}")
                conversation = created.conversation
                conversation.status = status
                if status == Conversation.Status.BLOCKED:
                    conversation.status_before_block = Conversation.Status.ACTIVE
                if status == Conversation.Status.DELETED:
                    admin = User.objects.create_user(
                        username=f"delete-{status.lower()}", password=PASSWORD, role=User.Role.ADMIN
                    )
                    conversation.deleted_at = timezone.now()
                    conversation.deleted_by = admin
                conversation.save()
                with self.assertRaises(ConversationNotWritableError):
                    build_agent_context(current_message=created.first_message)


class ConcurrentClientTurnTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Concurrent portal idempotency requires PostgreSQL row locks.")
        self.user = User.objects.create_user(
            username="concurrent-client", password=PASSWORD, role=User.Role.CLIENT
        )
        self.created = create_conversation(
            owner=self.user, first_message="Initial", client_turn_key=uuid.uuid4()
        )

    def test_concurrent_duplicate_turn_persists_exactly_once(self):
        turn_key = uuid.uuid4()
        user_id = self.user.id
        conversation_id = self.created.conversation.id

        def submit():
            close_old_connections()
            try:
                actor = User.objects.get(pk=user_id)
                result = append_client_message(
                    actor=actor,
                    conversation=conversation_id,
                    body="Concurrent same turn",
                    client_turn_key=turn_key,
                )
                return result.message.id, result.created
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: submit(), range(2)))

        self.assertEqual(len({message_id for message_id, _ in results}), 1)
        self.assertEqual(sum(created for _, created in results), 1)
        self.assertEqual(
            Message.objects.filter(
                conversation_id=conversation_id,
                sender_type=Message.SenderType.CLIENT,
                idempotency_key=turn_key,
            ).count(),
            1,
        )
