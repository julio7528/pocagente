from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.models import Conversation
from apps.web_portal.integrations.human_escalation import (
    HumanTransitionUnavailable,
    transition_human_escalation,
)


class HumanEscalationHttpClientTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username="support.integration.client", password="TestPassword!28", role=User.Role.CLIENT
        )
        self.support = User.objects.create_user(
            username="support.integration.agent", password="TestPassword!28", role=User.Role.SUPPORT_AGENT
        )
        self.conversation = Conversation.objects.create(
            owner=self.client_user, title="Cliente pede ajuda humana"
        )

    @override_settings(
        AGENT_API_INTERNAL_URL="http://agent-api.internal:8000",
        AGENT_API_SERVICE_TOKEN="synthetic-internal-test-token",
        AGENT_API_CONNECT_TIMEOUT_SECONDS=1.5,
        AGENT_API_READ_TIMEOUT_SECONDS=3.0,
    )
    @patch("apps.web_portal.integrations.human_escalation.request_internal")
    def test_confirmation_uses_private_bearer_and_typed_non_authoritative_payload(self, internal_request):
        response = Mock(status_code=200)
        response.json.return_value = {
            "status": "TRANSITIONED",
            "conversation": {"conversation_id": str(self.conversation.pk)},
            "state": "WAITING_HUMAN",
            "reason": "HANDOFF_CONFIRMED_AWAITING_OPERATOR",
            "handoff_package": None,
            "assigned_operator_id": None,
            "automation_suspended": False,
        }
        internal_request.return_value = response
        result = transition_human_escalation(
            actor=self.client_user,
            conversation=self.conversation,
            action="CONFIRM",
            current_state="WAITING_CONFIRMATION",
        )
        self.assertEqual(result.state, "WAITING_HUMAN")
        args, kwargs = internal_request.call_args
        self.assertEqual(args, ("POST", "/internal/human-escalation/transition"))
        self.assertIs(kwargs["actor"], self.client_user)
        self.assertFalse(kwargs["ops_authorized"])
        self.assertEqual(kwargs["json"]["action"], "CONFIRM")
        self.assertTrue(kwargs["json"]["handoff"]["user_confirmation"])
        self.assertNotIn("operator", kwargs["json"])

    @override_settings(
        AGENT_API_INTERNAL_URL="http://agent-api.internal:8000",
        AGENT_API_SERVICE_TOKEN="synthetic-internal-test-token",
    )
    @patch("apps.web_portal.integrations.human_escalation.request_internal")
    def test_resolution_propagates_database_assignment_but_not_browser_claim(self, internal_request):
        response = Mock(status_code=200)
        response.json.return_value = {
            "status": "TRANSITIONED",
            "conversation": {"conversation_id": str(self.conversation.pk)},
            "state": "RESOLVED",
            "reason": "EXPLICIT_HUMAN_RESOLUTION",
            "handoff_package": None,
            "assigned_operator_id": None,
            "automation_suspended": False,
        }
        internal_request.return_value = response
        transition_human_escalation(
            actor=self.support,
            conversation=self.conversation,
            action="RESOLVE",
            current_state="HUMAN",
            active_operator_id=str(self.support.pk),
        )
        args, kwargs = internal_request.call_args
        body = kwargs["json"]
        self.assertEqual(args[1], "/internal/human-escalation/transition")
        self.assertEqual(body["active_operator_id"], str(self.support.pk))
        self.assertIs(kwargs["actor"], self.support)
        self.assertFalse(kwargs["ops_authorized"])
        self.assertNotIn("role", body)
        self.assertNotIn("operator", body)

    @override_settings(AGENT_API_INTERNAL_URL="http://agent-api.internal:8000", AGENT_API_SERVICE_TOKEN="")
    def test_missing_service_token_fails_closed_without_http_call(self):
        with patch("apps.web_portal.integrations.internal_service._pooled_http_client") as client_factory:
            with self.assertRaises(HumanTransitionUnavailable):
                transition_human_escalation(
                    actor=self.client_user,
                    conversation=self.conversation,
                    action="CONFIRM",
                    current_state="WAITING_CONFIRMATION",
                )
        client_factory.assert_not_called()

    @override_settings(
        AGENT_API_INTERNAL_URL="http://agent-api.internal:8000",
        AGENT_API_SERVICE_TOKEN="synthetic-internal-test-token",
    )
    def test_non_boolean_automation_suspended_value_is_rejected(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "status": "TRANSITIONED",
            "conversation": {"conversation_id": str(self.conversation.pk)},
            "state": "WAITING_HUMAN",
            "assigned_operator_id": None,
            "automation_suspended": "false",
        }
        with patch(
            "apps.web_portal.integrations.human_escalation.request_internal",
            return_value=response,
        ):
            with self.assertRaises(HumanTransitionUnavailable):
                transition_human_escalation(
                    actor=self.client_user,
                    conversation=self.conversation,
                    action="CONFIRM",
                    current_state="WAITING_CONFIRMATION",
                )
