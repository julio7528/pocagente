"""Application-level Phase 5 preparation and non-publication tests."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.agent_api.app.rag.ingestion.service import IngestionPreparationService
from apps.agent_api.app.rag.models import Document, SourceMetadata


class FakeRAGLookup:
    def __init__(self, existing: object | None = None, changed: bool = False) -> None:
        self.existing = existing
        self.changed = changed
        self.calls: list[str] = []

    async def get_document_by_key(self, source_id, document_key):
        self.calls.append("get")
        return self.existing

    async def document_checksum_changed(self, document_id, checksum):
        self.calls.append("changed")
        return self.changed


def _document(content: str = "# Regra\nDeve manter o protocolo.") -> Document:
    return Document(
        document_id="pdd-r1",
        content=content,
        metadata=SourceMetadata(source_id="internal-r1", title="PDD R1", source_type="INTERNAL_DOCUMENT", approved=True),
    )


def test_new_document_prepares_deterministic_artifacts_without_persistence() -> None:
    repository = FakeRAGLookup()
    service = IngestionPreparationService(repository)
    result = asyncio.run(service.prepare(_document("# Regra\r\nDeve manter o protocolo."), uuid4()))
    assert result.operation == "INGEST"
    assert result.chunks and result.chunks[0].metadata["content_checksum"] == result.document.content_checksum
    assert result.chunks[0].boundary_type == "business_rule"
    assert result.chunks[0].content_type == "BUSINESS_RULE"
    assert repository.calls == ["get"]
    assert "embedding" not in result.chunks[0].model_fields_set


def test_unchanged_document_stops_before_chunk_replacement() -> None:
    repository = FakeRAGLookup(SimpleNamespace(document_id=uuid4()), changed=False)
    result = asyncio.run(IngestionPreparationService(repository).prepare(_document(), uuid4()))
    assert result.operation == "SKIPPED_UNCHANGED"
    assert result.chunks == ()
    assert repository.calls == ["get", "changed"]


def test_changed_document_prepares_replacement_candidate_only() -> None:
    repository = FakeRAGLookup(SimpleNamespace(document_id=uuid4()), changed=True)
    result = asyncio.run(IngestionPreparationService(repository).prepare(_document(), uuid4()))
    assert result.operation == "REINGEST"
    assert result.chunks


def test_invalid_preparation_does_not_touch_repository() -> None:
    repository = FakeRAGLookup()
    with pytest.raises(ValueError, match="blank"):
        asyncio.run(IngestionPreparationService(repository).prepare(_document("  "), uuid4()))
    assert repository.calls == []


def test_public_registry_type_maps_to_database_contract_and_preserves_class() -> None:
    document = Document(
        document_id="public-page",
        content="# Página\nConteúdo público.",
        metadata=SourceMetadata(
            source_id="getnet-help",
            title="Ajuda Getnet",
            source_type="public_getnet",
            source_class="official_support",
            domain="site.getnet.com.br",
            approved=True,
            active=True,
            ingestion_enabled=True,
            url="https://site.getnet.com.br/get-ajuda/",
        ),
    )
    result = asyncio.run(IngestionPreparationService(FakeRAGLookup()).prepare(document, uuid4()))
    assert result.document.database_source_type == "PUBLIC_OFFICIAL"
    assert result.document.database_origin == "PUBLIC"
    assert result.chunks[0].metadata["source_type"] == "PUBLIC_OFFICIAL"
    assert result.chunks[0].metadata["origin"] == "PUBLIC"
    assert result.chunks[0].metadata["source_class"] == "official_support"
