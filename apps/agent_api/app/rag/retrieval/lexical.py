"""PostgreSQL full-text search retrieval boundary."""

from __future__ import annotations

from collections.abc import Sequence
import re
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
        return await self._repository.search_lexical_candidates(
            normalize_lexical_query(query), limit
        )


_QUESTION_STOPWORDS = frozenset(
    {
        "a", "as", "antes", "ao", "aos", "como", "da", "das", "de", "depois",
        "do", "dos", "durante", "e", "em", "na", "nas", "no", "nos", "o", "os",
        "ou", "para", "pela", "pelas", "pelo", "pelos", "por", "qual", "quais",
        "quando", "que", "se", "um", "uma",
    }
)


def normalize_lexical_query(query: str) -> str:
    """Build a bounded OR query from meaningful natural-language terms.

    PostgreSQL ``websearch_to_tsquery`` joins ordinary words with AND. That is
    appropriate for short keyword searches but over-constrains complete user
    questions: one absent conversational term can eliminate every lexical
    candidate. This normalization keeps identifiers and Portuguese terms,
    removes only question boilerplate, deduplicates in input order, and asks
    PostgreSQL FTS for documents matching any meaningful term. Ranking still
    comes exclusively from PostgreSQL ``ts_rank_cd`` and the approved RRF.
    """

    terms = re.findall(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ_]+", query.casefold())
    meaningful = tuple(
        dict.fromkeys(
            term
            for term in terms
            if len(term) >= 2 and term not in _QUESTION_STOPWORDS
        )
    )
    if not meaningful:
        raise ValueError("Lexical query has no searchable terms")
    return " OR ".join(meaningful[:24])
