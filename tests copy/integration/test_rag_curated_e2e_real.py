"""Real PostgreSQL end-to-end integration test for curated internal corpus publication."""

from __future__ import annotations

import os

import numpy as np
import pytest

from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.repositories.rag import RAGRepository
from apps.agent_api.app.rag.embeddings.fastembed import FastEmbedAdapter
from apps.agent_api.app.rag.models import SearchCandidate
from apps.agent_api.app.rag.scope import KnowledgeScope
from apps.agent_api.app.rag.publication.cli import (
    INTERNAL_SOURCE_CONFIG,
    publish_curated_corpus,
)
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL integration tests are opt-in",
)


def test_real_curated_internal_corpus_publication_and_smoke_search(
    real_database_config: DatabaseConfig,
) -> None:
    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        embed_adapter = FastEmbedAdapter()

        try:
            # 1. Publish curated corpus (PDD, SDD, Technical Overview)
            results = await publish_curated_corpus(database, embed_adapter=embed_adapter)
            assert len(results) == 3
            assert all(r.status in {"SUCCESS", "SKIPPED"} for r in results)

            # 2. Verify persisted source
            async with database.connection() as conn:
                repo = RAGRepository(conn)
                source = await repo.get_source_by_reference(
                    INTERNAL_SOURCE_CONFIG["origin"],
                    INTERNAL_SOURCE_CONFIG["reference"],
                )
                assert source is not None
                assert source.status == "ACTIVE"
                assert source.domain == "cancellation-process"
                source_id = source.source_id

                # 3. Verify persisted documents
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT document_id, document_key, title, document_type, status, content_checksum "
                        "FROM rag.documents WHERE source_id = %s ORDER BY document_key",
                        (source_id,),
                    )
                    docs = await cur.fetchall()
                    assert len(docs) == 3
                    doc_keys = [d[1] for d in docs]
                    assert doc_keys == [
                        "robot_01_r1/pdd-cancelamento",
                        "robot_01_r1/sdd-cancelamento",
                        "robot_01_r1/technical-overview",
                    ]
                    for doc in docs:
                        assert doc[4] == "ACTIVE"
                        assert len(doc[5]) == 64  # valid SHA-256

                    # 4. Verify persisted chunks
                    await cur.execute(
                        "SELECT count(*), min(chunk_order), max(chunk_order) "
                        "FROM rag.chunks c JOIN rag.documents d ON d.document_id = c.document_id "
                        "WHERE d.source_id = %s",
                        (source_id,),
                    )
                    chunk_stats = await cur.fetchone()
                    total_chunks = chunk_stats[0]
                    assert total_chunks == 99  # 52 (PDD) + 20 (SDD) + 27 (Tech Overview)
                    assert chunk_stats[1] == 0

                    # Verify embedding dimensions and FTS tsvector
                    await cur.execute(
                        "SELECT count(*) FROM rag.chunks c "
                        "JOIN rag.documents d ON d.document_id = c.document_id "
                        "WHERE d.source_id = %s AND (vector_dims(c.embedding) <> 384 OR c.search_vector IS NULL)",
                        (source_id,),
                    )
                    invalid_chunks_count = (await cur.fetchone())[0]
                    assert invalid_chunks_count == 0

                # 5. Test idempotency: re-running publication results in SKIPPED_UNCHANGED
                skipped_results = await publish_curated_corpus(database, embed_adapter=embed_adapter)
                assert len(skipped_results) == 3
                assert all(r.operation == "SKIPPED_UNCHANGED" for r in skipped_results)
                assert all(r.status == "SKIPPED" for r in skipped_results)
                assert all(r.chunks_published == 0 for r in skipped_results)

                # 6. Lexical smoke search
                lex_results = await repo.search_lexical_candidates("cancelamento de venda", 5, KnowledgeScope.INTERNAL)
                assert len(lex_results) >= 1
                assert all(isinstance(c, SearchCandidate) for c in lex_results)
                assert all(c.retrieval_channel == "lexical" for c in lex_results)
                assert all(c.channel_score > 0 for c in lex_results)
                assert [c.channel_rank for c in lex_results] == list(range(1, len(lex_results) + 1))

                # 7. Semantic smoke search
                query_vec = embed_adapter.embed_query("processo de cancelamento automatizado no Getnet")
                assert len(query_vec) == 384
                sem_results = await repo.search_semantic_candidates(
                    np.array(query_vec, dtype=np.float32), 5, KnowledgeScope.INTERNAL
                )
                assert len(sem_results) >= 1
                assert all(isinstance(c, SearchCandidate) for c in sem_results)
                assert all(c.retrieval_channel == "semantic" for c in sem_results)
                assert all(c.channel_score is not None and 0.0 <= c.channel_score <= 2.0 for c in sem_results)
                assert [c.channel_rank for c in sem_results] == list(range(1, len(sem_results) + 1))

        finally:
            await database.close()

    run_async(validate())
