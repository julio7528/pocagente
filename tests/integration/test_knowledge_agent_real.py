"""Opt-in real Phase 7/8 integration for the Knowledge Agent with a mocked LLM."""

from __future__ import annotations

import os

import pytest

from apps.agent_api.app.agents.knowledge import KnowledgeAgent, KnowledgeRequest, KnowledgeResultStatus
from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.llm.models import LLMGenerationRequest, LLMGenerationResult
from apps.agent_api.app.rag.embeddings.fastembed import FastEmbedAdapter
from apps.agent_api.app.rag.grounding.context_builder import ContextBuilder
from apps.agent_api.app.rag.retrieval.hybrid import HybridRetriever
from apps.agent_api.app.rag.retrieval.lexical import LexicalRetriever
from apps.agent_api.app.rag.retrieval.semantic import SemanticRetriever
from apps.agent_api.app.rag.scope import KnowledgeScope
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL integration tests are opt-in",
)


class MockKnowledgeProvider:
    def __init__(self) -> None:
        self.requests: list[LLMGenerationRequest] = []

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
        self.requests.append(request)
        return LLMGenerationResult(content=(
            '{"schema_version":"1.0","status":"ANSWERED",'
            '"answer":"Resposta simulada fundamentada [C1].","citation_ids":["C1"]}'
        ))


def test_real_retrieval_and_grounding_produce_safe_mocked_knowledge_result(
    real_database_config: DatabaseConfig,
) -> None:
    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            semantic = SemanticRetriever(None, FastEmbedAdapter())  # type: ignore[arg-type]
            retrieval = HybridRetriever(
                LexicalRetriever(None),  # type: ignore[arg-type]
                semantic,
                database=database,
            )
            provider = MockKnowledgeProvider()
            agent = KnowledgeAgent(retrieval, ContextBuilder(), provider)

            result = await agent.answer(
                KnowledgeRequest(
                    question="Como funciona o cancelamento de venda?",
                    knowledge_scope=KnowledgeScope.INTERNAL,
                )
            )

            assert result.status is KnowledgeResultStatus.ANSWERED
            assert result.answer
            assert 0 < len(result.citations) <= 5
            assert [citation.id for citation in result.citations] == [
                f"C{position}" for position in range(1, len(result.citations) + 1)
            ]
            assert provider.requests
            prompt = provider.requests[0].messages[1].content
            assert "Evidence data:" in prompt
            serialized = result.model_dump_json()
            assert "source_reference" not in serialized
            assert "document_key" not in serialized
        finally:
            await database.close()

    run_async(validate())
