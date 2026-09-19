"""pgvector semantic search abstraction without database queries."""

from ..models import SearchCandidate


class SemanticRetriever:
    """Retrieve semantic candidates through future pgvector search."""

    def search(self, query: str, limit: int) -> list[SearchCandidate]:
        """Return semantic candidates in a future implementation."""

        raise NotImplementedError("Semantic retrieval is not implemented yet.")

