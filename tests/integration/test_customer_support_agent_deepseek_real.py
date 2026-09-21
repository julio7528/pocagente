"""Explicit opt-in Customer Support smoke using synthetic OPS data and DeepSeek."""

from __future__ import annotations

import os
from pathlib import Path

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
from apps.agent_api.app.llm.config import load_deepseek_config
from apps.agent_api.app.llm.deepseek import DeepSeekProvider
from apps.agent_api.app.llm.models import LLMGenerationRequest, LLMGenerationResult
from apps.agent_api.app.tools.ops import OpsAccessContext, OperationalTools
from tests.integration.deepseek_env import load_deepseek_environment
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1"
    or os.getenv("GETNET_RUN_DEEPSEEK_INTEGRATION") != "1",
    reason="real Customer Support smoke requires explicit database and DeepSeek integration flags",
)


@pytest.fixture(scope="module", autouse=True)
def load_local_deepseek_environment() -> None:
    load_deepseek_environment(Path(__file__).resolve().parents[2] / ".env")


AUTHORIZED = OpsAccessContext(principal_id="integration-support-operator", can_read_operational_facts=True)


class RecordingProvider:
    """Record the neutral request while delegating the opt-in call to DeepSeek."""

    def __init__(self, delegate: DeepSeekProvider) -> None:
        self._delegate = delegate
        self.requests: list[LLMGenerationRequest] = []

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
        self.requests.append(request)
        return await self._delegate.generate(request)


def test_real_customer_support_returns_typed_fact_and_inference_result(
    real_database_config: DatabaseConfig,
) -> None:
    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            async with database.connection() as connection:
                provider = RecordingProvider(DeepSeekProvider(load_deepseek_config()))
                agent = CustomerSupportAgent(
                    OperationalTools(OperationalRepository(connection)),
                    provider,
                )
                result = await agent.answer(
                    CustomerSupportRequest(
                        question="Qual falha foi observada no protocolo?",
                        protocol_number="POC-OPS-0002",
                        operation=CustomerSupportOperation.EXECUTION_FAILURE,
                        authorization=AUTHORIZED,
                    )
                )

                assert result.status is CustomerSupportStatus.ANSWERED
                assert result.answer and result.answer.strip()
                assert result.facts
                assert len(provider.requests) == 1
                assert "Qual falha foi observada no protocolo?" in provider.requests[0].messages[1].content
                assert all(item.source in {"ProtocolStatusFacts", "ExecutionFailureEvidence"} for item in result.facts)
                assert all(inference.statement.strip() for inference in result.inferences)
                serialized = result.model_dump_json()
                for unsafe in ("api_key", "password", "postgres://", "source_reference"):
                    assert unsafe not in serialized.lower()
        finally:
            await database.close()

    run_async(validate())
