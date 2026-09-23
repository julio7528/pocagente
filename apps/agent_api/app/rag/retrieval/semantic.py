"""pgvector semantic search retrieval boundary."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from pgvector import Vector

from ..embeddings.fastembed import FastEmbedAdapter
from ..models import SearchCandidate
from ..scope import KnowledgeScope, require_persistent_knowledge_scope


class _SemanticRepository(Protocol):
    async def search_semantic_candidates(
        self, embedding: Sequence[float], limit: int, knowledge_scope: KnowledgeScope
    ) -> Sequence[SearchCandidate]: ...


class SemanticRetriever:
    """Embed a query once and delegate cosine retrieval to RAGRepository."""

    def __init__(
        self,
        repository: _SemanticRepository,
        embed_adapter: FastEmbedAdapter,
    ) -> None:
        self._repository = repository
        self._embed_adapter = embed_adapter

    @property
    def embed_adapter(self) -> FastEmbedAdapter:
        """Expose the approved adapter for a repository-bound snapshot run."""

        return self._embed_adapter

    async def search(self, query: str, limit: int, knowledge_scope: KnowledgeScope) -> Sequence[SearchCandidate]:
        if not query.strip():
            raise ValueError("Semantic query cannot be blank")
        if not 1 <= limit <= 10:
            raise ValueError("Semantic candidate limit must be between 1 and 10")
        require_persistent_knowledge_scope(knowledge_scope)
        embedding = self._embed_adapter.embed_query(query)
        if len(embedding) != 384:
            raise ValueError("Semantic query embedding must have 384 dimensions")
        return await self._repository.search_semantic_candidates(Vector(embedding), limit, knowledge_scope)
