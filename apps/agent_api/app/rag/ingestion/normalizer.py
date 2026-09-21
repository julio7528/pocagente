"""Deterministic, non-semantic normalization for curated text."""


def normalize_content(content: str) -> str:
    """Normalize transport-level line endings while retaining document meaning."""

    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        raise ValueError("Normalized document content cannot be blank")
    return normalized
