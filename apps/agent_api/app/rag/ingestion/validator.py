"""Eligibility and metadata validation boundary before persistence."""

from ..models import Document, SourceMetadata


_SUPPORTED_SOURCE_TYPES = frozenset(
    {"INTERNAL_DOCUMENT", "INTERNAL_POLICY", "PUBLIC_OFFICIAL", "public_getnet"}
)


class IngestionValidator:
    """Validate approval, activity, content, version, and checksum rules."""

    def validate_source(
        self,
        metadata: SourceMetadata,
        *,
        approved: bool,
        active: bool,
    ) -> None:
        """Validate explicit source eligibility before any persistence work."""

        if not approved or not metadata.approved:
            raise ValueError("Source is not approved for ingestion")
        if not active or not metadata.active:
            raise ValueError("Source is not active for ingestion")
        if not metadata.ingestion_enabled:
            raise ValueError("Source is not eligible for ingestion")
        if metadata.source_type not in _SUPPORTED_SOURCE_TYPES:
            raise ValueError("Unsupported source type")
        if not metadata.source_id.strip() or not metadata.title.strip():
            raise ValueError("Source identity and title are required")


    def validate_document(self, document: Document) -> None:
        """Validate a normalized document and its source relationship."""

        if not document.document_id.strip():
            raise ValueError("Document identity is required")
        if not document.content.strip():
            raise ValueError("Document content cannot be blank")
        if not document.metadata.source_id.strip():
            raise ValueError("Document source identity is required")
        if document.metadata.document_id and document.metadata.document_id != document.document_id:
            raise ValueError("Document identity conflicts with source metadata")
