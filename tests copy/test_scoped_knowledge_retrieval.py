"""Phase 11.1.3 trusted KnowledgeScope propagation contracts."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from apps.agent_api.app.agents.knowledge import KnowledgeRequest
from apps.agent_api.app.rag.retrieval.hybrid import HybridRetriever
from apps.agent_api.app.rag.retrieval.lexical import LexicalRetriever
from apps.agent_api.app.rag.retrieval.semantic import SemanticRetriever
from apps.agent_api.app.rag.scope import KnowledgeScope


def test_knowledge_request_requires_explicit_persistent_scope() -> None:
    assert KnowledgeRequest(question="internal", knowledge_scope=KnowledgeScope.INTERNAL)
    assert KnowledgeRequest(question="public", knowledge_scope=KnowledgeScope.PUBLIC_GETNET)
    with pytest.raises(ValidationError):
        KnowledgeRequest(question="none", knowledge_scope=KnowledgeScope.NONE)
    with pytest.raises(ValidationError):
        KnowledgeRequest(question="public", knowledge_scope=KnowledgeScope.PUBLIC_GETNET, extra="x")


def test_scope_is_sent_identically_to_lexical_and_semantic_channels() -> None:
    repository = MagicMock()
    repository.search_lexical_candidates = AsyncMock(return_value=())
    repository.search_semantic_candidates = AsyncMock(return_value=())
    adapter = MagicMock()
    adapter.embed_query.return_value = [0.0] * 384
    retriever = HybridRetriever(
        LexicalRetriever(repository),
        SemanticRetriever(repository, adapter),
    )

    asyncio.run(retriever.search("public product wording", KnowledgeScope.PUBLIC_GETNET))

    assert repository.search_lexical_candidates.await_args.args[2] is KnowledgeScope.PUBLIC_GETNET
    assert repository.search_semantic_candidates.await_args.args[2] is KnowledgeScope.PUBLIC_GETNET
    assert adapter.embed_query.call_args.args == ("public product wording",)


def test_public_empty_scope_does_not_widen_to_internal() -> None:
    repository = MagicMock()
    repository.search_lexical_candidates = AsyncMock(return_value=())
    repository.search_semantic_candidates = AsyncMock(return_value=())
    adapter = MagicMock()
    adapter.embed_query.return_value = [0.0] * 384
    retriever = HybridRetriever(LexicalRetriever(repository), SemanticRetriever(repository, adapter))

    assert asyncio.run(retriever.search("unsupported public question", KnowledgeScope.PUBLIC_GETNET)) == ()
    assert repository.search_lexical_candidates.await_args.args[2] is KnowledgeScope.PUBLIC_GETNET
    assert repository.search_semantic_candidates.await_args.args[2] is KnowledgeScope.PUBLIC_GETNET
    assert repository.search_lexical_candidates.await_count == 1
    assert repository.search_semantic_candidates.await_count == 1
