"""Architectural contract regression tests for the RAG type pipeline.

Ensures clear semantic separation across:
1. Chunk (structural ingestion)
2. PersistedChunk (physical database row)
3. SearchCandidate (pre-fusion channel candidate)
4. RetrievedChunk (post-fusion final ranked result)
5. RAGResult (final search output)
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import get_args, get_origin, get_type_hints
from uuid import uuid4

import pytest
from pydantic import ValidationError

from apps.agent_api.app.database.mapping import map_search_candidate
from apps.agent_api.app.rag.grounding.context_builder import (
    ContextBuilder,
    GroundedContext,
)
from apps.agent_api.app.rag.models import (
    Chunk,
    PersistedChunk,
    RAGResult,
    RetrievalProvenance,
    RetrievedChunk,
    SearchCandidate,
    SourceMetadata,
)
from apps.agent_api.app.rag.ranking.rrf import RRFRanker


def _sample_persisted_chunk() -> PersistedChunk:
    return PersistedChunk(
        chunk_id=101,
        document_id=uuid4(),
        content="Sample chunk content from database",
        chunk_order=0,
        section="Section 1",
        content_type="BUSINESS_RULE",
        metadata={"domain": "acquiring"},
        created_at=datetime.now(timezone.utc),
    )


def _sample_provenance() -> RetrievalProvenance:
    return RetrievalProvenance(
        source_id=uuid4(),
        source_name="Getnet Portal",
        source_type="INTERNAL_DOCUMENT",
        origin="INTERNAL",
        source_reference="REF-001",
        domain="core",
        priority=1,
        document_id=uuid4(),
        document_key="DOC-KEY-1",
        title="Operational Manual",
        document_type="PDD",
    )


def test_1_chunk_preserves_structural_semantics() -> None:
    metadata = SourceMetadata(
        source_id="src-1",
        title="Source Title",
        source_type="INTERNAL_DOCUMENT",
    )
    chunk = Chunk(
        chunk_id="chunk-structural-1",
        document_id="doc-structural-1",
        content="Structural boundary chunk",
        metadata=metadata,
        boundary_type="section",
    )
    assert chunk.boundary_type == "section"
    assert isinstance(chunk.chunk_id, str)
    assert isinstance(chunk.document_id, str)
    assert not hasattr(chunk, "content_type")
    assert not hasattr(chunk, "created_at")


def test_2_persisted_chunk_preserves_physical_identity_semantics() -> None:
    persisted = _sample_persisted_chunk()
    assert isinstance(persisted.chunk_id, int)
    assert isinstance(persisted.content_type, str)
    assert not hasattr(persisted, "rank")
    assert not hasattr(persisted, "score")
    assert not hasattr(persisted, "matched_channels")

    # Rejects ranking/fusion fields
    with pytest.raises(ValidationError):
        PersistedChunk(
            chunk_id=1,
            document_id=uuid4(),
            content="text",
            chunk_order=0,
            content_type="TEXT",
            created_at=datetime.now(timezone.utc),
            rank=1,  # type: ignore[call-arg]
        )


def test_3_search_candidate_contains_pre_fusion_candidate_contract() -> None:
    persisted = _sample_persisted_chunk()
    prov = _sample_provenance()

    candidate = SearchCandidate(
        chunk=persisted,
        provenance=prov,
        retrieval_channel="lexical",
        channel_rank=1,
        channel_score=0.88,
    )
    assert candidate.chunk is persisted
    assert isinstance(candidate.chunk, PersistedChunk)
    assert candidate.provenance is prov
    assert candidate.retrieval_channel == "lexical"
    assert candidate.channel_rank == 1
    assert candidate.channel_score == 0.88

    # SearchCandidate does not carry fused ranking fields
    assert not hasattr(candidate, "matched_channels")
    assert not hasattr(candidate, "score")
    assert not hasattr(candidate, "rank")


def test_4_retrieved_chunk_contains_post_fusion_ranked_contract() -> None:
    persisted = _sample_persisted_chunk()
    prov = _sample_provenance()

    retrieved = RetrievedChunk(
        chunk=persisted,
        provenance=prov,
        rank=1,
        score=0.96,
        matched_channels=("lexical", "semantic"),
    )
    assert retrieved.chunk is persisted
    assert isinstance(retrieved.chunk, PersistedChunk)
    assert retrieved.provenance is prov
    assert retrieved.rank == 1
    assert retrieved.score == 0.96
    assert retrieved.matched_channels == ("lexical", "semantic")

    with pytest.raises(ValidationError):
        RetrievedChunk(
            chunk=persisted,
            provenance=prov,
            rank=0,  # ge=1 violated
            score=0.96,
            matched_channels=("lexical",),
        )


def test_5_rag_result_contains_only_final_retrieved_chunks() -> None:
    persisted = _sample_persisted_chunk()
    prov = _sample_provenance()
    retrieved = RetrievedChunk(
        chunk=persisted,
        provenance=prov,
        rank=1,
        score=0.95,
        matched_channels=("lexical",),
    )

    # Valid RAGResult with RetrievedChunk
    result = RAGResult(
        query="qual o procedimento de cancelamento",
        chunks=[retrieved],
        top_k=5,
    )
    assert len(result.chunks) == 1
    assert isinstance(result.chunks[0], RetrievedChunk)
    assert result.chunks[0].chunk is persisted

    # Reject PersistedChunk in RAGResult.chunks
    with pytest.raises(ValidationError):
        RAGResult(
            query="test query",
            chunks=[persisted],  # type: ignore[list-item]
            top_k=5,
        )

    # Reject SearchCandidate in RAGResult.chunks
    candidate = SearchCandidate(
        chunk=persisted,
        provenance=prov,
        retrieval_channel="lexical",
        channel_rank=1,
    )
    with pytest.raises(ValidationError):
        RAGResult(
            query="test query",
            chunks=[candidate],  # type: ignore[list-item]
            top_k=5,
        )


def test_6_rrf_ranker_contract_signature_matches() -> None:
    sig = inspect.signature(RRFRanker.rank)
    assert "lexical" in sig.parameters
    assert "semantic" in sig.parameters
    assert "top_k" in sig.parameters

    hints = get_type_hints(RRFRanker.rank)
    return_type = hints.get("return")
    assert get_origin(return_type) is list
    assert get_args(return_type) == (RetrievedChunk,)


def test_7_context_builder_consumes_retrieved_chunk_contract() -> None:
    sig = inspect.signature(ContextBuilder.build)
    assert "query" in sig.parameters
    assert "retrieved_chunks" in sig.parameters

    hints = get_type_hints(ContextBuilder.build)
    return_type = hints.get("return")
    assert return_type is GroundedContext

    gc_hints = get_type_hints(GroundedContext)
    assert "evidence" in gc_hints
    assert "citations" in gc_hints


def test_8_database_mapping_creates_persisted_chunk_not_retrieved_chunk() -> None:
    now = datetime.now(timezone.utc)
    doc_id = uuid4()
    source_id = uuid4()
    row = {
        "chunk_id": 55,
        "document_id": doc_id,
        "content": "Database row content",
        "chunk_order": 0,
        "section": "Sec 1",
        "content_type": "TEXT",
        "metadata": {},
        "created_at": now,
        "source_id": source_id,
        "source_name": "Portal",
        "source_type": "INTERNAL_DOCUMENT",
        "origin": "INTERNAL",
        "source_reference": "REF-55",
        "domain": "pos",
        "priority": 1,
        "document_key": "key-55",
        "title": "Doc 55",
        "document_type": "PDD",
        "content_checksum": None,
        "last_ingested_at": None,
        "retrieval_channel": "lexical",
        "channel_rank": 1,
        "channel_score": 0.9,
    }

    candidate = map_search_candidate(row)
    assert isinstance(candidate, SearchCandidate)
    assert isinstance(candidate.chunk, PersistedChunk)
    assert not isinstance(candidate.chunk, RetrievedChunk)
    assert not isinstance(candidate, RetrievedChunk)
    assert not hasattr(candidate, "matched_channels")
    assert not hasattr(candidate, "score")
    assert not hasattr(candidate, "rank")
