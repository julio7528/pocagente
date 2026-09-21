"""Domain and provenance models shared across the RAG pipeline."""

from collections.abc import Mapping
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SourceMetadata(BaseModel):
    """Provenance retained from a registered source through retrieval."""

    model_config = ConfigDict(str_strip_whitespace=True)

    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    domain: str | None = None
    approved: bool = False
    active: bool = True
    ingestion_enabled: bool = True
    source_class: str | None = None
    document_id: str | None = None
    document_version: str | None = None
    section: str | None = None
    logical_location: str | None = None
    url: HttpUrl | None = None
    retrieved_at: datetime | None = None
    content_checksum: str | None = None


class Document(BaseModel):
    """A source document before structural chunking."""

    document_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    metadata: SourceMetadata


class Chunk(BaseModel):
    """A provenance-bearing structural unit of a document."""

    chunk_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    metadata: SourceMetadata
    boundary_type: Literal["section", "business_rule", "technical_symbol"]


class PersistedChunk(BaseModel):
    """A persisted chunk read from the database."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: int
    document_id: UUID
    content: str
    chunk_order: int
    section: str | None = None
    content_type: str
    metadata: Mapping[str, object] = Field(default_factory=dict)
    created_at: datetime


class RetrievalProvenance(BaseModel):
    """Provenance and metadata of the document and source for a retrieved chunk."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: UUID
    source_name: str
    source_type: str
    origin: str
    source_reference: str
    domain: str | None = None
    priority: int
    document_id: UUID
    document_key: str
    title: str
    document_type: str
    content_checksum: str | None = None
    last_ingested_at: datetime | None = None


class SearchCandidate(BaseModel):
    """A candidate returned by one retrieval channel."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk: PersistedChunk
    provenance: RetrievalProvenance
    retrieval_channel: Literal["lexical", "semantic"]
    channel_rank: int = Field(ge=1)
    channel_score: float | None = None


class RetrievedChunk(BaseModel):
    """Final post-ranking/post-fusion retrieval result consumed by grounding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk: PersistedChunk
    provenance: RetrievalProvenance
    rank: int = Field(ge=1)
    score: float
    matched_channels: tuple[Literal["lexical", "semantic"], ...]
    lexical_rank: int | None = None
    semantic_rank: int | None = None


class RAGResult(BaseModel):
    """Provider-neutral result returned by the RAG service."""

    query: str = Field(min_length=1)
    chunks: list[RetrievedChunk]
    top_k: int = Field(ge=1)
