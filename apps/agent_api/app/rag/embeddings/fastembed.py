"""Adapter boundary for the approved local FastEmbed provider."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from fastembed import TextEmbedding

APPROVED_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIMENSIONS = 384


class FastEmbedAdapter:
    """Expose embedding operations using the approved local FastEmbed provider."""

    def __init__(
        self,
        model_name: str = APPROVED_EMBEDDING_MODEL,
        *,
        threads: int | None = None,
        lazy: bool = True,
    ) -> None:
        if model_name != APPROVED_EMBEDDING_MODEL:
            raise ValueError(
                f"Unsupported embedding model '{model_name}'. "
                f"Approved model is '{APPROVED_EMBEDDING_MODEL}'."
            )
        self._model_name = model_name
        self._threads = threads
        self._model: Any = None
        if not lazy:
            self._ensure_model()

    def _ensure_model(self) -> Any:
        if self._model is None:
            kwargs: dict[str, Any] = {"model_name": self._model_name}
            if self._threads is not None:
                kwargs["threads"] = self._threads
            self._model = TextEmbedding(**kwargs)
        return self._model

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a sequence of document texts, returning 384-dimensional vectors."""
        if not texts:
            return []

        for i, text in enumerate(texts):
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"Document text at index {i} cannot be empty or blank")

        model = self._ensure_model()
        raw_embeddings = list(model.embed(texts))
        if len(raw_embeddings) != len(texts):
            raise ValueError(
                f"Mismatch between input text count ({len(texts)}) "
                f"and embedding count ({len(raw_embeddings)})"
            )

        validated: list[list[float]] = []
        for i, vec in enumerate(raw_embeddings):
            vec_list = [float(val) for val in vec]
            if len(vec_list) != EMBEDDING_DIMENSIONS:
                raise ValueError(
                    f"Embedding at index {i} has {len(vec_list)} dimensions; "
                    f"expected {EMBEDDING_DIMENSIONS}"
                )
            if not all(math.isfinite(val) for val in vec_list):
                raise ValueError(f"Embedding at index {i} contains non-finite values")
            validated.append(vec_list)

        return validated

    def embed_query(self, query: str) -> list[float]:
        """Embed a query text, returning a 384-dimensional vector."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query cannot be empty or blank")

        model = self._ensure_model()
        raw_embeddings = list(model.query_embed(query))
        if not raw_embeddings:
            raise ValueError("Embedding provider returned empty output for query")

        vec_list = [float(val) for val in raw_embeddings[0]]
        if len(vec_list) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Query embedding has {len(vec_list)} dimensions; "
                f"expected {EMBEDDING_DIMENSIONS}"
            )
        if not all(math.isfinite(val) for val in vec_list):
            raise ValueError("Query embedding contains non-finite values")

        return vec_list
