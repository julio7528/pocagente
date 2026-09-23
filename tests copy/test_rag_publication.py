"""Unit tests for publication models and RAGPublicationService (Phase 6.3 - 6.8)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from apps.agent_api.app.database.models import RAGDocumentRecord, RAGSourceRecord
from apps.agent_api.app.rag.embeddings.fastembed import FastEmbedAdapter
from apps.agent_api.app.rag.ingestion.models import (
    PreparedChunk,
    PreparedDocument,
    PreparedIngestion,
)
from apps.agent_api.app.rag.models import SourceMetadata
from apps.agent_api.app.rag.publication.models import PublicationChunk, PublicationResult
from apps.agent_api.app.rag.publication.service import RAGPublicationService


def _sample_prepared_document() -> PreparedDocument:
    metadata = SourceMetadata(
        source_id="src-pos-01",
        document_id="doc-pos-01",
        title="Manual Operacional POS",
        source_type="INTERNAL_DOCUMENT",
        approved=True,
    )
    return PreparedDocument(
        document_id="doc-pos-01",
        metadata=metadata,
        normalized_content="Conteudo normalizado do documento POS.",
        content_checksum="a" * 64,
        database_source_type="INTERNAL_DOCUMENT",
        database_origin="INTERNAL",
    )


def _sample_prepared_chunk(order: int) -> PreparedChunk:
    return PreparedChunk(
        content=f"Conteudo do chunk {order}",
        chunk_order=order,
        section="Secao 1",
        boundary_type="section",
        content_type="TEXT",
        metadata={"order": order},
    )


def test_publication_chunk_validates_dimensions_and_conversion() -> None:
    chunk = PublicationChunk(
        content="Texto de teste",
        chunk_order=0,
        section="Secao A",
        boundary_type="section",
        content_type="TEXT",
        metadata={"test": 1},
        embedding=[0.1] * 384,
        search_vector=None,
    )
    assert len(chunk.embedding) == 384
    record = chunk.to_repository_record()
    assert record["content"] == "Texto de teste"
    assert record["chunk_order"] == 0
    assert record["section"] == "Secao A"
    assert record["content_type"] == "TEXT"
    assert record["metadata"] == {"test": 1}
    assert len(record["embedding"]) == 384
    assert record["search_vector"] is None

    # Rejects != 384 dimensions
    with pytest.raises(ValidationError):
        PublicationChunk(
            content="Texto",
            chunk_order=0,
            boundary_type="section",
            content_type="TEXT",
            embedding=[0.1] * 128,  # invalid
        )


@pytest.mark.anyio
async def test_rag_publication_service_skipped_unchanged_does_not_embed() -> None:
    doc = _sample_prepared_document()
    prepared = PreparedIngestion(operation="SKIPPED_UNCHANGED", document=doc, chunks=())

    mock_db = MagicMock()
    mock_adapter = MagicMock(spec=FastEmbedAdapter)
    mock_conn = MagicMock()
    mock_cursor = AsyncMock()
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor

    # Setup transaction context manager
    mock_db.transaction.return_value.__aenter__.return_value = mock_conn

    # Setup repository mock inside transaction
    source_id = uuid4()
    doc_id = uuid4()
    existing_doc_row = {
        "document_id": doc_id,
        "source_id": source_id,
        "document_key": doc.document_id,
        "title": doc.metadata.title,
        "document_type": "INTERNAL_DOCUMENT",
        "content_checksum": doc.content_checksum,
        "status": "ACTIVE",
        "last_ingested_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    # get_document_by_key returns existing_doc_row, start_ingestion_run returns 42
    mock_cursor.fetchone.side_effect = [existing_doc_row, {"ingestion_run_id": 42}]

    service = RAGPublicationService(mock_db, mock_adapter)
    result = await service.publish(prepared, source_id)

    assert isinstance(result, PublicationResult)
    assert result.operation == "SKIPPED_UNCHANGED"
    assert result.status == "SKIPPED"
    assert result.chunks_published == 0
    assert result.ingestion_run_id == 42
    assert result.document_id == doc_id

    # Crucial: FastEmbed was NOT called
    mock_adapter.embed_documents.assert_not_called()


@pytest.mark.anyio
async def test_rag_publication_service_ingest_embeds_before_transaction() -> None:
    doc = _sample_prepared_document()
    chunks = (_sample_prepared_chunk(0), _sample_prepared_chunk(1))
    prepared = PreparedIngestion(operation="INGEST", document=doc, chunks=chunks)

    mock_db = MagicMock()
    mock_adapter = MagicMock(spec=FastEmbedAdapter)
    mock_adapter.embed_documents.return_value = [[0.1] * 384, [0.2] * 384]

    mock_conn = MagicMock()
    mock_cursor = AsyncMock()
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
    mock_db.transaction.return_value.__aenter__.return_value = mock_conn

    source_id = uuid4()
    doc_id = uuid4()
    now = datetime.now(UTC)

    source_row = {
        "source_id": source_id,
        "name": "POS Source",
        "source_type": "INTERNAL_DOCUMENT",
        "origin": "INTERNAL",
        "reference": "ref-pos",
        "domain": "pos",
        "status": "ACTIVE",
        "priority": 1,
        "created_at": now,
        "updated_at": now,
    }
    saved_doc_row = {
        "document_id": doc_id,
        "source_id": source_id,
        "document_key": doc.document_id,
        "title": doc.metadata.title,
        "document_type": "INTERNAL_DOCUMENT",
        "content_checksum": doc.content_checksum,
        "status": "ACTIVE",
        "last_ingested_at": now,
        "created_at": now,
        "updated_at": now,
    }

    # Responses for: get_source_by_id, get_document_by_key (None), start_ingestion_run, save_document
    mock_cursor.fetchone.side_effect = [
        source_row,
        None,
        {"ingestion_run_id": 99},
        saved_doc_row,
    ]

    service = RAGPublicationService(mock_db, mock_adapter)
    result = await service.publish(prepared, source_id)

    assert isinstance(result, PublicationResult)
    assert result.operation == "INGEST"
    assert result.status == "SUCCESS"
    assert result.chunks_published == 2
    assert result.ingestion_run_id == 99
    assert result.document_id == doc_id

    # FastEmbed was called with chunk contents
    mock_adapter.embed_documents.assert_called_once_with(
        ["Conteudo do chunk 0", "Conteudo do chunk 1"]
    )


@pytest.mark.anyio
async def test_rag_publication_service_fails_fast_on_zero_chunks() -> None:
    doc = _sample_prepared_document()
    prepared = PreparedIngestion(operation="INGEST", document=doc, chunks=())

    mock_db = MagicMock()
    mock_adapter = MagicMock(spec=FastEmbedAdapter)
    service = RAGPublicationService(mock_db, mock_adapter)

    with pytest.raises(ValueError, match="zero chunks"):
        await service.publish(prepared, uuid4())

    mock_db.transaction.assert_not_called()
    mock_adapter.embed_documents.assert_not_called()


def test_publication_package_has_no_dependency_on_tests() -> None:
    import ast
    from pathlib import Path

    pkg_dir = Path(__file__).resolve().parents[1] / "apps" / "agent_api" / "app" / "rag" / "publication"
    for py_file in pkg_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("tests"), f"Forbidden import of {alias.name} in {py_file}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith("tests"), f"Forbidden import from {node.module} in {py_file}"

