"""Bounded context construction with preserved chunk provenance."""

from collections.abc import Sequence
from dataclasses import dataclass

from ..models import RetrievedChunk


@dataclass(frozen=True, slots=True)
class GroundedContext:
    """Future LLM context paired with the chunks that support it."""

    text: str
    chunks: tuple[RetrievedChunk, ...]


class ContextBuilder:
    """Convert retrieved chunks into bounded, provenance-aware context."""

    def build(
        self,
        chunks: Sequence[RetrievedChunk],
        max_characters: int,
    ) -> GroundedContext:
        """Build bounded context in a future implementation."""

        raise NotImplementedError("Grounded context construction is not implemented yet.")

