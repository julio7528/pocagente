"""CLI delegation tests without a real database connection."""

import asyncio
from pathlib import Path
from uuid import uuid4

from apps.agent_api.app.rag.ingestion import cli
from apps.agent_api.app.rag.ingestion.loader import InternalMarkdownLoader
from apps.agent_api.app.rag.models import SourceMetadata


class _ConnectionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *args):
        return False


class _Database:
    async def open(self):
        return None

    async def close(self):
        return None

    def connection(self):
        return _ConnectionContext()


class _Repository:
    def __init__(self, connection):
        self.connection = connection

    async def get_document_by_key(self, source_id, document_key):
        return None

    async def document_checksum_changed(self, document_id, checksum):
        raise AssertionError("not called for a new document")


def test_internal_cli_delegates_to_preparation_service(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "curated.md"
    path.write_text("# Documento\nConteúdo validado.", encoding="utf-8")
    monkeypatch.setattr(cli, "load_database_config", lambda: object())
    monkeypatch.setattr(cli, "PostgresDatabase", lambda config: _Database())
    monkeypatch.setattr(cli, "RAGRepository", _Repository)
    monkeypatch.setattr(cli, "InternalMarkdownLoader", lambda: InternalMarkdownLoader(approved_root=tmp_path))

    result = asyncio.run(
        cli.prepare_internal(
            path,
            SourceMetadata(source_id="curated", document_id="curated", title="Curated", source_type="INTERNAL_DOCUMENT", approved=True),
            uuid4(),
        )
    )

    assert result.startswith("INGEST:")
    assert "publication=deferred_to_phase_6" in result


def test_public_cli_reports_validation_errors_without_network(tmp_path: Path) -> None:
    registry = tmp_path / "invalid.yaml"
    registry.write_text("sources: []", encoding="utf-8")
    assert cli.validate_public_registry(registry).startswith("VALIDATED_PUBLIC_REGISTRY:")
