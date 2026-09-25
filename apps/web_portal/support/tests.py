import uuid

from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.models import Conversation
from apps.web_portal.support.models import PasswordResetRequest, SupportHandoff


class SupportModelMetadataTests(SimpleTestCase):
    def test_handoff_and_password_reset_contracts(self):
        self.assertEqual(SupportHandoff._meta.pk.get_internal_type(), "UUIDField")
        self.assertEqual(SupportHandoff._meta.db_table, "support_handoffs")
        self.assertTrue(SupportHandoff._meta.get_field("conversation").one_to_one)
        self.assertEqual(
            tuple(SupportHandoff.Status.values), ("WAITING", "ASSIGNED", "RESOLVED", "CANCELLED")
        )
        self.assertEqual(PasswordResetRequest._meta.pk.get_internal_type(), "UUIDField")
        self.assertEqual(PasswordResetRequest._meta.db_table, "password_reset_requests")
        self.assertEqual(
            tuple(PasswordResetRequest.Status.values), ("OPEN", "RESOLVED", "REJECTED")
        )
        field_names = {field.name for field in PasswordResetRequest._meta.fields}
        self.assertFalse(field_names & {"password", "new_password", "reset_token", "password_hash"})


class SupportPersistenceTests(TestCase):
    def setUp(self):
        self.client = User.objects.create_user(
            username="client", password="synthetic-test-password", role=User.Role.CLIENT
        )
        self.support = User.objects.create_user(
            username="support", password="synthetic-test-password", role=User.Role.SUPPORT_AGENT
        )
        self.admin = User.objects.create_user(
            username="admin", password="synthetic-test-password", role=User.Role.ADMIN
        )
        self.conversation = Conversation.objects.create(owner=self.client, title="First client turn")

    def test_single_handoff_lifecycle_has_uuid_and_assignment_timestamps(self):
        handoff = SupportHandoff.objects.create(conversation=self.conversation)
        self.assertIsInstance(handoff.pk, uuid.UUID)
        handoff.status = SupportHandoff.Status.ASSIGNED
        handoff.assigned_support_user = self.support
        handoff.accepted_at = handoff.requested_at
        handoff.save()
        self.assertEqual(SupportHandoff.objects.get(conversation=self.conversation), handoff)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SupportHandoff.objects.create(conversation=self.conversation)

    def test_password_reset_persists_no_password_material(self):
        request = PasswordResetRequest.objects.create(requester=self.client)
        self.assertIsInstance(request.pk, uuid.UUID)
        self.assertEqual(request.status, PasswordResetRequest.Status.OPEN)
        self.assertIsNone(request.resolver_id)
        self.assertEqual(self.admin.role, User.Role.ADMIN)

    def test_human_resolution_and_closed_conversation_are_distinct_from_block(self):
        self.conversation.status = Conversation.Status.HUMAN
        self.conversation.save()
        handoff = SupportHandoff.objects.create(
            conversation=self.conversation,
            status=SupportHandoff.Status.ASSIGNED,
            assigned_support_user=self.support,
            accepted_at=timezone.now(),
        )
        handoff.status = SupportHandoff.Status.RESOLVED
        handoff.resolved_at = timezone.now()
        handoff.resolved_by = self.support
        handoff.save()
        self.conversation.status = Conversation.Status.CLOSED
        self.conversation.save()
        self.conversation.refresh_from_db()
        handoff.refresh_from_db()
        self.assertEqual(self.conversation.status, Conversation.Status.CLOSED)
        self.assertEqual(handoff.status, SupportHandoff.Status.RESOLVED)
