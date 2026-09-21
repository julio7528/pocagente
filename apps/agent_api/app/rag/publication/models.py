"""Publication contracts bridging Phase 5 preparation and database persistence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PublicationChunk(BaseModel):
    """A complete chunk with embedding and FTS metadata ready for rag.chunks publication."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content: str = Field(min_length=1)
    chunk_order: int = Field(ge=0)
    section: str | None = None
    boundary_type: Literal["section", "business_rule", "technical_symbol"]
    content_type: Literal["TEXT", "BUSINESS_RULE", "TECHNICAL"]
    metadata: Mapping[str, object] = Field(default_factory=dict)
    embedding: list[float] = Field(min_length=384, max_length=384)
    search_vector: str | None = None

    def to_repository_record(self) -> dict[str, object]:
        """Convert into the dictionary structure expected by RAGRepository."""
        return {
            "content": self.content,
            "chunk_order": self.chunk_order,
            "section": self.section,
            "content_type": self.content_type,
            "metadata": dict(self.metadata),
            "embedding": list(self.embedding),
            "search_vector": self.search_vector,
        }


class PublicationResult(BaseModel):
    """Outcome of an atomic publication operation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Literal["INGEST", "REINGEST", "SKIPPED_UNCHANGED"]
    status: Literal["SUCCESS", "SKIPPED"]
    source_id: UUID
    document_id: UUID | None
    document_key: str
    chunks_published: int
    ingestion_run_id: int
