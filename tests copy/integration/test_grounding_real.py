"""Opt-in Phase 8 grounding validation over the real Phase 7 corpus."""

from __future__ import annotations

import os

import pytest

from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.rag.embeddings.fastembed import FastEmbedAdapter
from apps.agent_api.app.rag.grounding.context_builder import (
    ContextBuilder,
    EvidenceStatus,
)
from apps.agent_api.app.rag.retrieval.hybrid import HybridRetriever
from apps.agent_api.app.rag.retrieval.lexical import LexicalRetriever
from apps.agent_api.app.rag.retrieval.semantic import SemanticRetriever
from apps.agent_api.app.rag.scope import KnowledgeScope
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL integration tests are opt-in",
)


def test_real_grounding_preserves_provenance_and_structural_no_evidence(
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
            builder = ContextBuilder()
            for query in (
                "Como funciona o cancelamento de venda?",
                "Qual é o objetivo do robô R1?",
                "O que acontece durante o processamento do cancelamento?",
            ):
                retrieved = await hybrid.search(query, KnowledgeScope.INTERNAL)
                context = builder.build(query, retrieved)
                assert context.evidence_status is EvidenceStatus.SUFFICIENT_CONTEXT
                assert 0 < len(context.evidence) <= 5
                assert [citation.id for citation in context.citations] == [
                    f"C{index}" for index in range(1, len(context.citations) + 1)
                ]
                for evidence in context.evidence:
                    retrieved_chunk = next(
                        item for item in retrieved
                        if item.chunk.chunk_id == evidence.provenance.chunk_id
                    )
                    source = retrieved_chunk.provenance
                    target = evidence.provenance
                    assert target.source_id == str(source.source_id)
                    assert target.source_name == source.source_name
                    assert target.source == source.source_name
                    assert target.source_type == source.source_type
                    assert target.origin == source.origin
                    assert target.source_reference == source.source_reference
                    assert target.domain == source.domain
                    assert target.priority == source.priority
                    assert target.document_id == str(source.document_id)
                    assert target.document_key == source.document_key
                    assert target.title == source.title
                    assert target.document_type == source.document_type
                    assert target.content_checksum == source.content_checksum
                    assert target.last_ingested_at == source.last_ingested_at
                    assert target.chunk_id == retrieved_chunk.chunk.chunk_id
                    assert target.section == retrieved_chunk.chunk.section
                    assert target.retrieval_rank == retrieved_chunk.rank
                    assert target.rrf_score == retrieved_chunk.score
                    assert target.lexical_rank == retrieved_chunk.lexical_rank
                    assert target.semantic_rank == retrieved_chunk.semantic_rank
                    assert target.matched_channels == tuple(retrieved_chunk.matched_channels)
                assert all(
                    citation.label in {
                        "Internal process documentation",
                        "Internal technical documentation",
                    }
                    for citation in context.citations
                )
                assert all(citation.source_url is None for citation in context.citations)

            no_evidence = builder.build("consulta intencional sem evidência", ())
            assert no_evidence.evidence_status is EvidenceStatus.INSUFFICIENT_EVIDENCE
            assert no_evidence.evidence == ()
            assert no_evidence.citations == ()
            assert no_evidence.reason == "NO_USABLE_EVIDENCE"
        finally:
            await database.close()

    run_async(validate())
