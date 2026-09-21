"""Rank-position-only Reciprocal Rank Fusion."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from ..models import RetrievedChunk, SearchCandidate


class RRFRanker:
    """Fuse lexical and semantic ranks without combining raw scores."""

    k: int = 60

    def rank(
        self,
        lexical: Sequence[SearchCandidate],
        semantic: Sequence[SearchCandidate],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        if not 1 <= top_k:
            raise ValueError("RRF top_k must be positive")
        accumulators: dict[int, _Accumulator] = {}
        for candidate in lexical:
            accumulator = accumulators.setdefault(candidate.chunk.chunk_id, _Accumulator(candidate))
            accumulator.add(candidate, "lexical")
        for candidate in semantic:
            accumulator = accumulators.setdefault(candidate.chunk.chunk_id, _Accumulator(candidate))
            accumulator.add(candidate, "semantic")

        ordered = sorted(
            accumulators.values(),
            key=lambda item: (-item.score, item.best_rank, item.chunk_id),
        )
        return [item.to_result(rank) for rank, item in enumerate(ordered[:top_k], start=1)]


@dataclass
class _Accumulator:
    candidate: SearchCandidate
    score: float = 0.0
    best_rank: int = 2**31 - 1
    channels: set[str] = field(default_factory=set)
    lexical_rank: int | None = None
    semantic_rank: int | None = None

    @property
    def chunk_id(self) -> int:
        return self.candidate.chunk.chunk_id

    def add(self, candidate: SearchCandidate, channel: str) -> None:
        self.score += 1 / (RRFRanker.k + candidate.channel_rank)
        self.best_rank = min(self.best_rank, candidate.channel_rank)
        self.channels.add(channel)
        if channel == "lexical":
            self.lexical_rank = candidate.channel_rank
        else:
            self.semantic_rank = candidate.channel_rank

    def to_result(self, rank: int) -> RetrievedChunk:
        return RetrievedChunk(
            chunk=self.candidate.chunk,
            provenance=self.candidate.provenance,
            rank=rank,
            score=self.score,
            matched_channels=tuple(channel for channel in ("lexical", "semantic") if channel in self.channels),
            lexical_rank=self.lexical_rank,
            semantic_rank=self.semantic_rank,
        )

        raise NotImplementedError("RRF ranking is not implemented yet.")
