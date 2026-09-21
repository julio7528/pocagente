"""Real transactional validation of the concrete RAG repository."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import numpy as np
import pytest

from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.models import RAGDocumentRecord, RAGSourceRecord
from apps.agent_api.app.database.repositories.rag import RAGRepository
from apps.agent_api.app.rag.models import SearchCandidate
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL integration tests are opt-in",
)


class _RollbackScenario(Exception):
    pass


def _embedding(seed: int) -> np.ndarray:
    vector = np.zeros(384, dtype=np.float32)
    vector[seed % 384] = 1.0
    vector[(seed + 17) % 384] = 0.25
    return vector


def _chunk(token: str, embedding: np.ndarray) -> dict[str, object]:
    return {
        "content": f"Synthetic integration content {token}",
        "chunk_order": 0,
        "section": "Integration validation",
        "content_type": "TEXT",
        "metadata": {"synthetic": True, "token": token},
        "embedding": embedding,
        "search_vector": f"'{token}':1 'integration':2",
    }


def test_real_rag_repository_lifecycle_and_rollback(
    real_database_config: DatabaseConfig,
) -> None:
    unique = uuid4().hex
    active_token = f"ragactive{unique}"
    inactive_token = f"raginactive{unique}"
    active_reference = f"integration/rag/active/{unique}"
    inactive_reference = f"integration/rag/inactive/{unique}"
    now = datetime.now(UTC)

    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            with pytest.raises(_RollbackScenario):
                async with database.transaction() as connection:
                    repository = RAGRepository(connection)
                    source = await repository.register_source(
                        {
                            "name": "Synthetic active integration source",
                            "source_type": "INTERNAL_DOCUMENT",
                            "origin": "INTERNAL",
                            "reference": active_reference,
                            "domain": "integration",
                            "status": "ACTIVE",
                            "priority": 1,
                            "updated_at": now,
                        }
                    )
                    assert isinstance(source, RAGSourceRecord)
                    assert await repository.get_source_by_id(source.source_id) == source
                    assert (
                        await repository.get_source_by_reference(
                            "INTERNAL", active_reference
                        )
                    ) == source

                    document = await repository.save_document(
                        {
                            "source_id": source.source_id,
                            "document_key": f"document-{unique}",
                            "title": "Synthetic integration document",
                            "document_type": "PDD",
                            "content_checksum": "a" * 64,
                            "status": "ACTIVE",
                            "last_ingested_at": now,
                            "updated_at": now,
                        }
                    )
                    assert isinstance(document, RAGDocumentRecord)
                    assert await repository.get_document_by_id(document.document_id) == document
                    assert (
                        await repository.get_document_by_key(
                            source.source_id, document.document_key
                        )
                    ) == document
                    assert not await repository.document_checksum_changed(
                        document.document_id, "a" * 64
                    )
                    assert await repository.document_checksum_changed(
                        document.document_id, "b" * 64
                    )

                    updated_document = await repository.save_document(
                        {
                            "source_id": source.source_id,
                            "document_key": document.document_key,
                            "title": "Synthetic integration document updated",
                            "document_type": "PDD",
                            "content_checksum": "b" * 64,
                            "status": "ACTIVE",
                            "last_ingested_at": now,
                            "updated_at": now,
                        }
                    )
                    assert updated_document.document_id == document.document_id

                    ingestion_run_id = await repository.start_ingestion_run(
                        source.source_id, document.document_id, "REINGEST"
                    )
                    active_embedding = _embedding(11)
                    await repository.replace_document_chunks(
                        document.document_id,
                        [_chunk(active_token, active_embedding)],
                    )

                    lexical = await repository.search_lexical_candidates(
                        active_token, 10
                    )
                    assert lexical
                    assert all(isinstance(item, SearchCandidate) for item in lexical)
                    assert any(
                        item.chunk.document_id == document.document_id
                        and item.retrieval_channel == "lexical"
                        for item in lexical
                    )

                    semantic = await repository.search_semantic_candidates(
                        active_embedding, 10
                    )
                    assert semantic
                    assert all(isinstance(item, SearchCandidate) for item in semantic)
                    assert any(
                        item.chunk.document_id == document.document_id
                        and item.retrieval_channel == "semantic"
                        for item in semantic
                    )

                    await repository.finish_ingestion_run(
                        ingestion_run_id,
                        status="SUCCESS",
                        finished_at=datetime.now(UTC),
                        chunks_created=1,
                        result_message="Synthetic integration publication completed",
                    )

                    inactive_source = await repository.register_source(
                        {
                            "name": "Synthetic inactive integration source",
                            "source_type": "INTERNAL_DOCUMENT",
                            "origin": "INTERNAL",
                            "reference": inactive_reference,
                            "status": "INACTIVE",
                            "priority": 0,
                            "updated_at": now,
                        }
                    )
                    inactive_document = await repository.save_document(
                        {
                            "source_id": inactive_source.source_id,
                            "document_key": f"inactive-{unique}",
                            "title": "Synthetic inactive document",
                            "document_type": "PDD",
                            "content_checksum": "c" * 64,
                            "status": "ACTIVE",
                            "last_ingested_at": now,
                            "updated_at": now,
                        }
                    )
                    await repository.replace_document_chunks(
                        inactive_document.document_id,
                        [_chunk(inactive_token, _embedding(37))],
                    )
                    assert (
                        await repository.search_lexical_candidates(inactive_token, 10)
                    ) == ()

                    inactive_document = await repository.save_document(
                        {
                            "source_id": source.source_id,
                            "document_key": f"document-inactive-{unique}",
                            "title": "Synthetic inactive document state",
                            "document_type": "PDD",
                            "content_checksum": "d" * 64,
                            "status": "INACTIVE",
                            "last_ingested_at": now,
                            "updated_at": now,
                        }
                    )
                    document_inactive_token = f"docinactive{unique}"
                    await repository.replace_document_chunks(
                        inactive_document.document_id,
                        [_chunk(document_inactive_token, _embedding(71))],
                    )
                    assert (
                        await repository.search_lexical_candidates(
                            document_inactive_token, 10
                        )
                    ) == ()
                    raise _RollbackScenario()

            async with database.connection() as connection:
                repository = RAGRepository(connection)
                assert (
                    await repository.get_source_by_reference(
                        "INTERNAL", active_reference
                    )
                    is None
                )
                assert (
                    await repository.get_source_by_reference(
                        "INTERNAL", inactive_reference
                    )
                    is None
                )
        finally:
            await database.close()

    run_async(validate())
