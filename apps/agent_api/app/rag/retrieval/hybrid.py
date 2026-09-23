"""Consistent-snapshot hybrid retrieval orchestration."""

from __future__ import annotations

from collections.abc import Sequence

from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.repositories.rag import RAGRepository

from ..config import DEFAULT_RAG_CONFIG, RAGConfig
from ..models import RetrievedChunk
from ..scope import KnowledgeScope, require_persistent_knowledge_scope
from .lexical import LexicalRetriever
from ..ranking.rrf import RRFRanker
from .semantic import SemanticRetriever


class HybridRetriever:
    """Coordinate bounded lexical and semantic retrieval channels."""

    def __init__(
        self,
        lexical: LexicalRetriever,
        semantic: SemanticRetriever,
        database: PostgresDatabase | None = None,
        config: RAGConfig | None = None,
        ranker: RRFRanker | None = None,
    ) -> None:
        self._lexical = lexical
        self._semantic = semantic
        self._database = database
        self._config = config or DEFAULT_RAG_CONFIG
        self._ranker = ranker or RRFRanker()

    async def search(self, query: str, knowledge_scope: KnowledgeScope) -> Sequence[RetrievedChunk]:
        """Retrieve both channels in one read-only repeatable-read snapshot."""

        if not query.strip():
            raise ValueError("Hybrid query cannot be blank")
        require_persistent_knowledge_scope(knowledge_scope)
        if self._database is None:
            lexical = await self._lexical.search(query, self._config.lexical_candidate_limit, knowledge_scope)
            semantic = await self._semantic.search(query, self._config.semantic_candidate_limit, knowledge_scope)
            return tuple(self._ranker.rank(lexical, semantic, self._config.final_top_k))

        async with self._database.transaction() as connection:
            repository = RAGRepository(connection)
            await repository.begin_read_only_repeatable_read()
            lexical = await LexicalRetriever(repository).search(
                query, self._config.lexical_candidate_limit, knowledge_scope
            )
            semantic = await SemanticRetriever(
                repository, self._semantic.embed_adapter
            ).search(query, self._config.semantic_candidate_limit, knowledge_scope)
            return tuple(self._ranker.rank(lexical, semantic, self._config.final_top_k))
