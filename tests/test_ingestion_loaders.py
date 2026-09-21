"""Focused tests for Phase 5 local ingestion loaders."""

from pathlib import Path

import pytest

from apps.agent_api.app.rag.ingestion.loader import (
    InternalMarkdownLoader,
    PublicSourceRegistryLoader,
)
from apps.agent_api.app.rag.models import SourceMetadata


def _metadata() -> SourceMetadata:
    return SourceMetadata(
        source_id="internal-r1-pdd",
        document_id="internal-r1-pdd",
        title="PDD R1",
        source_type="INTERNAL_DOCUMENT",
    )


def test_internal_markdown_loader_reads_utf8_and_preserves_metadata(tmp_path: Path) -> None:
    source = tmp_path / "document.md"
    source.write_text("# Título\n\nTexto ágil.", encoding="utf-8")

    document = InternalMarkdownLoader(approved_root=tmp_path).load(source, _metadata())

    assert document.content == "# Título\n\nTexto ágil."
    assert document.metadata == _metadata()


@pytest.mark.parametrize("name", ["missing.md", "directory"])
def test_internal_markdown_loader_rejects_non_regular_files(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    if name == "directory":
        path.mkdir()
    with pytest.raises(ValueError, match="existing regular file"):
        InternalMarkdownLoader(approved_root=tmp_path).load(path, _metadata())


def test_internal_markdown_loader_rejects_non_markdown(tmp_path: Path) -> None:
    path = tmp_path / "document.txt"
    path.write_text("text", encoding="utf-8")
    with pytest.raises(ValueError, match="Markdown"):
        InternalMarkdownLoader(approved_root=tmp_path).load(path, _metadata())


def test_public_registry_loader_is_deterministic_and_network_free() -> None:
    registry = Path("knowledge/internal/cancellation-process/public/sources.yaml")
    sources = PublicSourceRegistryLoader().load(registry)
    assert sources
    assert [source.source_id for source in sources] == sorted(source.source_id for source in sources)
    assert all(source.url is not None for source in sources)
    assert all(source.source_type == "public_getnet" for source in sources)
    assert {source.source_class for source in sources} >= {"official_support", "official_product"}
    assert len(sources) == 23
    assert sum(source.ingestion_enabled for source in sources) == 22


def test_internal_markdown_loader_rejects_arbitrary_path(tmp_path: Path) -> None:
    path = tmp_path / "outside.md"
    path.write_text("# Outside", encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        InternalMarkdownLoader().load(path, _metadata())


def test_public_registry_loader_rejects_malformed_and_duplicate_entries(tmp_path: Path) -> None:
    malformed = tmp_path / "bad.yaml"
    malformed.write_text("sources: [", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed"):
        PublicSourceRegistryLoader().load(malformed)

    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text(
        "sources:\n"
        "  - source_id: same\n    title: A\n    source_type: public_getnet\n    url: https://example.invalid/a\n    ingestion: {enabled: true}\n"
        "  - source_id: same\n    title: B\n    source_type: public_getnet\n    url: https://example.invalid/b\n    ingestion: {enabled: true}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate"):
        PublicSourceRegistryLoader().load(duplicate)
