"""Reciprocal Rank Fusion interface without ranking implementation."""

from collections.abc import Sequence

from ..models import RetrievedChunk, SearchCandidate


class RRFRanker:
    """Fuse candidate rankings without an external reranker."""

    def rank(
        self,
        candidates: Sequence[SearchCandidate],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Rank candidates through RRF in a future implementation."""

        raise NotImplementedError("RRF ranking is not implemented yet.")

