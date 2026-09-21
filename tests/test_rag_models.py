"""Tests for RAG domain models, separating structural chunking from persisted retrieval models."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from apps.agent_api.app.rag.models import (
    Chunk,
    PersistedChunk,
    RetrievalProvenance,
    RetrievedChunk,
    SearchCandidate,
    SourceMetadata,
)


def test_structural_chunk_still_serves_chunking_semantics() -> None:
    metadata = SourceMetadata(
        source_id="src-1",
        title="Source Title",
        source_type="INTERNAL_DOCUMENT",
    )
    chunk = Chunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        content="Structural content",
        metadata=metadata,
        boundary_type="section",
    )
    assert chunk.chunk_id == "chunk-1"
    assert chunk.boundary_type == "section"

    # Reject invalid boundary_type for structural chunk
    with pytest.raises(ValidationError):
        Chunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            content="Structural content",
            metadata=metadata,
            boundary_type="invalid_boundary",  # type: ignore[arg-type]
        )


def test_persisted_chunk_uses_physical_identity_types() -> None:
    now = datetime.now(timezone.utc)
    doc_id = uuid4()
    chunk = PersistedChunk(
        chunk_id=42,
        document_id=doc_id,
        content="Persisted content",
        chunk_order=0,
        section="Sec 1",
        content_type="BUSINESS_RULE",
        metadata={"key": "value"},
        created_at=now,
    )
    assert chunk.chunk_id == 42
    assert isinstance(chunk.chunk_id, int)
    assert chunk.document_id == doc_id
    assert isinstance(chunk.document_id, type(doc_id))
    assert chunk.content_type == "BUSINESS_RULE"
    assert chunk.metadata == {"key": "value"}

    # PersistedChunk does NOT contain ranking or fusion attributes
    assert not hasattr(chunk, "rank")
    assert not hasattr(chunk, "score")
    assert not hasattr(chunk, "matched_channels")

    # Reject ranking or fusion attributes via extra="forbid"
    with pytest.raises(ValidationError):
        PersistedChunk(
            chunk_id=42,
            document_id=doc_id,
            content="Persisted content",
            chunk_order=0,
            content_type="TEXT",
            created_at=now,
            rank=1,  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        PersistedChunk(
            chunk_id=42,
            document_id=doc_id,
            content="Persisted content",
            chunk_order=0,
            content_type="TEXT",
            created_at=now,
            score=0.9,  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        PersistedChunk(
            chunk_id=42,
            document_id=doc_id,
            content="Persisted content",
            chunk_order=0,
            content_type="TEXT",
            created_at=now,
            matched_channels=("lexical",),  # type: ignore[call-arg]
        )

    # Bigint must be an int, document_id must be a UUID
    with pytest.raises(ValidationError):
        PersistedChunk(
            chunk_id="not_an_int",  # type: ignore[arg-type]
            document_id=doc_id,
            content="Content",
            chunk_order=0,
            content_type="TEXT",
            created_at=now,
        )

    with pytest.raises(ValidationError):
        PersistedChunk(
            chunk_id=42,
            document_id="not-a-valid-uuid",  # type: ignore[arg-type]
            content="Content",
            chunk_order=0,
            content_type="TEXT",
            created_at=now,
        )


def test_retrieval_provenance_retains_identifiers() -> None:
    src_id = uuid4()
    doc_id = uuid4()
    prov = RetrievalProvenance(
        source_id=src_id,
        source_name="Getnet Portal",
        source_type="INTERNAL_DOCUMENT",
        origin="INTERNAL",
        source_reference="REF-001",
        domain="core",
        priority=1,
        document_id=doc_id,
        document_key="DOC-KEY-1",
        title="Operational Guide",
        document_type="PDD",
    )
    assert prov.source_id == src_id
    assert prov.document_id == doc_id
    assert prov.source_name == "Getnet Portal"
    assert prov.title == "Operational Guide"


def test_lexical_candidate_validates() -> None:
    now = datetime.now(timezone.utc)
    doc_id = uuid4()
    src_id = uuid4()
    chunk = PersistedChunk(
        chunk_id=1,
        document_id=doc_id,
        content="Lexical chunk content",
        chunk_order=0,
        content_type="TEXT",
        created_at=now,
    )
    prov = RetrievalProvenance(
        source_id=src_id,
        source_name="Sources",
        source_type="INTERNAL_DOCUMENT",
        origin="INTERNAL",
        source_reference="REF-1",
        priority=0,
        document_id=doc_id,
        document_key="DOC-1",
        title="Title",
        document_type="PDD",
    )
    candidate = SearchCandidate(
        chunk=chunk,
        provenance=prov,
        retrieval_channel="lexical",
        channel_rank=1,
        channel_score=0.85,
    )
    assert isinstance(candidate.chunk, PersistedChunk)
    assert candidate.retrieval_channel == "lexical"
    assert candidate.channel_rank == 1
    assert candidate.channel_score == 0.85


def test_semantic_candidate_validates() -> None:
    now = datetime.now(timezone.utc)
    doc_id = uuid4()
    src_id = uuid4()
    chunk = PersistedChunk(
        chunk_id=2,
        document_id=doc_id,
        content="Semantic chunk content",
        chunk_order=1,
        content_type="CODE",
        created_at=now,
    )
    prov = RetrievalProvenance(
        source_id=src_id,
        source_name="Sources",
        source_type="INTERNAL_DOCUMENT",
        origin="INTERNAL",
        source_reference="REF-1",
        priority=0,
        document_id=doc_id,
        document_key="DOC-1",
        title="Title",
        document_type="PDD",
    )
    candidate = SearchCandidate(
        chunk=chunk,
        provenance=prov,
        retrieval_channel="semantic",
        channel_rank=2,
        channel_score=0.12,
    )
    assert isinstance(candidate.chunk, PersistedChunk)
    assert candidate.retrieval_channel == "semantic"
    assert candidate.channel_rank == 2


def test_search_candidate_rejects_invalid_channel_and_rank() -> None:
    now = datetime.now(timezone.utc)
    doc_id = uuid4()
    src_id = uuid4()
    chunk = PersistedChunk(
        chunk_id=1,
        document_id=doc_id,
        content="Content",
        chunk_order=0,
        content_type="TEXT",
        created_at=now,
    )
    prov = RetrievalProvenance(
        source_id=src_id,
        source_name="Sources",
        source_type="INTERNAL_DOCUMENT",
        origin="INTERNAL",
        source_reference="REF-1",
        priority=0,
        document_id=doc_id,
        document_key="DOC-1",
        title="Title",
        document_type="PDD",
    )

    # Invalid retrieval channel
    with pytest.raises(ValidationError):
        SearchCandidate(
            chunk=chunk,
            provenance=prov,
            retrieval_channel="hybrid",  # type: ignore[arg-type]
            channel_rank=1,
        )

    # Rank < 1 rejected
    with pytest.raises(ValidationError):
        SearchCandidate(
            chunk=chunk,
            provenance=prov,
            retrieval_channel="lexical",
            channel_rank=0,
        )

    # Mandatory provenance cannot be omitted
    with pytest.raises(ValidationError):
        SearchCandidate(
            chunk=chunk,
            retrieval_channel="lexical",
            channel_rank=1,
        )


def test_search_candidate_rejects_structural_chunk() -> None:
    metadata = SourceMetadata(
        source_id="src-1",
        title="Source Title",
        source_type="INTERNAL_DOCUMENT",
    )
    structural_chunk = Chunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        content="Structural content",
        metadata=metadata,
        boundary_type="section",
    )
    src_id = uuid4()
    doc_id = uuid4()
    prov = RetrievalProvenance(
        source_id=src_id,
        source_name="Sources",
        source_type="INTERNAL_DOCUMENT",
        origin="INTERNAL",
        source_reference="REF-1",
        priority=0,
        document_id=doc_id,
        document_key="DOC-1",
        title="Title",
        document_type="PDD",
    )

    # SearchCandidate must NOT accept a structural Chunk
    with pytest.raises(ValidationError):
        SearchCandidate(
            chunk=structural_chunk,  # type: ignore[arg-type]
            provenance=prov,
            retrieval_channel="lexical",
            channel_rank=1,
        )


def test_final_retrieved_chunk_validates_and_retains_persisted_chunk() -> None:
    now = datetime.now(timezone.utc)
    doc_id = uuid4()
    src_id = uuid4()
    persisted = PersistedChunk(
        chunk_id=10,
        document_id=doc_id,
        content="Final retrieved text",
        chunk_order=0,
        section="Section 1",
        content_type="TEXT",
        created_at=now,
    )
    prov = RetrievalProvenance(
        source_id=src_id,
        source_name="Sources",
        source_type="INTERNAL_DOCUMENT",
        origin="INTERNAL",
        source_reference="REF-1",
        priority=0,
        document_id=doc_id,
        document_key="DOC-1",
        title="Title",
        document_type="PDD",
    )

    # Valid final RetrievedChunk with lexical channel
    rc_lex = RetrievedChunk(
        chunk=persisted,
        provenance=prov,
        rank=1,
        score=0.95,
        matched_channels=("lexical",),
    )
    assert rc_lex.rank == 1
    assert rc_lex.score == 0.95
    assert rc_lex.matched_channels == ("lexical",)
    assert rc_lex.chunk is persisted
    assert rc_lex.provenance is prov

    # Valid with semantic channel
    rc_sem = RetrievedChunk(
        chunk=persisted,
        provenance=prov,
        rank=2,
        score=0.88,
        matched_channels=("semantic",),
    )
    assert rc_sem.matched_channels == ("semantic",)

    # Valid with both channels (fused)
    rc_both = RetrievedChunk(
        chunk=persisted,
        provenance=prov,
        rank=1,
        score=0.99,
        matched_channels=("lexical", "semantic"),
    )
    assert rc_both.matched_channels == ("lexical", "semantic")

    # Rank must be >= 1
    with pytest.raises(ValidationError):
        RetrievedChunk(
            chunk=persisted,
            provenance=prov,
            rank=0,
            score=0.5,
            matched_channels=("lexical",),
        )

    # Invalid matched_channels value rejected
    with pytest.raises(ValidationError):
        RetrievedChunk(
            chunk=persisted,
            provenance=prov,
            rank=1,
            score=0.5,
            matched_channels=("unsupported",),  # type: ignore[arg-type]
        )

    # Extra fields rejected
    with pytest.raises(ValidationError):
        RetrievedChunk(
            chunk=persisted,
            provenance=prov,
            rank=1,
            score=0.5,
            matched_channels=("lexical",),
            unknown_attribute="rejected",  # type: ignore[call-arg]
        )


def test_pipeline_type_distinctions() -> None:
    # 1. Structural Chunk vs PersistedChunk vs RetrievedChunk
    assert Chunk != PersistedChunk
    assert RetrievedChunk != PersistedChunk
    assert SearchCandidate != RetrievedChunk

    # 2. Field type annotations confirm hierarchy
    assert SearchCandidate.model_fields["chunk"].annotation is PersistedChunk
    assert RetrievedChunk.model_fields["chunk"].annotation is PersistedChunk
    assert RetrievedChunk.model_fields["provenance"].annotation is RetrievalProvenance
