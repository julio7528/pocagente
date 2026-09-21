"""Canonical checksums for normalized ingestion content."""

from hashlib import sha256


def normalized_content_checksum(content: str) -> str:
    """Return the lowercase SHA-256 digest of normalized document content."""

    return sha256(content.encode("utf-8")).hexdigest()
