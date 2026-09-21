"""Unit tests for the connection-bound RAG repository."""

import inspect
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from apps.agent_api.app.database.models import RAGDocumentRecord, RAGSourceRecord
from apps.agent_api.app.database.repositories.rag import RAGRepository
from apps.agent_api.app.database.repositories import rag as rag_module
from apps.agent_api.app.rag.models import SearchCandidate
from tests.repository_fakes import FakeConnection, normalized_sql


def _source_row(source_id: UUID) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "source_id": source_id,
        "name": "Manual",
        "source_type": "INTERNAL_DOCUMENT",
        "origin": "INTERNAL",
        "reference": "pdd",
        "domain": None,
        "status": "ACTIVE",
        "priority": 1,
        "created_at": now,
        "updated_at": now,
    }


def _document_row(document_id: UUID, source_id: UUID | None = None) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "document_id": document_id,
        "source_id": source_id or uuid4(),
        "document_key": "manual",
        "title": "Manual Doc",
        "document_type": "PDD",
        "content_checksum": "a" * 64,
        "status": "ACTIVE",
        "last_ingested_at": now,
        "created_at": now,
        "updated_at": now,
    }


def _candidate_row(chunk_id: int, channel: str) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "chunk_id": chunk_id,
        "document_id": uuid4(),
        "content": "chunk text",
        "chunk_order": 0,
        "section": "Sec 1",
        "content_type": "TEXT",
        "metadata": {},
        "created_at": now,
        "source_id": uuid4(),
        "source_name": "Source 1",
        "source_type": "INTERNAL_DOCUMENT",
        "origin": "INTERNAL",
        "source_reference": "REF-1",
        "domain": None,
        "priority": 0,
        "document_key": "doc-1",
        "title": "Doc 1",
        "document_type": "PDD",
        "content_checksum": None,
        "last_ingested_at": None,
        "retrieval_channel": channel,
        "channel_rank": 1,
        "channel_score": 0.5,
    }


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_rag_repository_retains_injected_connection_without_side_effects() -> None:
    connection = MagicMock()

    repository = RAGRepository(connection)

    assert repository._connection is connection
    connection.cursor.assert_not_called()
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_not_called()


def test_rag_repository_foundation_has_no_infrastructure_or_cross_schema_access() -> None:
    source = inspect.getsource(rag_module)

    for forbidden in (
        "AsyncConnectionPool",
        "PostgresDatabase(",
        "AsyncConnection(",
        "ops.",
        "audit.",
        ".commit(",
        ".rollback(",
    ):
        assert forbidden not in source


@pytest.mark.anyio
async def test_source_lookups_use_approved_keys_and_handle_missing_rows() -> None:
    source_id = uuid4()
    row = _source_row(source_id)
    connection = FakeConnection(row, None)
    repository = RAGRepository(connection)

    result = await repository.get_source_by_id(source_id)
    assert isinstance(result, RAGSourceRecord)
    assert result.source_id == source_id
    assert await repository.get_source_by_reference("INTERNAL", "missing") is None

    first, second = connection.statements
    assert "FROM rag.sources" in normalized_sql(first)
    assert "WHERE source_id = %s" in normalized_sql(first)
    assert first.parameters == (source_id,)
    assert "WHERE origin = %s AND reference = %s" in normalized_sql(second)
    assert second.parameters == ("INTERNAL", "missing")


@pytest.mark.anyio
async def test_register_source_uses_allowlisted_fields_and_database_uuid_default() -> None:
    now = datetime.now(UTC)
    source_id = uuid4()
    returned = _source_row(source_id)
    connection = FakeConnection(returned)
    repository = RAGRepository(connection)
    payload = {
        "name": "PDD",
        "source_type": "INTERNAL_DOCUMENT",
        "origin": "INTERNAL",
        "reference": "PDD/Getnet",
        "status": "ACTIVE",
        "updated_at": now,
    }

    result = await repository.register_source(payload)
    assert isinstance(result, RAGSourceRecord)
    assert result.source_id == source_id

    statement = connection.statements[0]
    query = normalized_sql(statement)
    assert query.startswith("INSERT INTO rag.sources")
    assert "RETURNING" in query
    assert "source_id" not in query.partition("VALUES")[0]
    assert statement.parameters == tuple(payload.values())
    assert "ops." not in query and "audit." not in query


