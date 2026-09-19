"""PostgreSQL full-text search abstraction without database queries."""

from ..models import SearchCandidate


class LexicalRetriever:
    """Retrieve lexical candidates through future PostgreSQL FTS."""

    def search(self, query: str, limit: int) -> list[SearchCandidate]:
        """Return lexical candidates in a future implementation."""

        raise NotImplementedError("Lexical retrieval is not implemented yet.")

