"""Pure deterministic Phase 5 preparation tests."""

import re

import pytest

from apps.agent_api.app.rag.ingestion.checksum import normalized_content_checksum
from apps.agent_api.app.rag.ingestion.chunker import StructuralChunker
from apps.agent_api.app.rag.ingestion.normalizer import normalize_content
from apps.agent_api.app.rag.ingestion.validator import IngestionValidator
from apps.agent_api.app.rag.models import Document, SourceMetadata


def _document(content: str) -> Document:
    return Document(
        document_id="r1-pdd",
        content=content,
        metadata=SourceMetadata(source_id="r1", title="R1", source_type="INTERNAL_DOCUMENT", approved=True),
    )


def test_normalization_is_idempotent_and_preserves_markdown() -> None:
    raw = "# Título\r\n\r\n- item  com  espaços\r\n\r\n```python\r\nprint('x')\r\n```"
    normalized = normalize_content(raw)
    assert normalized == normalize_content(normalized)
    assert "# Título" in normalized and "- item  com  espaços" in normalized
    assert "```python" in normalized and "print('x')" in normalized


def test_normalization_rejects_blank_content() -> None:
    with pytest.raises(ValueError, match="blank"):
        normalize_content(" \r\n\t ")


def test_checksum_is_normalized_and_deterministic() -> None:
    normalized = normalize_content("a\r\nb\r\n")
    checksum = normalized_content_checksum(normalized)
    assert checksum == normalized_content_checksum("a\nb\n")
    assert checksum != normalized_content_checksum("a\nb changed\n")
    assert re.fullmatch(r"[0-9a-f]{64}", checksum)


def test_validator_rejects_ineligible_and_invalid_documents() -> None:
    validator = IngestionValidator()
    metadata = SourceMetadata(source_id="x", title="X", source_type="INTERNAL_DOCUMENT", approved=True)
    validator.validate_source(metadata, approved=True, active=True)
    validator.validate_document(_document("content"))
    with pytest.raises(ValueError, match="not approved"):
        validator.validate_source(metadata, approved=False, active=True)
    with pytest.raises(ValueError, match="cannot be blank"):
        validator.validate_document(_document(" "))


def test_structural_chunker_preserves_sections_rules_and_technical_blocks() -> None:
    document = _document(
        "# Introdução\nTexto.\n\n## Regra de negócio\nDeve validar o protocolo.\n\n## Código\n```python\ndef run():\n    return 1\n```"
    )
    chunks = StructuralChunker().chunk(document)
    assert [chunk.metadata.section for chunk in chunks] == ["Introdução", "Regra de negócio", "Código"]
    assert [chunk.boundary_type for chunk in chunks] == ["section", "business_rule", "technical_symbol"]
    assert [chunk.boundary_type for chunk in chunks] == ["section", "business_rule", "technical_symbol"]
    assert all(chunk.content.strip() for chunk in chunks)
    assert chunks == StructuralChunker().chunk(document)


def test_structural_chunker_safeguard_splits_only_at_paragraph_boundaries() -> None:
    content = "# Grande\n\n" + "A" * 2500 + "\n\n" + "B" * 2500
    chunks = StructuralChunker().chunk(_document(content))
    assert len(chunks) == 2
    assert all(chunk.content for chunk in chunks)
    assert all(len(chunk.content) <= StructuralChunker.max_safeguard_chars for chunk in chunks)
