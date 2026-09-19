"""Adapter boundary for the approved local FastEmbed provider."""

from collections.abc import Sequence


class FastEmbedAdapter:
    """Expose embedding operations without loading or downloading a model."""

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed document text in a future implementation."""

        raise NotImplementedError("FastEmbed document embedding is not implemented yet.")

    def embed_query(self, query: str) -> list[float]:
        """Embed a query in a future implementation."""

        raise NotImplementedError("FastEmbed query embedding is not implemented yet.")