@pytest.mark.anyio
async def test_register_source_rejects_unknown_or_missing_fields_before_sql() -> None:
    connection = FakeConnection()
    repository = RAGRepository(connection)

    with pytest.raises(ValueError, match="Unsupported fields"):
        await repository.register_source({"name": "x", "password": "secret"})
    with pytest.raises(ValueError, match="Missing required fields"):
        await repository.register_source({"name": "x"})

    assert connection.statements == []


@pytest.mark.anyio
async def test_document_lookups_use_pk_and_stable_unique_key() -> None:
    document_id = uuid4()
    source_id = uuid4()
    row = _document_row(document_id, source_id)
    connection = FakeConnection(row, row)
    repository = RAGRepository(connection)

    by_id_result = await repository.get_document_by_id(document_id)
    assert isinstance(by_id_result, RAGDocumentRecord)
    assert by_id_result.document_id == document_id

    by_key_result = await repository.get_document_by_key(source_id, "manual")
    assert isinstance(by_key_result, RAGDocumentRecord)
    assert by_key_result.document_id == document_id

    by_id, by_key = connection.statements
    assert "FROM rag.documents WHERE document_id = %s" in normalized_sql(by_id)
    assert by_id.parameters == (document_id,)
    assert "WHERE source_id = %s AND document_key = %s" in normalized_sql(by_key)
    assert by_key.parameters == (source_id, "manual")


@pytest.mark.anyio
async def test_checksum_change_detection_treats_missing_or_inactive_as_changed() -> None:
    document_id = uuid4()
    checksum = "a" * 64
    connection = FakeConnection({"changed": False}, {"changed": True}, None)
    repository = RAGRepository(connection)

    assert await repository.document_checksum_changed(document_id, checksum) is False
    assert await repository.document_checksum_changed(document_id, checksum) is True
    assert await repository.document_checksum_changed(document_id, checksum) is True
    assert all(statement.parameters == (checksum, document_id) for statement in connection.statements)


@pytest.mark.anyio
async def test_save_document_upserts_on_stable_identity_without_mutating_ids() -> None:
    source_id = uuid4()
    now = datetime.now(UTC)
    payload = {
        "source_id": source_id,
        "document_key": "approved-key",
        "title": "Current title",
        "document_type": "PDD",
        "content_checksum": "b" * 64,
        "status": "ACTIVE",
        "last_ingested_at": now,
        "updated_at": now,
    }
    doc_id = uuid4()
    returned = {
        "document_id": doc_id,
        **payload,
        "created_at": now,
    }
    connection = FakeConnection(returned)
    repository = RAGRepository(connection)

    result = await repository.save_document(payload)
    assert isinstance(result, RAGDocumentRecord)
    assert result.document_id == doc_id

    statement = connection.statements[0]
    query = normalized_sql(statement)
    assert "INSERT INTO rag.documents" in query
    assert "ON CONFLICT (source_id, document_key) DO UPDATE" in query
    assert "document_id = EXCLUDED.document_id" not in query
    assert "source_id = EXCLUDED.source_id" not in query
    assert "document_key = EXCLUDED.document_key" not in query
    assert statement.parameters == tuple(payload.values())


@pytest.mark.anyio
async def test_save_document_rejects_unknown_fields_before_sql() -> None:
    connection = FakeConnection()
    repository = RAGRepository(connection)

    with pytest.raises(ValueError, match="Unsupported fields"):
        await repository.save_document({"source_id": uuid4(), "title": "x", "version": 2})

    assert connection.statements == []


