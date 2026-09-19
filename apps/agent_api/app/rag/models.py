"""Domain and provenance models shared across the RAG pipeline."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SourceMetadata(BaseModel):
    """Provenance retained from a registered source through retrieval."""

    model_config = ConfigDict(str_strip_whitespace=True)

    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
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


class SearchCandidate(BaseModel):
    """A candidate returned by one retrieval channel."""

    chunk: Chunk
    retrieval_channel: Literal["lexical", "semantic"]
    channel_rank: int = Field(ge=1)
    channel_score: float | None = None


class RetrievedChunk(BaseModel):
    """A ranked chunk with its retrieval evidence preserved."""

    chunk: Chunk
    rank: int = Field(ge=1)
    score: float
    matched_channels: tuple[Literal["lexical", "semantic"], ...]


class RAGResult(BaseModel):
    """Provider-neutral result returned by the RAG service."""

    query: str = Field(min_length=1)
    chunks: list[RetrievedChunk]
    top_k: int = Field(ge=1)

