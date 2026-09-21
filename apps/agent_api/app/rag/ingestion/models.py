"""Immutable Phase 5 contracts, deliberately separate from database rows."""

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..models import SourceMetadata


class PreparedChunk(BaseModel):
    """A complete structural unit before embedding and FTS publication."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content: str = Field(min_length=1)
    chunk_order: int = Field(ge=0)
    section: str | None = None
    boundary_type: Literal["section", "business_rule", "technical_symbol"]
    content_type: Literal["TEXT", "BUSINESS_RULE", "TECHNICAL"]
    metadata: Mapping[str, object] = Field(default_factory=dict)


class PreparedDocument(BaseModel):
    """A normalized validated document ready for later publication."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str = Field(min_length=1)
    metadata: SourceMetadata
    normalized_content: str = Field(min_length=1)
    content_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    database_source_type: Literal["INTERNAL_DOCUMENT", "INTERNAL_POLICY", "PUBLIC_OFFICIAL"]
    database_origin: Literal["INTERNAL", "PUBLIC"]


class PreparedIngestion(BaseModel):
    """Result of Phase 5 preparation, with no embedding or tsvector payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Literal["INGEST", "REINGEST", "SKIPPED_UNCHANGED"]
    document: PreparedDocument
    chunks: tuple[PreparedChunk, ...] = ()