def _chunk(order: int) -> dict[str, object]:
    return {
        "content": f"chunk {order}",
        "chunk_order": order,
        "section": "Section",
        "content_type": "TEXT",
        "metadata": {"page": order + 1},
        "embedding": [0.0] * 384,
        "search_vector": "'chunk':1",
    }


@pytest.mark.anyio
async def test_empty_chunk_replacement_is_rejected_before_delete() -> None:
    connection = FakeConnection()
    repository = RAGRepository(connection)

    with pytest.raises(ValueError, match="cannot be empty"):
        await repository.replace_document_chunks(uuid4(), [])

    assert connection.statements == []


@pytest.mark.anyio
async def test_chunk_replacement_deletes_one_document_then_inserts_complete_set() -> None:
    document_id = uuid4()
    connection = FakeConnection()
    repository = RAGRepository(connection)

    await repository.replace_document_chunks(document_id, [_chunk(0), _chunk(1)])

    delete, insert = connection.statements
    assert normalized_sql(delete) == "DELETE FROM rag.chunks WHERE document_id = %s"
    assert delete.parameters == (document_id,)
    assert insert.many is True
    assert "INSERT INTO rag.chunks" in normalized_sql(insert)
    rows = list(insert.parameters)
    assert len(rows) == 2
    assert all(row[0] == document_id for row in rows)
    assert all(len(row[6]) == 384 for row in rows)
    assert all(row[5].obj == {"page": index + 1} for index, row in enumerate(rows))
    connection.commit.assert_not_awaited()
    connection.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_chunk_replacement_rejects_unknown_fields_and_non_object_metadata() -> None:
    connection = FakeConnection()
    repository = RAGRepository(connection)
    invalid = _chunk(0)
    invalid["document_id"] = uuid4()

    with pytest.raises(ValueError, match="Unsupported fields"):
        await repository.replace_document_chunks(uuid4(), [invalid])

    invalid = _chunk(0)
    invalid["metadata"] = ["not", "an", "object"]
    with pytest.raises(ValueError, match="JSON object"):
        await repository.replace_document_chunks(uuid4(), [invalid])

    assert connection.statements == []


@pytest.mark.anyio
async def test_ingestion_run_start_uses_running_defaults_and_returns_identity() -> None:
    source_id = uuid4()
    document_id = uuid4()
    connection = FakeConnection({"ingestion_run_id": 41})
    repository = RAGRepository(connection)

    assert await repository.start_ingestion_run(source_id, document_id, "REINGEST") == 41

    statement = connection.statements[0]
    query = normalized_sql(statement)
    assert "INSERT INTO rag.ingestion_runs (source_id, document_id, operation)" in query
    assert "status" not in query.partition("VALUES")[0]
    assert "RETURNING ingestion_run_id" in query
    assert statement.parameters == (source_id, document_id, "REINGEST")


@pytest.mark.anyio
async def test_ingestion_run_finish_uses_terminal_values_without_transaction_control() -> None:
    finished_at = datetime.now(UTC)
    connection = FakeConnection()
    repository = RAGRepository(connection)

    await repository.finish_ingestion_run(
        41,
        status="SUCCESS",
        finished_at=finished_at,
        chunks_created=2,
        result_message="published",
    )

    statement = connection.statements[0]
    assert "UPDATE rag.ingestion_runs" in normalized_sql(statement)
    assert "WHERE ingestion_run_id = %s" in normalized_sql(statement)
    assert statement.parameters == ("SUCCESS", finished_at, 2, "published", 41)
    connection.commit.assert_not_awaited()
    connection.rollback.assert_not_awaited()


