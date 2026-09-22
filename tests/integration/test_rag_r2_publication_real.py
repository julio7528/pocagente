"""Opt-in real local PostgreSQL validation for the separate R2 corpus."""

from __future__ import annotations

import os

import numpy as np
import pytest

from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.repositories.rag import RAGRepository
from apps.agent_api.app.rag.embeddings.fastembed import FastEmbedAdapter
from apps.agent_api.app.rag.publication.cli import (
    INTERNAL_SOURCE_CONFIG,
    R2_CURATED_DOCUMENTS,
    R2_INTERNAL_SOURCE_CONFIG,
    publish_r2_curated_corpus,
)
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL integration tests are opt-in",
)


def test_real_r2_publication_provenance_and_idempotency(
    real_database_config: DatabaseConfig,
) -> None:
    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        adapter = FastEmbedAdapter()
        try:
            first = await publish_r2_curated_corpus(database, embed_adapter=adapter)
            assert len(first) == 3
            assert all(result.operation in {"INGEST", "REINGEST", "SKIPPED_UNCHANGED"} for result in first)
            assert {result.document_key for result in first} == {
                item["key"] for item in R2_CURATED_DOCUMENTS
            }

            async with database.connection() as connection:
                repository = RAGRepository(connection)
                r2 = await repository.get_source_by_reference(
                    R2_INTERNAL_SOURCE_CONFIG["origin"], R2_INTERNAL_SOURCE_CONFIG["reference"]
                )
                r1 = await repository.get_source_by_reference(
                    INTERNAL_SOURCE_CONFIG["origin"], INTERNAL_SOURCE_CONFIG["reference"]
                )
                assert r2 is not None and r2.status == "ACTIVE" and r2.priority == 10
                assert r1 is not None and r1.status == "ACTIVE" and r1.priority == 10

                async with connection.cursor() as cursor:
                    await cursor.execute(
                        "SELECT document_key, document_type, status "
                        "FROM rag.documents WHERE source_id = %s ORDER BY document_key",
                        (r2.source_id,),
                    )
                    documents = await cursor.fetchall()
                    assert documents == [
                        ("robot_02_r2/pdd-cancelamento", "PDD", "ACTIVE"),
                        ("robot_02_r2/sdd-cancelamento", "SDD", "ACTIVE"),
                        ("robot_02_r2/technical-overview", "TECHNICAL_OVERVIEW", "ACTIVE"),
                    ]
                    await cursor.execute(
                        "SELECT count(*) FROM rag.chunks c "
                        "JOIN rag.documents d ON d.document_id = c.document_id "
                        "WHERE d.source_id = %s AND (c.embedding IS NULL OR vector_dims(c.embedding) <> 384 "
                        "OR c.search_vector IS NULL)",
                        (r2.source_id,),
                    )
                    assert (await cursor.fetchone())[0] == 0

                for query in (
                    "acompanhamento de protocolos pendentes",
                    "consulta da Retaguarda",
                    "download do arquivo de retorno",
                    "Robot 02 R2",
                ):
                    lexical = await repository.search_lexical_candidates(query, 10)
                    semantic = await repository.search_semantic_candidates(
                        np.asarray(adapter.embed_query(query), dtype=np.float32), 10
                    )
                    candidates = lexical + semantic
                    assert candidates, query
                    assert any(
                        item.provenance.source_reference == R2_INTERNAL_SOURCE_CONFIG["reference"]
                        and item.provenance.document_key.startswith("robot_02_r2/")
                        for item in candidates
                    ), query

            second = await publish_r2_curated_corpus(database, embed_adapter=adapter)
            assert len(second) == 3
            assert all(result.operation == "SKIPPED_UNCHANGED" for result in second)
            assert all(result.chunks_published == 0 for result in second)
        finally:
            await database.close()

    run_async(validate())
