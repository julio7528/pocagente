"""Opt-in real Phase 7 hybrid retrieval validation."""

from __future__ import annotations

import os

import pytest

from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.rag.embeddings.fastembed import FastEmbedAdapter
from apps.agent_api.app.rag.retrieval.hybrid import HybridRetriever
from apps.agent_api.app.rag.retrieval.lexical import LexicalRetriever
from apps.agent_api.app.rag.retrieval.semantic import SemanticRetriever
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL integration tests are opt-in",
)


def test_real_hybrid_retrieval_returns_bounded_fused_provenance(
    real_database_config: DatabaseConfig,
) -> None:
    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            semantic = SemanticRetriever(None, FastEmbedAdapter())  # type: ignore[arg-type]
            hybrid = HybridRetriever(
                LexicalRetriever(None),  # type: ignore[arg-type]
                semantic,
                database=database,
            )
            for query in (
                "Como funciona o cancelamento de venda?",
                "O que o robô R1 faz no processo?",
                "O que acontece durante o processamento do arquivo?",
            ):
                results = await hybrid.search(query)
                assert len(results) <= 5
                assert all(item.rank <= 5 and item.score > 0 for item in results)
                assert all(item.provenance.source_reference for item in results)
                assert all(item.provenance.document_id for item in results)
                assert all(item.matched_channels for item in results)
        finally:
            await database.close()

    run_async(validate())
