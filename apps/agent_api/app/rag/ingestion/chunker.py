"""Structural chunking boundary for semantic document units."""

from enum import StrEnum

from ..models import Chunk, Document


class ChunkBoundary(StrEnum):
    """Approved semantic boundaries for future chunking."""

    SECTION = "section"
    BUSINESS_RULE = "business_rule"
    TECHNICAL_SYMBOL = "technical_symbol"


class StructuralChunker:
    """Split documents by meaning and structure, not only fixed size."""

    def chunk(self, document: Document) -> list[Chunk]:
        """Create structural chunks in a future implementation."""

        raise NotImplementedError("Structural chunking is not implemented yet.")