@pytest.mark.anyio
async def test_ingestion_run_rejects_invalid_lifecycle_before_sql() -> None:
    connection = FakeConnection()
    repository = RAGRepository(connection)

    with pytest.raises(ValueError, match="operation"):
        await repository.start_ingestion_run(uuid4(), None, "UNKNOWN")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="at least one"):
        await repository.finish_ingestion_run(
            1,
            status="SUCCESS",
            finished_at=datetime.now(UTC),
            chunks_created=0,
            result_message=None,
        )
    with pytest.raises(ValueError, match="cannot commit"):
        await repository.finish_ingestion_run(
            1,
            status="ERROR",
            finished_at=datetime.now(UTC),
            chunks_created=1,
            result_message="sanitized",
        )

    assert connection.statements == []


@pytest.mark.anyio
async def test_lexical_retrieval_uses_approved_fts_and_active_filters() -> None:
    rows = [_candidate_row(1, "lexical")]
    connection = FakeConnection(rows)
    repository = RAGRepository(connection)

    candidates = await repository.search_lexical_candidates("Falha R1", 10)
    assert len(candidates) == 1
    assert isinstance(candidates[0], SearchCandidate)
    assert candidates[0].chunk.chunk_id == 1
    assert candidates[0].retrieval_channel == "lexical"
    assert candidates[0].channel_rank == 1

    statement = connection.statements[0]
    query = normalized_sql(statement)
    assert "websearch_to_tsquery('portuguese', %s)" in query
    assert "websearch_to_tsquery('simple', %s)" in query
    assert "ts_rank_cd(c.search_vector, q.value)" in query
    assert "FROM rag.chunks AS c" in query
    assert "JOIN rag.documents AS d" in query
    assert "JOIN rag.sources AS s" in query
    assert "d.status = 'ACTIVE'" in query
    assert "s.status = 'ACTIVE'" in query
    assert "ORDER BY channel_score DESC, chunk_id ASC" in query
    assert "LIMIT %s" in query
    assert statement.parameters == ("Falha R1", "Falha R1", 10)
    assert "ops." not in query and "audit." not in query
    assert "RRF" not in query


@pytest.mark.anyio
async def test_lexical_retrieval_rejects_blank_query_or_unbounded_limit() -> None:
    connection = FakeConnection()
    repository = RAGRepository(connection)

    with pytest.raises(ValueError, match="blank"):
        await repository.search_lexical_candidates("   ", 5)
    with pytest.raises(ValueError, match="between 1 and 10"):
        await repository.search_lexical_candidates("query", 11)

    assert connection.statements == []


@pytest.mark.anyio
async def test_semantic_retrieval_uses_exact_cosine_and_active_filters() -> None:
    embedding = [0.01] * 384
    rows = [_candidate_row(9, "semantic")]
    connection = FakeConnection(rows)
    repository = RAGRepository(connection)

    candidates = await repository.search_semantic_candidates(embedding, 7)
    assert len(candidates) == 1
    assert isinstance(candidates[0], SearchCandidate)
    assert candidates[0].chunk.chunk_id == 9
    assert candidates[0].retrieval_channel == "semantic"
    assert candidates[0].channel_rank == 1

    statement = connection.statements[0]
    query = normalized_sql(statement)
    assert "c.embedding <=> %s AS channel_score" in query
    assert "ORDER BY channel_score ASC, chunk_id ASC" in query
    assert "d.status = 'ACTIVE'" in query
    assert "s.status = 'ACTIVE'" in query
    assert statement.parameters[0].to_list() == pytest.approx(embedding)
    assert statement.parameters[1] == 7
    for forbidden in ("hnsw", "ivfflat", "vector_cosine_ops", "ops.", "audit.", "RRF"):
        assert forbidden not in query.lower() if forbidden.islower() else forbidden not in query


@pytest.mark.anyio
async def test_semantic_retrieval_rejects_wrong_dimension_or_limit_before_sql() -> None:
    connection = FakeConnection()
    repository = RAGRepository(connection)

    with pytest.raises(ValueError, match="384"):
        await repository.search_semantic_candidates([0.0] * 383, 5)
    with pytest.raises(ValueError, match="between 1 and 10"):
        await repository.search_semantic_candidates([0.0] * 384, 0)

    assert connection.statements == []
