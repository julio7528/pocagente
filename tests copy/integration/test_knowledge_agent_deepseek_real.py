"""Explicit opt-in real Knowledge Agent smoke with PostgreSQL corpus and DeepSeek."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from apps.agent_api.app.agents.knowledge import KnowledgeAgent, KnowledgeResultStatus
from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.llm.config import load_deepseek_config
from apps.agent_api.app.llm.deepseek import DeepSeekProvider
from apps.agent_api.app.rag.embeddings.fastembed import FastEmbedAdapter
from apps.agent_api.app.rag.grounding.context_builder import ContextBuilder
from apps.agent_api.app.rag.retrieval.hybrid import HybridRetriever
from apps.agent_api.app.rag.retrieval.lexical import LexicalRetriever
from apps.agent_api.app.rag.retrieval.semantic import SemanticRetriever
from tests.integration.deepseek_env import load_deepseek_environment
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1"
    or os.getenv("GETNET_RUN_DEEPSEEK_INTEGRATION") != "1",
    reason="real Knowledge smoke requires explicit database and DeepSeek integration flags",
)


@pytest.fixture(scope="module", autouse=True)
def load_local_deepseek_environment() -> None:
    """Load approved local DeepSeek configuration after explicit opt-in selection."""

    load_deepseek_environment(Path(__file__).resolve().parents[2] / ".env")


def test_real_knowledge_agent_returns_grounded_neutral_result(
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
            agent = KnowledgeAgent(
                retrieval,
                ContextBuilder(),
                DeepSeekProvider(load_deepseek_config()),
            )

            result = await agent.answer("Como funciona o cancelamento de venda?")

            assert result.status is KnowledgeResultStatus.ANSWERED
            assert result.answer and result.answer.strip()
            assert 0 < len(result.citations) <= 5
            assert [citation.id for citation in result.citations] == [
                f"C{position}" for position in range(1, len(result.citations) + 1)
            ]
            serialized = result.model_dump_json()
            assert "source_reference" not in serialized
            assert "document_key" not in serialized
            assert "content_checksum" not in serialized
        finally:
            await database.close()

    run_async(validate())
