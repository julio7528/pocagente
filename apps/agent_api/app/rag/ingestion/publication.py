"""Publish one validated public registry source through the existing RAG pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import httpx

from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.repositories.rag import RAGRepository
from apps.agent_api.app.rag.publication.models import PublicationResult
from apps.agent_api.app.rag.publication.service import RAGPublicationService

from .models import PublicRegistrySource
from .public_fetcher import PublicSourceFetcher
from .service import IngestionPreparationService


def _assert_source_identity(source: object, registry: PublicRegistrySource) -> None:
    expected = {
        "name": registry.title,
        "source_type": "PUBLIC_OFFICIAL",
        "origin": "PUBLIC",
        "reference": str(registry.url),
        "domain": registry.domain,
        "status": "ACTIVE",
    }
    if any(getattr(source, key) != value for key, value in expected.items()):
        raise ValueError("Existing public RAG source conflicts with approved registry identity")


async def publish_public_registry_source(
    database: PostgresDatabase,
    registry_source: PublicRegistrySource,
    client: httpx.AsyncClient,
    *,
    fetcher: PublicSourceFetcher | None = None,
    publisher: RAGPublicationService | None = None,
) -> PublicationResult:
    """Acquire one exact allowlisted URL and atomically publish using Phase 5/6 services."""

    if not (registry_source.approved and registry_source.active and registry_source.ingestion_enabled):
        raise ValueError("Public registry source is not approved for ingestion")

    document = await (fetcher or PublicSourceFetcher()).fetch(registry_source, client)
    async with database.transaction() as connection:
        repository = RAGRepository(connection)
        source = await repository.get_source_by_reference("PUBLIC", str(registry_source.url))
        if source is None:
            source = await repository.register_source(
                {
                    "source_id": uuid4(),
                    "name": registry_source.title,
                    "source_type": "PUBLIC_OFFICIAL",
                    "origin": "PUBLIC",
                    "reference": str(registry_source.url),
                    "domain": registry_source.domain,
                    "status": "ACTIVE",
                    "priority": 30,
                    "updated_at": datetime.now(UTC),
                }
            )
        else:
            _assert_source_identity(source, registry_source)
        source_id = source.source_id

    async with database.connection() as connection:
        prepared = await IngestionPreparationService(RAGRepository(connection)).prepare(
            document, source_id
        )

    return await (publisher or RAGPublicationService(database)).publish(prepared, source_id)
