"""Opt-in PostgreSQL integration for Customer Support with a mocked LLM provider."""

from __future__ import annotations

import os

import pytest

from apps.agent_api.app.agents.customer_support import (
    CustomerSupportAgent,
    CustomerSupportOperation,
    CustomerSupportRequest,
    CustomerSupportStatus,
)
from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.repositories.operational import OperationalRepository
from apps.agent_api.app.llm.models import LLMGenerationRequest, LLMGenerationResult
from apps.agent_api.app.tools.ops import OpsAccessContext, OperationalTools
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL integration tests are opt-in",
)


class MockedProvider:
    def __init__(self) -> None:
        self.requests: list[LLMGenerationRequest] = []

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
        self.requests.append(request)
        return LLMGenerationResult(
            content=(
                '{"answer":"O protocolo possui evidência operacional observada.",'
                '"inferences":[{"statement":"A evidência pode indicar uma falha no download."}]}'
            )
        )


AUTHORIZED = OpsAccessContext(principal_id="integration-support-operator", can_read_operational_facts=True)


def test_customer_support_uses_real_ops_evidence_without_database_mutation(
    real_database_config: DatabaseConfig,
) -> None:
    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            async with database.connection() as connection:
                provider = MockedProvider()
                agent = CustomerSupportAgent(
                    OperationalTools(OperationalRepository(connection)),
                    provider,
                )
                result = await agent.answer(
                    CustomerSupportRequest(
                        question="Investigue a falha observada no protocolo.",
                        protocol_number="POC-OPS-0002",
                        operation=CustomerSupportOperation.EXECUTION_FAILURE,
                        authorization=AUTHORIZED,
                    )
                )

                assert result.status is CustomerSupportStatus.ANSWERED
                assert result.facts
                assert any(item.source == "ProtocolStatusFacts" for item in result.facts)
                assert any(item.source == "ExecutionFailureEvidence" for item in result.facts)
                assert result.inferences
                assert len(provider.requests) == 1
                assert "Investigue a falha observada no protocolo." in provider.requests[0].messages[1].content
                serialized = result.model_dump_json()
                assert "postgres" not in serialized.lower()
                assert "source_reference" not in serialized
        finally:
            await database.close()

    run_async(validate())
