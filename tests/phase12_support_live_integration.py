"""Opt-in local Django-to-FastAPI transition integration test.

Run with P12_LIVE_FASTAPI_TEST=1. The test starts a temporary local Uvicorn
instance with a synthetic service token; Django's test runner must use an
isolated PostgreSQL test DB.
"""

from __future__ import annotations

import os
import socket
import threading
import time
import unittest

from django.test import TestCase
from pydantic import SecretStr
import uvicorn

from apps.agent_api.app.agents.human_escalation import HumanEscalationAgent
from apps.agent_api.app.auth import ServiceAuthConfig
from apps.agent_api.app.main import create_app
from apps.web_portal.accounts.models import User
from apps.web_portal.conversations.models import Conversation
from apps.web_portal.support.models import SupportHandoff
from apps.web_portal.support.services import claim_handoff, finalize_handoff, request_human_support


@unittest.skipUnless(
    os.environ.get("P12_LIVE_FASTAPI_TEST") == "1",
    "requires explicit opt-in and an isolated PostgreSQL test database",
)
class LiveHumanTransitionIntegrationTests(TestCase):
    def test_client_confirm_support_claim_and_resolution_cross_private_http_boundary(self):
        client = User.objects.create_user(
            username="live.transition.client", password="LiveTest!41", role=User.Role.CLIENT
        )
        support = User.objects.create_user(
            username="live.transition.support", password="LiveTest!41", role=User.Role.SUPPORT_AGENT
        )
        conversation = Conversation.objects.create(owner=client, title="Teste de transição segura")

        class UnusedChatService:
            async def handle(self, *_args, **_kwargs):
                raise AssertionError("The support lifecycle must not invoke /chat.")

        token = "synthetic-phase12-support-transition-token"
        api = create_app(
            chat_service=UnusedChatService(),
            auth_config=ServiceAuthConfig(service_token=SecretStr(token)),
            human_escalation_agent=HumanEscalationAgent(),
        )
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("127.0.0.1", 0))
        server_socket.listen(8)
        port = server_socket.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(api, log_level="critical", access_log=False, lifespan="on")
        )
        thread = threading.Thread(
            target=server.run,
            kwargs={"sockets": [server_socket]},
            daemon=True,
        )
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(server.started, "temporary FastAPI transition test server did not start")
            from django.test import override_settings

            with override_settings(
                AGENT_API_INTERNAL_URL=f"http://127.0.0.1:{port}",
                AGENT_API_SERVICE_TOKEN=token,
                AGENT_API_CONNECT_TIMEOUT_SECONDS=1.0,
                AGENT_API_READ_TIMEOUT_SECONDS=2.0,
            ):
                waiting = request_human_support(
                    actor=client,
                    conversation_id=conversation.pk,
                    explicit_confirmation=True,
                )
                self.assertEqual(waiting.conversation.pk, conversation.pk)
                self.assertEqual(waiting.conversation.status, Conversation.Status.WAITING_HUMAN)
                self.assertEqual(waiting.handoff.status, SupportHandoff.Status.WAITING)

                active = claim_handoff(actor=support, conversation_id=conversation.pk)
                self.assertEqual(active.conversation.pk, conversation.pk)
                self.assertEqual(active.conversation.status, Conversation.Status.HUMAN)
                self.assertEqual(active.handoff.assigned_support_user_id, support.pk)

                closed = finalize_handoff(actor=support, conversation_id=conversation.pk)
                self.assertEqual(closed.conversation.pk, conversation.pk)
                self.assertEqual(closed.conversation.status, Conversation.Status.CLOSED)
                self.assertEqual(closed.handoff.status, SupportHandoff.Status.RESOLVED)
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            server_socket.close()

