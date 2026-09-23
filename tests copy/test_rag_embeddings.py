"""Unit tests for FastEmbedAdapter (Phase 6.1 and 6.2)."""

from __future__ import annotations

import math
from unittest.mock import MagicMock

import numpy as np
import pytest

from apps.agent_api.app.rag.embeddings.fastembed import (
    APPROVED_EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
    FastEmbedAdapter,
)


def test_fastembed_adapter_rejects_unapproved_model() -> None:
    with pytest.raises(ValueError, match="Unsupported embedding model"):
        FastEmbedAdapter(model_name="sentence-transformers/all-MiniLM-L6-v2")


def test_fastembed_adapter_lazy_initialization() -> None:
    adapter = FastEmbedAdapter(lazy=True)
    assert adapter._model is None


def test_fastembed_adapter_embed_documents_empty_list() -> None:
    adapter = FastEmbedAdapter()
    assert adapter.embed_documents([]) == []


def test_fastembed_adapter_embed_documents_rejects_blank_or_invalid() -> None:
    adapter = FastEmbedAdapter()
    with pytest.raises(ValueError, match="cannot be empty or blank"):
        adapter.embed_documents(["Valid text", "   "])

    with pytest.raises(ValueError, match="cannot be empty or blank"):
        adapter.embed_documents([""])

    with pytest.raises(ValueError, match="cannot be empty or blank"):
        adapter.embed_documents([123])  # type: ignore[list-item]


def test_fastembed_adapter_embed_query_rejects_blank_or_invalid() -> None:
    adapter = FastEmbedAdapter()
    with pytest.raises(ValueError, match="Query cannot be empty or blank"):
        adapter.embed_query("")

    with pytest.raises(ValueError, match="Query cannot be empty or blank"):
        adapter.embed_query("   ")

    with pytest.raises(ValueError, match="Query cannot be empty or blank"):
        adapter.embed_query(None)  # type: ignore[arg-type]


def test_fastembed_adapter_embed_portuguese_documents_and_query() -> None:
    adapter = FastEmbedAdapter()

    # Document texts in Portuguese
    texts = [
        "Procedimento operacional para cancelamento de maquininha Getnet.",
        "Robô R1 realiza o download de anexos do email operacional.",
        "Regra de negócio: estorno de transação acima de 5000 reais exige aprovação.",
    ]
    doc_embeddings = adapter.embed_documents(texts)

    assert len(doc_embeddings) == 3
    for vec in doc_embeddings:
        assert isinstance(vec, list)
        assert len(vec) == EMBEDDING_DIMENSIONS
        assert all(isinstance(val, float) for val in vec)
        assert all(math.isfinite(val) for val in vec)
        # Verify vector is not all zeros
        assert any(abs(val) > 1e-4 for val in vec)

    # Query in Portuguese
    query = "Como cancelar maquininha POS com erro R1?"
    query_embedding = adapter.embed_query(query)

    assert isinstance(query_embedding, list)
    assert len(query_embedding) == EMBEDDING_DIMENSIONS
    assert all(isinstance(val, float) for val in query_embedding)
    assert all(math.isfinite(val) for val in query_embedding)
    assert any(abs(val) > 1e-4 for val in query_embedding)


def test_fastembed_adapter_enforces_dimension_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FastEmbedAdapter()
    fake_model = MagicMock()
    # Return vector with 128 dimensions instead of 384
    fake_model.embed.return_value = [np.zeros(128)]
    monkeypatch.setattr(adapter, "_ensure_model", lambda: fake_model)

    with pytest.raises(ValueError, match="expected 384"):
        adapter.embed_documents(["Sample text"])


def test_fastembed_adapter_enforces_non_finite_values(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FastEmbedAdapter()
    fake_model = MagicMock()
    bad_vec = np.zeros(384)
    bad_vec[10] = float("nan")
    fake_model.embed.return_value = [bad_vec]
    monkeypatch.setattr(adapter, "_ensure_model", lambda: fake_model)

    with pytest.raises(ValueError, match="non-finite values"):
        adapter.embed_documents(["Sample text"])


def test_fastembed_adapter_enforces_count_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = FastEmbedAdapter()
    fake_model = MagicMock()
    fake_model.embed.return_value = [np.zeros(384)]  # only 1 vector for 2 texts
    monkeypatch.setattr(adapter, "_ensure_model", lambda: fake_model)

    with pytest.raises(ValueError, match="Mismatch between input text count"):
        adapter.embed_documents(["Text 1", "Text 2"])
