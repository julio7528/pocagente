"""Explicit opt-in real DeepSeek smoke for bounded LangGraph orchestration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from apps.agent_api.app.agents.customer_support import (
    CustomerSupportAgent,
    CustomerSupportOperation,
)
from apps.agent_api.app.agents.knowledge import KnowledgeAgent
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
from apps.agent_api.app.llm.config import load_deepseek_config
from apps.agent_api.app.llm.deepseek import DeepSeekProvider
from apps.agent_api.app.rag.embeddings.fastembed import FastEmbedAdapter
from apps.agent_api.app.rag.grounding.context_builder import ContextBuilder
from apps.agent_api.app.rag.retrieval.hybrid import HybridRetriever
from apps.agent_api.app.rag.retrieval.lexical import LexicalRetriever
from apps.agent_api.app.rag.retrieval.semantic import SemanticRetriever
from apps.agent_api.app.tools.ops import OpsAccessContext, OperationalTools
from tests.integration.deepseek_env import load_deepseek_environment
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1"
    or os.getenv("GETNET_RUN_DEEPSEEK_INTEGRATION") != "1",
    reason="real LangGraph smoke requires explicit database and DeepSeek integration flags",
)


@pytest.fixture(scope="module", autouse=True)
def load_local_deepseek_environment() -> None:
    load_deepseek_environment(Path(__file__).resolve().parents[2] / ".env")


AUTHORIZED = OpsAccessContext(principal_id="orchestration-smoke", can_read_operational_facts=True)


def test_real_langgraph_executes_approved_agent_paths(
    real_database_config: DatabaseConfig,
) -> None:
    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            async with database.connection() as connection:
                provider = DeepSeekProvider(load_deepseek_config())
                graph = LangGraphOrchestrator(
                    RouterAgent(),
                    KnowledgeAgent(
                        HybridRetriever(
                            LexicalRetriever(None),  # type: ignore[arg-type]
                            SemanticRetriever(None, FastEmbedAdapter()),  # type: ignore[arg-type]
                            database=database,
                        ),
                        ContextBuilder(),
                        provider,
                    ),
                    CustomerSupportAgent(
                        OperationalTools(OperationalRepository(connection)),
                        provider,
                    ),
                )
                support_context = CustomerSupportContext(
                    protocol_number="POC-OPS-0002",
                    operation=CustomerSupportOperation.EXECUTION_FAILURE,
                )

                knowledge = await graph.execute(
                    OrchestrationRequest(message="Qual é o processo documentado de cancelamento de venda?")
                )
                support = await graph.execute(
                    OrchestrationRequest(
                        message="Qual falha foi observada no protocolo POC-OPS-0002?",
                        customer_support_context=support_context,
                    )
                )
                cooperative = await graph.execute(
                    OrchestrationRequest(
                        message="O protocolo está atrasado? O que deveria ter acontecido?",
                        ops_access_context=AUTHORIZED,
                        customer_support_context=support_context,
                    )
                )

                for result in (knowledge, support, cooperative):
                    assert result.status is OrchestrationStatus.COMPLETED
                    assert "api_key" not in result.model_dump_json().lower()
                    assert "postgres://" not in result.model_dump_json().lower()
                assert knowledge.knowledge_result and knowledge.knowledge_result.answer
                assert support.customer_support_result and support.customer_support_result.answer
                assert cooperative.knowledge_result and cooperative.customer_support_result
                assert cooperative.knowledge_result.citations
                assert cooperative.customer_support_result.facts
        finally:
            await database.close()

    run_async(validate())
