import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.conversations.titles import conversation_title_from_first_message


class ConversationTitleTests(SimpleTestCase):
    def test_title_normalizes_whitespace_without_padding(self):
        self.assertEqual(conversation_title_from_first_message("  Olá,   Getnet!\n"), "Olá, Getnet!")
        self.assertEqual(len(conversation_title_from_first_message("a" * 49)), 49)

    def test_title_boundary_and_truncation(self):
        self.assertEqual(conversation_title_from_first_message("a" * 50), "a" * 50)
        self.assertEqual(conversation_title_from_first_message("a" * 51), "a" * 47 + "...")
        title = conversation_title_from_first_message("ação " * 20)
        self.assertLessEqual(len(title), 50)

    def test_title_does_not_call_any_model_provider(self):
        self.assertEqual(conversation_title_from_first_message("  1 + 1?  "), "1 + 1?")


class PortalModelMetadataTests(SimpleTestCase):
    def test_conversation_contract(self):
        self.assertEqual(Conversation._meta.pk.get_internal_type(), "UUIDField")
        self.assertEqual(Conversation._meta.db_table, "conversations")
        self.assertEqual(Conversation._meta.get_field("title").max_length, 50)
        self.assertEqual(
            tuple(Conversation.Status.values),
            ("ACTIVE", "WAITING_HUMAN", "HUMAN", "CLOSED", "BLOCKED", "DELETED"),
        )
        self.assertIn("status_before_block", {field.name for field in Conversation._meta.fields})
        self.assertIn("deleted_at", {field.name for field in Conversation._meta.fields})
        self.assertIn("deleted_by", {field.name for field in Conversation._meta.fields})

    def test_message_contract_and_immutable_queryset_guard(self):
        self.assertEqual(Message._meta.pk.get_internal_type(), "UUIDField")
        self.assertEqual(Message._meta.db_table, "messages")
        self.assertEqual(Message._meta.ordering, ("created_at", "id"))
        with self.assertRaises(ValidationError):
            Message.objects.all().update(body="rewritten historical content")
        with self.assertRaises(ValidationError):
            Message.objects.all().delete()


class PortalPersistenceTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username="client", password="synthetic-test-password", role=User.Role.CLIENT
        )
        self.support_user = User.objects.create_user(
            username="support", password="synthetic-test-password", role=User.Role.SUPPORT_AGENT
        )
        self.conversation = Conversation.objects.create(
            owner=self.client_user,
            status=Conversation.Status.ACTIVE,
            title=conversation_title_from_first_message("primeira mensagem"),
        )

    def test_primary_keys_and_required_relationships_are_uuid_backed(self):
        self.assertIsInstance(self.client_user.pk, uuid.UUID)
        self.assertIsInstance(self.conversation.pk, uuid.UUID)
        self.assertEqual(self.conversation.owner_id, self.client_user.pk)

    def test_message_sender_and_client_idempotency_contract(self):
        key = uuid.uuid4()
        first = Message.objects.create(
            conversation=self.conversation,
            sender_type=Message.SenderType.CLIENT,
            sender_user=self.client_user,
            body="pergunta",
            idempotency_key=key,
        )
        second = Message.objects.create(
            conversation=self.conversation,
            sender_type=Message.SenderType.AGENT,
            sender_user=None,
            body="resposta",
        )
        self.assertIsInstance(first.pk, uuid.UUID)
        self.assertIsInstance(second.pk, uuid.UUID)
        self.assertEqual(list(self.conversation.messages.all()), [first, second])

        with self.assertRaises(IntegrityError), transaction.atomic():
            Message.objects.create(
                conversation=self.conversation,
                sender_type=Message.SenderType.CLIENT,
                sender_user=self.client_user,
                body="duplicated retry",
                idempotency_key=key,
            )

        stored = Message.objects.get(pk=first.pk)
        stored.body = "changed historical content"
        with self.assertRaises(ValidationError):
            stored.save()

    def test_block_closed_and_soft_delete_state_shapes(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender_type=Message.SenderType.CLIENT,
            sender_user=self.client_user,
            body="kept with the conversation",
            idempotency_key=uuid.uuid4(),
        )
        self.conversation.status = Conversation.Status.BLOCKED
        self.conversation.status_before_block = Conversation.Status.HUMAN
        self.conversation.save()
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.status_before_block, Conversation.Status.HUMAN)

        self.conversation.status = Conversation.Status.DELETED
        self.conversation.status_before_block = None
        self.conversation.deleted_at = self.conversation.updated_at
        self.conversation.deleted_by = User.objects.create_user(
            username="admin", password="synthetic-test-password", role=User.Role.ADMIN
        )
        self.conversation.save()
        self.assertTrue(Message.objects.filter(pk=message.pk).exists())

    def test_admin_block_can_restore_each_approved_prior_state(self):
        for status in (
            Conversation.Status.ACTIVE,
            Conversation.Status.WAITING_HUMAN,
            Conversation.Status.HUMAN,
        ):
            with self.subTest(prior_status=status):
                conversation = Conversation.objects.create(
                    owner=self.client_user,
                    status=status,
                    title=f"Block test {status}",
                )
                handoff = None
                if status == Conversation.Status.HUMAN:
                    from apps.web_portal.support.models import SupportHandoff

                    handoff = SupportHandoff.objects.create(
                        conversation=conversation,
                        status=SupportHandoff.Status.ASSIGNED,
                        accepted_at=timezone.now(),
                        assigned_support_user=self.support_user,
                    )

                conversation.status = Conversation.Status.BLOCKED
                conversation.status_before_block = status
                conversation.save()
                conversation.refresh_from_db()
                self.assertEqual(conversation.status_before_block, status)

                conversation.status = status
                conversation.status_before_block = None
                conversation.save()
                conversation.refresh_from_db()
                self.assertEqual(conversation.status, status)
                if handoff is not None:
                    handoff.refresh_from_db()
                    self.assertEqual(handoff.assigned_support_user, self.support_user)
