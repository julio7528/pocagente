"""Real PostgreSQL integration tests for atomic RAG publication."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import numpy as np
import pytest

from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.repositories.rag import RAGRepository
from apps.agent_api.app.rag.embeddings.fastembed import FastEmbedAdapter
from apps.agent_api.app.rag.ingestion.models import PreparedChunk, PreparedDocument, PreparedIngestion
from apps.agent_api.app.rag.models import SearchCandidate, SourceMetadata
from apps.agent_api.app.rag.scope import KnowledgeScope
from apps.agent_api.app.rag.publication.service import RAGPublicationService
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL integration tests are opt-in",
)


class _RollbackScenario(Exception):
    pass


def _create_prepared_ingestion(
    document_key: str,
    title: str,
    checksum: str,
    operation: str = "INGEST",
    chunks_content: tuple[str, ...] = ("Conteúdo de teste para publicação Getnet.",),
) -> PreparedIngestion:
    doc_metadata = SourceMetadata(
        source_id="test-source",
        document_id=document_key,
        title=title,
        source_type="INTERNAL_DOCUMENT",
        approved=True,
    )
    doc = PreparedDocument(
        document_id=document_key,
        metadata=doc_metadata,
        normalized_content="\n\n".join(chunks_content),
        content_checksum=checksum,
        database_source_type="INTERNAL_DOCUMENT",
        database_origin="INTERNAL",
    )
    if operation == "SKIPPED_UNCHANGED":
        return PreparedIngestion(operation="SKIPPED_UNCHANGED", document=doc, chunks=())

    chunks = tuple(
        PreparedChunk(
            content=text,
            chunk_order=i,
            section=f"Seção {i + 1}",
            boundary_type="section",
            content_type="TEXT",
            metadata={
                "source_id": "test-source",
                "document_id": document_key,
                "document_key": document_key,
                "section": f"Seção {i + 1}",
                "chunk_order": i,
                "content_checksum": checksum,
                "boundary_type": "section",
                "content_type": "TEXT",
            },
        )
        for i, text in enumerate(chunks_content)
    )
    return PreparedIngestion(operation=operation, document=doc, chunks=chunks)


def test_real_rag_publication_lifecycle_ingest_skipped_reingest(
    real_database_config: DatabaseConfig,
) -> None:
    unique = uuid4().hex
    reference = f"integration/publication/{unique}"
    doc_key = f"doc-pub-{unique}"
    now = datetime.now(UTC)

    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        embed_adapter = FastEmbedAdapter()
        try:
            # 1. Setup Source in DB
            async with database.transaction() as conn:
                repo = RAGRepository(conn)
                source = await repo.register_source(
                    {
                        "name": f"Integration Publication Source {unique}",
                        "source_type": "INTERNAL_DOCUMENT",
                        "origin": "INTERNAL",
                        "reference": reference,
                        "domain": "cancellation",
                        "status": "ACTIVE",
                        "priority": 1,
                        "updated_at": now,
                    }
                )
                source_id = source.source_id

            service = RAGPublicationService(database, embed_adapter=embed_adapter)

            # 2. Stage: INGEST
            checksum_v1 = "1" * 64
            token_v1 = f"cancelamentorpa{unique}"
            content_v1 = f"Processo de cancelamento automatizado {token_v1} no Getnet."
            prep_v1 = _create_prepared_ingestion(
                document_key=doc_key,
                title="Manual de Cancelamento",
                checksum=checksum_v1,
                operation="INGEST",
                chunks_content=(content_v1,),
            )

            result_v1 = await service.publish(prep_v1, source_id)
            assert result_v1.operation == "INGEST"
            assert result_v1.status == "SUCCESS"
            assert result_v1.source_id == source_id
            assert result_v1.document_key == doc_key
            assert result_v1.chunks_published == 1
            assert result_v1.ingestion_run_id > 0

            # Verify persisted DB state after INGEST
            async with database.connection() as conn:
                repo = RAGRepository(conn)
                doc_record = await repo.get_document_by_key(source_id, doc_key)
                assert doc_record is not None
                assert doc_record.status == "ACTIVE"
                assert doc_record.content_checksum == checksum_v1

                # Lexical search smoke test
                lex_results = await repo.search_lexical_candidates(token_v1, 10, KnowledgeScope.INTERNAL)
                assert len(lex_results) >= 1
                assert isinstance(lex_results[0], SearchCandidate)
                assert lex_results[0].chunk.document_id == doc_record.document_id
                assert lex_results[0].retrieval_channel == "lexical"
                assert lex_results[0].channel_score > 0

                # Semantic search smoke test
                query_emb = embed_adapter.embed_query(token_v1)
                assert len(query_emb) == 384
                sem_results = await repo.search_semantic_candidates(
                    np.array(query_emb, dtype=np.float32), 10, KnowledgeScope.INTERNAL
                )
                assert len(sem_results) >= 1
                assert isinstance(sem_results[0], SearchCandidate)
                assert sem_results[0].chunk.document_id == doc_record.document_id
                assert sem_results[0].retrieval_channel == "semantic"

            # 3. Stage: SKIPPED_UNCHANGED
            prep_skipped = _create_prepared_ingestion(
                document_key=doc_key,
                title="Manual de Cancelamento",
                checksum=checksum_v1,
                operation="SKIPPED_UNCHANGED",
            )
            result_skipped = await service.publish(prep_skipped, source_id)
            assert result_skipped.operation == "SKIPPED_UNCHANGED"
            assert result_skipped.status == "SKIPPED"
            assert result_skipped.chunks_published == 0

            # Verify chunk count remains 1 and unchanged
            async with database.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT count(*) FROM rag.chunks WHERE document_id = %s",
                        (doc_record.document_id,),
                    )
                    count_row = await cur.fetchone()
                    assert count_row[0] == 1

            # 4. Stage: REINGEST
            checksum_v2 = "2" * 64
            token_v2 = f"estornorpa{unique}"
            content_v2_1 = f"Novo fluxo de estorno {token_v2} etapa um."
            content_v2_2 = f"Novo fluxo de estorno {token_v2} etapa dois."
            prep_v2 = _create_prepared_ingestion(
                document_key=doc_key,
                title="Manual de Cancelamento Atualizado",
                checksum=checksum_v2,
                operation="REINGEST",
                chunks_content=(content_v2_1, content_v2_2),
            )

            result_v2 = await service.publish(prep_v2, source_id)
            assert result_v2.operation == "REINGEST"
            assert result_v2.status == "SUCCESS"
            assert result_v2.chunks_published == 2

            # Verify chunks replaced atomically
            async with database.connection() as conn:
                repo = RAGRepository(conn)
                doc_record_v2 = await repo.get_document_by_key(source_id, doc_key)
                assert doc_record_v2 is not None
                assert doc_record_v2.content_checksum == checksum_v2

                # Verify exactly 2 chunks now exist for this document
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT chunk_order, content, vector_dims(embedding) FROM rag.chunks WHERE document_id = %s ORDER BY chunk_order",
                        (doc_record.document_id,),
                    )
                    rows = await cur.fetchall()
                    assert len(rows) == 2
                    assert rows[0][0] == 0
                    assert rows[0][2] == 384
                    assert rows[1][0] == 1
                    assert rows[1][2] == 384

                # Lexical search for new token
                lex_v2 = await repo.search_lexical_candidates(token_v2, 10, KnowledgeScope.INTERNAL)
                assert len(lex_v2) >= 1
                assert any(c.chunk.document_id == doc_record.document_id for c in lex_v2)

        finally:
            # Clean up test source and cascaded documents/chunks
            async with database.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "DELETE FROM rag.ingestion_runs WHERE source_id IN (SELECT source_id FROM rag.sources WHERE reference = %s)",
                        (reference,),
                    )
                    await cur.execute(
                        "DELETE FROM rag.documents WHERE source_id IN (SELECT source_id FROM rag.sources WHERE reference = %s)",
                        (reference,),
                    )
                    await cur.execute("DELETE FROM rag.sources WHERE reference = %s", (reference,))
            await database.close()

    run_async(validate())


def test_real_rag_publication_atomic_rollback_on_failure(
    real_database_config: DatabaseConfig,
) -> None:
    unique = uuid4().hex
    reference = f"integration/publication-rollback/{unique}"
    doc_key = f"doc-rollback-{unique}"
    now = datetime.now(UTC)

    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            # Setup Source
            async with database.transaction() as conn:
                repo = RAGRepository(conn)
                source = await repo.register_source(
                    {
                        "name": f"Integration Rollback Source {unique}",
                        "source_type": "INTERNAL_DOCUMENT",
                        "origin": "INTERNAL",
                        "reference": reference,
                        "domain": "cancellation",
                        "status": "ACTIVE",
                        "priority": 1,
                        "updated_at": now,
                    }
                )
                source_id = source.source_id

            service = RAGPublicationService(database)

            # 1. Publish initial valid state
            checksum_v1 = "1" * 64
            token_v1 = f"validchunk{unique}"
            prep_v1 = _create_prepared_ingestion(
                document_key=doc_key,
                title="Doc Inicial",
                checksum=checksum_v1,
                operation="INGEST",
                chunks_content=(f"Conteúdo estável {token_v1}",),
            )
            result_v1 = await service.publish(prep_v1, source_id)
            assert result_v1.status == "SUCCESS"

            # 2. Attempt invalid publication (e.g. non-existent source_id or corrupted chunk)
            bad_source_id = uuid4()
            with pytest.raises(ValueError, match="Source with id .* does not exist"):
                await service.publish(prep_v1, bad_source_id)

            # Verify original document and chunks are intact
            async with database.connection() as conn:
                repo = RAGRepository(conn)
                doc = await repo.get_document_by_key(source_id, doc_key)
                assert doc is not None
                assert doc.content_checksum == checksum_v1
                lex = await repo.search_lexical_candidates(token_v1, 5, KnowledgeScope.INTERNAL)
                assert len(lex) >= 1

        finally:
            async with database.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "DELETE FROM rag.ingestion_runs WHERE source_id IN (SELECT source_id FROM rag.sources WHERE reference = %s)",
                        (reference,),
                    )
                    await cur.execute(
                        "DELETE FROM rag.documents WHERE source_id IN (SELECT source_id FROM rag.sources WHERE reference = %s)",
                        (reference,),
                    )
                    await cur.execute("DELETE FROM rag.sources WHERE reference = %s", (reference,))
            await database.close()

    run_async(validate())


def test_real_rag_publication_pre_transaction_embedding_failure(
    real_database_config: DatabaseConfig,
) -> None:
    unique = uuid4().hex
    reference = f"integration/publication-pre-embed-fail/{unique}"
    doc_key = f"doc-pre-fail-{unique}"
    now = datetime.now(UTC)

    class FailingEmbedAdapter(FastEmbedAdapter):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            raise RuntimeError("Synthetic FastEmbed embedding inference failure")

    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            async with database.transaction() as conn:
                repo = RAGRepository(conn)
                source = await repo.register_source(
                    {
                        "name": f"Integration Pre-Fail Source {unique}",
                        "source_type": "INTERNAL_DOCUMENT",
                        "origin": "INTERNAL",
                        "reference": reference,
                        "domain": "cancellation",
                        "status": "ACTIVE",
                        "priority": 1,
                        "updated_at": now,
                    }
                )
                source_id = source.source_id

            service = RAGPublicationService(database, embed_adapter=FailingEmbedAdapter())
            prep = _create_prepared_ingestion(
                document_key=doc_key,
                title="Doc Pre Fail",
                checksum="f" * 64,
                operation="INGEST",
                chunks_content=("Conteúdo de teste para falha pré-transacional.",),
            )

            with pytest.raises(RuntimeError, match="Synthetic FastEmbed embedding inference failure"):
                await service.publish(prep, source_id)

            # Verify no ingestion run, no document, no chunk was created
            async with database.connection() as conn:
                repo = RAGRepository(conn)
                doc = await repo.get_document_by_key(source_id, doc_key)
                assert doc is None
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT count(*) FROM rag.ingestion_runs WHERE source_id = %s",
                        (source_id,),
                    )
                    run_count = (await cur.fetchone())[0]
                    assert run_count == 0

        finally:
            async with database.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "DELETE FROM rag.ingestion_runs WHERE source_id IN (SELECT source_id FROM rag.sources WHERE reference = %s)",
                        (reference,),
                    )
                    await cur.execute(
                        "DELETE FROM rag.documents WHERE source_id IN (SELECT source_id FROM rag.sources WHERE reference = %s)",
                        (reference,),
                    )
                    await cur.execute("DELETE FROM rag.sources WHERE reference = %s", (reference,))
            await database.close()

    run_async(validate())


def test_real_rag_publication_post_mutation_atomic_rollback(
    real_database_config: DatabaseConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unique = uuid4().hex
    reference = f"integration/publication-post-mutation-rollback/{unique}"
    doc_key = f"doc-post-mutation-{unique}"
    now = datetime.now(UTC)

    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            # Setup Source
            async with database.transaction() as conn:
                repo = RAGRepository(conn)
                source = await repo.register_source(
                    {
                        "name": f"Integration Post-Mutation Source {unique}",
                        "source_type": "INTERNAL_DOCUMENT",
                        "origin": "INTERNAL",
                        "reference": reference,
                        "domain": "cancellation",
                        "status": "ACTIVE",
                        "priority": 1,
                        "updated_at": now,
                    }
                )
                source_id = source.source_id

            service = RAGPublicationService(database)

            # 1. Publish valid document V1
            checksum_v1 = "1" * 64
            token_v1 = f"v1token{unique}"
            content_v1 = f"Conteúdo original da versão um {token_v1} para publicação estável."
            prep_v1 = _create_prepared_ingestion(
                document_key=doc_key,
                title="Documento Versão Um",
                checksum=checksum_v1,
                operation="INGEST",
                chunks_content=(content_v1,),
            )
            result_v1 = await service.publish(prep_v1, source_id)
            assert result_v1.status == "SUCCESS"
            assert result_v1.chunks_published == 1

            # 2. Confirm V1 checksum and chunk are retrievable
            async with database.connection() as conn:
                repo = RAGRepository(conn)
                doc_v1 = await repo.get_document_by_key(source_id, doc_key)
                assert doc_v1 is not None
                assert doc_v1.content_checksum == checksum_v1
                assert doc_v1.status == "ACTIVE"

                lex_v1 = await repo.search_lexical_candidates(token_v1, 5, KnowledgeScope.INTERNAL)
                assert len(lex_v1) >= 1
                assert lex_v1[0].chunk.document_id == doc_v1.document_id

            # 3. Start REINGEST V2
            checksum_v2 = "2" * 64
            token_v2 = f"v2token{unique}"
            content_v2 = f"Conteúdo atualizado da versão dois {token_v2} em reingestão."
            prep_v2 = _create_prepared_ingestion(
                document_key=doc_key,
                title="Documento Versão Dois",
                checksum=checksum_v2,
                operation="REINGEST",
                chunks_content=(content_v2,),
            )

            # 4. Force a controlled failure after save_document() and during replace_document_chunks()
            original_replace = RAGRepository.replace_document_chunks

            async def failing_replace(self: RAGRepository, document_id: UUID, chunks: object) -> None:
                await original_replace(self, document_id, chunks)
                raise RuntimeError("Controlled post-mutation failure during publication transaction")

            monkeypatch.setattr(RAGRepository, "replace_document_chunks", failing_replace)

            with pytest.raises(RuntimeError, match="Controlled post-mutation failure"):
                await service.publish(prep_v2, source_id)

            monkeypatch.undo()

            # 5 & 6. Verify transaction rolled back and previous retrievable state is intact
            async with database.connection() as conn:
                repo = RAGRepository(conn)
                doc_after = await repo.get_document_by_key(source_id, doc_key)
                assert doc_after is not None

                # - original V1 checksum remains
                assert doc_after.content_checksum == checksum_v1
                # - original title remains
                assert doc_after.title == "Documento Versão Um"
                # - document remains ACTIVE
                assert doc_after.status == "ACTIVE"

                # - original V1 chunks remain and V2 chunks do not remain
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT chunk_order, content FROM rag.chunks WHERE document_id = %s",
                        (doc_after.document_id,),
                    )
                    chunk_rows = await cur.fetchall()
                    assert len(chunk_rows) == 1
                    assert token_v1 in chunk_rows[0][1]
                    assert token_v2 not in chunk_rows[0][1]

                # - original content is still retrievable
                lex_after = await repo.search_lexical_candidates(token_v1, 5, KnowledgeScope.INTERNAL)
                assert len(lex_after) >= 1
                assert lex_after[0].chunk.document_id == doc_after.document_id

                # - V2 content was never committed
                lex_v2 = await repo.search_lexical_candidates(token_v2, 5, KnowledgeScope.INTERNAL)
                assert len(lex_v2) == 0

        finally:
            async with database.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "DELETE FROM rag.ingestion_runs WHERE source_id IN (SELECT source_id FROM rag.sources WHERE reference = %s)",
                        (reference,),
                    )
                    await cur.execute(
                        "DELETE FROM rag.documents WHERE source_id IN (SELECT source_id FROM rag.sources WHERE reference = %s)",
                        (reference,),
                    )
                    await cur.execute("DELETE FROM rag.sources WHERE reference = %s", (reference,))
            await database.close()

    run_async(validate())
