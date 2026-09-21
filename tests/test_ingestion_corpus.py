"""Representative real-corpus preparation without database mutation."""

import asyncio
from pathlib import Path
from uuid import uuid4

from apps.agent_api.app.rag.ingestion.cli import validate_public_registry
from apps.agent_api.app.rag.ingestion.loader import InternalMarkdownLoader, PublicSourceRegistryLoader
from apps.agent_api.app.rag.ingestion.service import IngestionPreparationService
from apps.agent_api.app.rag.models import SourceMetadata


class _NoDocumentRepository:
    async def get_document_by_key(self, source_id, document_key):
        return None

    async def document_checksum_changed(self, document_id, content_checksum):
        raise AssertionError("No existing document should be checked")


def test_representative_curated_documents_prepare_without_database_mutation() -> None:
    paths = (
        Path("knowledge/internal/cancellation-process/robot_01_r1/pdd-cancelamento.md"),
        Path("knowledge/internal/cancellation-process/robot_01_r1/sdd-cancelamento.md"),
        Path("knowledge/internal/cancellation-process/robot_02_r2/technical-overview.md"),
    )
    loader = InternalMarkdownLoader()
    service = IngestionPreparationService(_NoDocumentRepository())
    for path in paths:
        document = loader.load(
            path,
            SourceMetadata(
                source_id=f"curated-{path.stem}-{path.parent.name}",
                document_id=f"curated-{path.stem}-{path.parent.name}",
                title=path.stem,
                source_type="INTERNAL_DOCUMENT",
                approved=True,
            ),
        )
        result = asyncio.run(service.prepare(document, uuid4()))
        assert result.operation == "INGEST"
        assert result.chunks
        assert all(chunk.content.strip() for chunk in result.chunks)
        assert [chunk.chunk_order for chunk in result.chunks] == list(range(len(result.chunks)))
        assert all(chunk.metadata["content_checksum"] == result.document.content_checksum for chunk in result.chunks)


def test_real_public_registry_is_validated_without_network_access() -> None:
    registry = Path("knowledge/internal/cancellation-process/public/sources.yaml")
    sources = PublicSourceRegistryLoader().load(registry)
    assert sources and all(source.approved for source in sources)
    assert validate_public_registry(registry).startswith("VALIDATED_PUBLIC_REGISTRY:")
