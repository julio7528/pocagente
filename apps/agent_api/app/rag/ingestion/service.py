"""Central Phase 5 orchestration for deterministic ingestion preparation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from apps.agent_api.app.database.models import RAGDocumentRecord

from ..models import Document, SourceMetadata
from .checksum import normalized_content_checksum
from .chunker import StructuralChunker
from .models import PreparedChunk, PreparedDocument, PreparedIngestion
from .normalizer import normalize_content
from .validator import IngestionValidator


_DATABASE_SOURCE_TYPES = {
    "public_getnet": "PUBLIC_OFFICIAL",
    "PUBLIC_OFFICIAL": "PUBLIC_OFFICIAL",
    "INTERNAL_DOCUMENT": "INTERNAL_DOCUMENT",
    "INTERNAL_POLICY": "INTERNAL_POLICY",
}
_DATABASE_ORIGINS = {"public_getnet": "PUBLIC", "PUBLIC_OFFICIAL": "PUBLIC"}
_CONTENT_TYPES = {"section": "TEXT", "business_rule": "BUSINESS_RULE", "technical_symbol": "TECHNICAL"}


class RAGDocumentLookup(Protocol):
    async def get_document_by_key(
        self, source_id: UUID, document_key: str
    ) -> RAGDocumentRecord | None: ...

    async def document_checksum_changed(
        self, document_id: UUID, content_checksum: str
    ) -> bool: ...


class IngestionPreparationService:
    """Prepare validated artifacts without publishing incomplete chunks."""

    def __init__(
        self,
        repository: RAGDocumentLookup | None = None,
        *,
        validator: IngestionValidator | None = None,
        chunker: StructuralChunker | None = None,
    ) -> None:
        self._repository = repository
        self._validator = validator or IngestionValidator()
        self._chunker = chunker or StructuralChunker()

    def validate_public_sources(
        self, sources: Sequence[SourceMetadata]
    ) -> tuple[SourceMetadata, ...]:
        """Validate allowlisted public registrations without fetching content."""

        eligible = tuple(
            source
            for source in sources
            if source.approved and source.active and source.ingestion_enabled
        )
        for source in eligible:
            self._validator.validate_source(
                source, approved=source.approved, active=source.active
            )
        return eligible

    async def prepare(self, document: Document, source_database_id: UUID) -> PreparedIngestion:
        """Run load-ready data through the Phase 5 preparation pipeline."""

        normalized = normalize_content(document.content)
        normalized_document = document.model_copy(update={"content": normalized})
        self._validator.validate_source(
            normalized_document.metadata,
            approved=normalized_document.metadata.approved,
            active=normalized_document.metadata.active,
        )
        self._validator.validate_document(normalized_document)
        checksum = normalized_content_checksum(normalized)
        prepared_document = PreparedDocument(
            document_id=normalized_document.document_id,
            metadata=normalized_document.metadata.model_copy(
                update={"content_checksum": checksum}
            ),
            normalized_content=normalized,
            content_checksum=checksum,
            database_source_type=_DATABASE_SOURCE_TYPES.get(
                normalized_document.metadata.source_type,
                normalized_document.metadata.source_type,
            ),
            database_origin=_DATABASE_ORIGINS.get(
                normalized_document.metadata.source_type, "INTERNAL"
            ),
        )

        if self._repository is None:
            raise RuntimeError("Document preparation requires a RAG repository")
        existing = await self._repository.get_document_by_key(
            source_database_id, normalized_document.document_id
        )
        if existing is None:
            operation = "INGEST"
        elif not await self._repository.document_checksum_changed(existing.document_id, checksum):
            return PreparedIngestion(operation="SKIPPED_UNCHANGED", document=prepared_document)
        else:
            operation = "REINGEST"

        structural_chunks = self._chunker.chunk(normalized_document)
        prepared_chunks = tuple(
            PreparedChunk(
                content=chunk.content,
                chunk_order=order,
                section=chunk.metadata.section,
                boundary_type=chunk.boundary_type,
                content_type=_CONTENT_TYPES[chunk.boundary_type],
                metadata={
                    "source_id": chunk.metadata.source_id,
                    "source_title": chunk.metadata.title,
                    "source_type": _DATABASE_SOURCE_TYPES.get(
                        chunk.metadata.source_type, chunk.metadata.source_type
                    ),
                    "origin": _DATABASE_ORIGINS.get(chunk.metadata.source_type, "INTERNAL"),
                    "source_class": chunk.metadata.source_class,
                    "document_id": chunk.document_id,
                    "document_key": normalized_document.document_id,
                    "section": chunk.metadata.section,
                    "logical_location": chunk.metadata.logical_location,
                    "content_checksum": checksum,
                    "boundary_type": chunk.boundary_type,
                    "content_type": _CONTENT_TYPES[chunk.boundary_type],
                    "chunk_order": order,
                    "reference": str(chunk.metadata.url) if chunk.metadata.url else None,
                    "domain": chunk.metadata.domain,
                    "retrieved_at": (
                        chunk.metadata.retrieved_at.isoformat()
                        if chunk.metadata.retrieved_at is not None
                        else None
                    ),
                },
            )
            for order, chunk in enumerate(structural_chunks)
        )
        return PreparedIngestion(
            operation=operation, document=prepared_document, chunks=prepared_chunks
        )
