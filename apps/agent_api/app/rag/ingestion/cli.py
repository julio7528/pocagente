"""Minimal manual Phase 5 preparation entry points; no publication occurs."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from uuid import UUID

from apps.agent_api.app.database.config import load_database_config
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.repositories.rag import RAGRepository

from ..models import SourceMetadata
from .loader import InternalMarkdownLoader, PublicSourceRegistryLoader
from .service import IngestionPreparationService


async def prepare_internal(path: Path, metadata: SourceMetadata, source_id: UUID) -> str:
    """Prepare one curated internal file through the central service."""

    database = PostgresDatabase(load_database_config())
    await database.open()
    try:
        async with database.connection() as connection:
            document = InternalMarkdownLoader().load(path, metadata)
            result = await IngestionPreparationService(RAGRepository(connection)).prepare(
                document, source_id
            )
    finally:
        await database.close()
    return f"{result.operation}: {result.document.document_id}; prepared_chunks={len(result.chunks)}; publication=deferred_to_phase_6"


def validate_public_registry(path: Path) -> str:
    """Validate approved public registrations without crawling or publishing."""

    registered = PublicSourceRegistryLoader().load(path)
    eligible_sources = IngestionPreparationService().validate_public_sources(registered)
    return (
        f"VALIDATED_PUBLIC_REGISTRY: registered={len(registered)}; "
        f"ingestion_enabled={len(eligible_sources)}; network=disabled"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare approved RAG ingestion artifacts")
    subparsers = parser.add_subparsers(dest="command", required=True)
    internal = subparsers.add_parser("internal")
    internal.add_argument("path", type=Path)
    internal.add_argument("--source-id", required=True, type=UUID)
    internal.add_argument("--source-key", required=True)
    internal.add_argument("--title", required=True)
    internal.add_argument("--source-type", default="INTERNAL_DOCUMENT")
    public = subparsers.add_parser("public-registry")
    public.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "public-registry":
        print(validate_public_registry(args.path))
        return
    metadata = SourceMetadata(
        source_id=args.source_key,
        document_id=args.source_key,
        title=args.title,
        source_type=args.source_type,
        approved=True,
    )
    print(asyncio.run(prepare_internal(args.path, metadata, args.source_id)))


if __name__ == "__main__":
    main()
