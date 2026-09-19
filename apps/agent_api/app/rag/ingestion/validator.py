"""Eligibility and metadata validation boundary before persistence."""

from ..models import Document, SourceMetadata


class IngestionValidator:
    """Validate approval, activity, content, version, and checksum rules."""

    def validate_source(
        self,
        metadata: SourceMetadata,
        *,
        approved: bool,
        active: bool,
    ) -> None:
        """Validate source eligibility in a future implementation."""

        raise NotImplementedError("Source eligibility validation is not implemented yet.")

    def validate_document(self, document: Document) -> None:
        """Validate required metadata and non-empty content in the future."""

        raise NotImplementedError("Document validation is not implemented yet.")

