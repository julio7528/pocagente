"""Focused Phase 7 retrieval, snapshot, and RRF tests."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from apps.agent_api.app.rag.config import RAGConfig
from apps.agent_api.app.rag.models import PersistedChunk, RetrievalProvenance, SearchCandidate
from apps.agent_api.app.rag.ranking.rrf import RRFRanker
from apps.agent_api.app.rag.retrieval.hybrid import HybridRetriever
from apps.agent_api.app.rag.retrieval.lexical import LexicalRetriever
from apps.agent_api.app.rag.retrieval.semantic import SemanticRetriever


def candidate(chunk_id: int, channel: str, rank: int) -> SearchCandidate:
    doc_id = uuid4()
    return SearchCandidate(
        chunk=PersistedChunk(
            chunk_id=chunk_id,
            document_id=doc_id,
            content=f"chunk {chunk_id}",
            chunk_order=0,
            content_type="TEXT",
            created_at=datetime.now(UTC),
        ),
        provenance=RetrievalProvenance(
            source_id=uuid4(), source_name="source", source_type="INTERNAL_DOCUMENT",
            origin="INTERNAL", source_reference="ref", priority=0, document_id=doc_id,
            document_key="doc", title="title", document_type="PDD",
        ),
        retrieval_channel=channel,
        channel_rank=rank,
        channel_score=999.0,
    )


def test_rrf_uses_ranks_only_deduplicates_and_tie_breaks() -> None:
    result = RRFRanker().rank(
        [candidate(1, "lexical", 1), candidate(2, "lexical", 2), candidate(3, "lexical", 3)],
        [candidate(3, "semantic", 1), candidate(1, "semantic", 2), candidate(4, "semantic", 3)],
        5,
    )
    assert [item.chunk.chunk_id for item in result] == [1, 3, 2, 4]
    assert result[0].matched_channels == ("lexical", "semantic")
    assert result[0].lexical_rank == 1 and result[0].semantic_rank == 2
    assert result[0].score == pytest.approx(1 / 61 + 1 / 62)
    assert all(item.score >= 0 for item in result)


def test_rrf_limits_top_k_and_handles_empty_channels() -> None:
    assert RRFRanker().rank([], [], 5) == []
    result = RRFRanker().rank([candidate(i, "lexical", i) for i in range(1, 9)], [], 5)
    assert len(result) == 5
    assert all(item.matched_channels == ("lexical",) for item in result)


def test_channel_retrievers_validate_and_delegate() -> None:
    repository = MagicMock()
    repository.search_lexical_candidates = AsyncMock(return_value=(candidate(1, "lexical", 1),))
    repository.search_semantic_candidates = AsyncMock(return_value=(candidate(1, "semantic", 1),))
    adapter = MagicMock()
    adapter.embed_query.return_value = [0.0] * 384
    lexical = LexicalRetriever(repository)
    semantic = SemanticRetriever(repository, adapter)

    async def run() -> None:
        assert len(await lexical.search("query", 10)) == 1
        assert len(await semantic.search("query", 10)) == 1
        with pytest.raises(ValueError):
            await lexical.search(" ", 10)
        with pytest.raises(ValueError):
            await semantic.search(" ", 10)

    asyncio.run(run())
    repository.search_lexical_candidates.assert_awaited_once_with("query", 10)
    assert repository.search_semantic_candidates.await_args.args[1] == 10
    assert len(repository.search_semantic_candidates.await_args.args[0].to_list()) == 384


def test_hybrid_public_api_fuses_two_channels_and_uses_config_limits() -> None:
    lexical = MagicMock()
    lexical.search = AsyncMock(return_value=(candidate(1, "lexical", 1),))
    semantic = MagicMock()
    semantic.search = AsyncMock(return_value=(candidate(2, "semantic", 1),))
    retriever = HybridRetriever(
        lexical, semantic, config=RAGConfig(lexical_candidate_limit=3, semantic_candidate_limit=4, final_top_k=1)
    )

    async def run() -> None:
        result = await retriever.search("query")
        assert len(result) == 1
        assert result[0].chunk.chunk_id == 1

    asyncio.run(run())
    lexical.search.assert_awaited_once_with("query", 3)
    semantic.search.assert_awaited_once_with("query", 4)


def test_hybrid_snapshot_uses_one_transaction_and_same_repository_connection(monkeypatch) -> None:
    import apps.agent_api.app.rag.retrieval.hybrid as hybrid_module

    connection = object()
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=connection)
    transaction.__aexit__ = AsyncMock(return_value=False)
    database = MagicMock()
    database.transaction.return_value = transaction
    repository = MagicMock()
    repository.begin_read_only_repeatable_read = AsyncMock()
    repository.search_lexical_candidates = AsyncMock(return_value=())
    repository.search_semantic_candidates = AsyncMock(return_value=())
    monkeypatch.setattr(hybrid_module, "RAGRepository", lambda received: repository)
    adapter = MagicMock()
    adapter.embed_query.return_value = [0.0] * 384

    retriever = HybridRetriever(
        LexicalRetriever(repository),
        SemanticRetriever(repository, adapter),
        database=database,
    )
    asyncio.run(retriever.search("snapshot"))

    database.transaction.assert_called_once_with()
    transaction.__aenter__.assert_awaited_once_with()
    repository.begin_read_only_repeatable_read.assert_awaited_once_with()
    repository.search_lexical_candidates.assert_awaited_once_with("snapshot", 10)
    repository.search_semantic_candidates.assert_awaited_once()
