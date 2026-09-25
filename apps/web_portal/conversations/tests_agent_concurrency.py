"""Real PostgreSQL guarantees for concurrent portal agent turns."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.db import close_old_connections
from django.test import TransactionTestCase

from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.agent_turns import execute_agent_turn
from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.conversations.services import create_conversation
from apps.web_portal.integrations.agent_chat import AgentChatResponse


class ConcurrentAgentTurnTests(TransactionTestCase):
    reset_sequences = True

    def test_same_logical_turn_persists_one_client_and_at_most_one_agent_row(self):
        actor = User.objects.create_user(
            username="phase13.concurrent.client",
            password="Safe-Test-Password-13!",
            role=User.Role.CLIENT,
        )
        created = create_conversation(
            owner=actor,
            first_message="Uma pergunta submetida em paralelo",
            client_turn_key=uuid.uuid4(),
        )
        barrier = threading.Barrier(2)
        outbound_turns: list[uuid.UUID] = []
        answer = AgentChatResponse(
            status="COMPLETED",
            route="CONVERSATIONAL",
            answer="Resposta única persistida",
            reason="CONVERSATION_COMPLETED",
        )

        def synchronized_execute(_client, turn):
            outbound_turns.append(turn.client_turn_id)
            barrier.wait(timeout=10)
            return answer

        def run_turn():
            close_old_connections()
            try:
                return execute_agent_turn(
                    actor=actor,
                    conversation_id=created.conversation.pk,
                    client_message_id=created.first_message.pk,
                )
            finally:
                close_old_connections()

        with patch(
            "apps.web_portal.conversations.agent_turns.AgentChatClient.execute",
            new=synchronized_execute,
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _index: run_turn(), range(2)))

        self.assertEqual(len(outbound_turns), 2)
        self.assertEqual(outbound_turns[0], outbound_turns[1])
        self.assertEqual(
            Message.objects.filter(
                conversation=created.conversation,
                sender_type=Message.SenderType.CLIENT,
                idempotency_key=created.first_message.idempotency_key,
            ).count(),
            1,
        )
        self.assertEqual(
            Message.objects.filter(
                conversation=created.conversation,
                sender_type=Message.SenderType.AGENT,
            ).count(),
            1,
        )
        self.assertEqual(
            Message.objects.get(
                conversation=created.conversation,
                sender_type=Message.SenderType.AGENT,
            ).body,
            "Resposta única persistida",
        )
        created.first_message.refresh_from_db()
        self.assertEqual(
            created.first_message.processing_status,
            Message.ProcessingStatus.COMPLETED,
        )
        self.assertEqual(len(results), 2)
        self.assertTrue(
            all(result.outcome in {"COMPLETED", "ALREADY_COMPLETED"} for result in results)
        )
        self.assertEqual(
            Conversation.objects.get(pk=created.conversation.pk).status,
            Conversation.Status.ACTIVE,
        )
