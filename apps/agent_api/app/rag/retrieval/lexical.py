"""PostgreSQL full-text search retrieval boundary."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from ..models import SearchCandidate


class _LexicalRepository(Protocol):
    async def search_lexical_candidates(
        self, query: str, limit: int
    ) -> Sequence[SearchCandidate]: ...


class LexicalRetriever:
    """Retrieve bounded lexical candidates through RAGRepository."""

    def __init__(self, repository: _LexicalRepository) -> None:
        self._repository = repository

    async def search(self, query: str, limit: int) -> Sequence[SearchCandidate]:
        if not query.strip():
            raise ValueError("Lexical query cannot be blank")
        if not 1 <= limit <= 10:
            raise ValueError("Lexical candidate limit must be between 1 and 10")
        return await self._repository.search_lexical_candidates(query, limit)
