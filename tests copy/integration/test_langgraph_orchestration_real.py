"""Opt-in real PostgreSQL integration for LangGraph capability coordination."""

from __future__ import annotations

import os

import pytest

from apps.agent_api.app.agents.customer_support import (
    CustomerSupportAgent,
    CustomerSupportOperation,
)
from apps.agent_api.app.agents.knowledge import KnowledgeAgent, KnowledgeResultStatus
from apps.agent_api.app.agents.orchestration import (
    CustomerSupportContext,
    LangGraphOrchestrator,
    OrchestrationRequest,
    OrchestrationStatus,
)
from apps.agent_api.app.agents.router import RouterAgent
from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.repositories.operational import OperationalRepository
from apps.agent_api.app.llm.models import LLMGenerationRequest, LLMGenerationResult
from apps.agent_api.app.rag.embeddings.fastembed import FastEmbedAdapter
from apps.agent_api.app.rag.grounding.context_builder import ContextBuilder
from apps.agent_api.app.rag.retrieval.hybrid import HybridRetriever
from apps.agent_api.app.rag.retrieval.lexical import LexicalRetriever
from apps.agent_api.app.rag.retrieval.semantic import SemanticRetriever
from apps.agent_api.app.tools.ops import OpsAccessContext, OperationalTools
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL integration tests are opt-in",
)


class MockedProvider:
    """Return the existing agent-specific neutral responses without external calls."""

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
        system = request.messages[0].content
        if "Return only JSON with exactly" in system:
            return LLMGenerationResult(
                content=(
                    '{"answer":"O protocolo possui evidência operacional observada.",'
                    '"inferences":[{"statement":"A evidência pode indicar falha no download."}]}'
                )
            )
        return LLMGenerationResult(content="Resposta fundamentada [C1].")


AUTHORIZED = OpsAccessContext(principal_id="orchestration-integration", can_read_operational_facts=True)


def test_real_langgraph_coordinates_knowledge_support_and_cooperative_paths_without_mutation(
    real_database_config: DatabaseConfig,
) -> None:
    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            async with database.connection() as connection:
                provider = MockedProvider()
                retrieval = HybridRetriever(
                    LexicalRetriever(None),  # type: ignore[arg-type]
                    SemanticRetriever(None, FastEmbedAdapter()),  # type: ignore[arg-type]
                    database=database,
                )
                graph = LangGraphOrchestrator(
                    RouterAgent(),
                    KnowledgeAgent(retrieval, ContextBuilder(), provider),
                    CustomerSupportAgent(
                        OperationalTools(OperationalRepository(connection)),
                        provider,
                    ),
                )
                support_context = CustomerSupportContext(
                    protocol_number="POC-OPS-0002",
                    operation=CustomerSupportOperation.EXECUTION_FAILURE,
                    authorization=AUTHORIZED,
                )

                knowledge = await graph.execute(
                    OrchestrationRequest(message="Qual é o processo documentado de cancelamento de venda?")
                )
                assert knowledge.status is OrchestrationStatus.COMPLETED
                assert knowledge.knowledge_result is not None
                assert knowledge.knowledge_result.status is KnowledgeResultStatus.ANSWERED
                assert knowledge.customer_support_result is None

                support = await graph.execute(
                    OrchestrationRequest(
                        message="Qual é o status do protocolo POC-OPS-0002?",
                        customer_support_context=support_context,
                    )
                )
                assert support.status is OrchestrationStatus.COMPLETED
                assert support.customer_support_result is not None
                assert support.customer_support_result.facts
                assert support.knowledge_result is None

                cooperative = await graph.execute(
                    OrchestrationRequest(
                        message="O protocolo está atrasado? O que deveria ter acontecido?",
                        has_authorized_protocol_context=True,
                        customer_support_context=support_context,
                    )
                )
                assert cooperative.status is OrchestrationStatus.COMPLETED
                assert cooperative.knowledge_result is not None
                assert cooperative.customer_support_result is not None
                assert cooperative.knowledge_result.citations
                assert cooperative.customer_support_result.facts
                assert cooperative.customer_support_result.inferences
        finally:
            await database.close()

    run_async(validate())
