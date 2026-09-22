"""Command-line entry points for RAG publication and smoke verification."""

from __future__ import annotations

import argparse
import asyncio
import selectors
import sys
from collections.abc import Coroutine
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar
from uuid import UUID

import numpy as np

from apps.agent_api.app.database.config import load_database_config
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.repositories.rag import RAGRepository
from apps.agent_api.app.rag.embeddings.fastembed import FastEmbedAdapter
from apps.agent_api.app.rag.ingestion.loader import InternalMarkdownLoader
from apps.agent_api.app.rag.ingestion.service import IngestionPreparationService
from apps.agent_api.app.rag.models import SourceMetadata
from apps.agent_api.app.rag.publication.models import PublicationResult
from apps.agent_api.app.rag.publication.service import RAGPublicationService

_T = TypeVar("_T")


def _run_async(coroutine: Coroutine[object, object, _T]) -> _T:
    """Run an async coroutine with a compatible event loop for Psycopg."""
    if sys.platform == "win32":
        return asyncio.run(
            coroutine,
            loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
        )
    return asyncio.run(coroutine)


CURATED_DOCUMENTS = (
    {
        "path": Path("knowledge/internal/cancellation-process/robot_01_r1/pdd-cancelamento.md"),
        "key": "robot_01_r1/pdd-cancelamento",
        "title": "Cancelamento de Venda — PDD Genérico",
        "source_class": "PDD",
    },
    {
        "path": Path("knowledge/internal/cancellation-process/robot_01_r1/sdd-cancelamento.md"),
        "key": "robot_01_r1/sdd-cancelamento",
        "title": "Cancelamento de Venda — SDD Genérico",
        "source_class": "SDD",
    },
    {
        "path": Path("knowledge/internal/cancellation-process/robot_01_r1/technical-overview.md"),
        "key": "robot_01_r1/technical-overview",
        "title": "Visão Técnica — Processo de Cancelamento",
        "source_class": "TECHNICAL_OVERVIEW",
    },
)

R2_CURATED_DOCUMENTS = (
    {
        "path": Path("knowledge/internal/cancellation-process/robot_02_r2/pdd-cancelamento.md"),
        "key": "robot_02_r2/pdd-cancelamento",
        "source_class": "PDD",
    },
    {
        "path": Path("knowledge/internal/cancellation-process/robot_02_r2/sdd-cancelamento.md"),
        "key": "robot_02_r2/sdd-cancelamento",
        "source_class": "SDD",
    },
    {
        "path": Path("knowledge/internal/cancellation-process/robot_02_r2/technical-overview.md"),
        "key": "robot_02_r2/technical-overview",
        "source_class": "TECHNICAL_OVERVIEW",
    },
)

INTERNAL_SOURCE_CONFIG = {
    "name": "Processo de Cancelamento - Robô R1",
    "source_type": "INTERNAL_DOCUMENT",
    "origin": "INTERNAL",
    "reference": "knowledge/internal/cancellation-process/robot_01_r1",
    "domain": "cancellation-process",
    "status": "ACTIVE",
    "priority": 10,
}

R2_INTERNAL_SOURCE_CONFIG = {
    "name": "Processo de Cancelamento - Robô R2",
    "source_type": "INTERNAL_DOCUMENT",
    "origin": "INTERNAL",
    "reference": "knowledge/internal/cancellation-process/robot_02_r2",
    "domain": "cancellation-process",
    "status": "ACTIVE",
    "priority": 10,
}


def _curated_title(path: Path) -> str:
    """Read the first Markdown H1 as the approved document title."""

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            if title:
                return title
    raise ValueError(f"Curated Markdown document has no title heading: {path.name}")


async def publish_internal_document(
    database: PostgresDatabase,
    path: Path,
    metadata: SourceMetadata,
    source_id: UUID,
    *,
    embed_adapter: FastEmbedAdapter | None = None,
) -> PublicationResult:
    """Prepare and atomically publish one curated internal Markdown file."""

    document = InternalMarkdownLoader().load(path, metadata)
    async with database.connection() as connection:
        repo = RAGRepository(connection)
        prep_service = IngestionPreparationService(repo)
        prepared = await prep_service.prepare(document, source_id)

    pub_service = RAGPublicationService(database, embed_adapter=embed_adapter)
    return await pub_service.publish(prepared, source_id)


async def publish_curated_corpus(
    database: PostgresDatabase,
    *,
    embed_adapter: FastEmbedAdapter | None = None,
) -> list[PublicationResult]:
    """Publish the representative curated documents (PDD, SDD, Technical Overview)."""

    now = datetime.now(UTC)
    async with database.transaction() as connection:
        repo = RAGRepository(connection)
        existing_source = await repo.get_source_by_reference(
            INTERNAL_SOURCE_CONFIG["origin"], INTERNAL_SOURCE_CONFIG["reference"]
        )
        if existing_source is not None:
            source_id = existing_source.source_id
        else:
            source = await repo.register_source(
                {
                    **INTERNAL_SOURCE_CONFIG,
                    "updated_at": now,
                }
            )
            source_id = source.source_id

    results: list[PublicationResult] = []
    for item in CURATED_DOCUMENTS:
        meta = SourceMetadata(
            source_id=item["key"],
            document_id=item["key"],
            title=item["title"],
            source_type="INTERNAL_DOCUMENT",
            source_class=item["source_class"],
            domain=INTERNAL_SOURCE_CONFIG["domain"],
            approved=True,
            active=True,
        )
        res = await publish_internal_document(
            database,
            item["path"],
            meta,
            source_id,
            embed_adapter=embed_adapter,
        )
        results.append(res)
    return results


async def publish_r2_curated_corpus(
    database: PostgresDatabase,
    *,
    embed_adapter: FastEmbedAdapter | None = None,
) -> list[PublicationResult]:
    """Publish the separate Robot 02 / R2 curated corpus idempotently."""

    now = datetime.now(UTC)
    async with database.transaction() as connection:
        repo = RAGRepository(connection)
        existing_source = await repo.get_source_by_reference(
            R2_INTERNAL_SOURCE_CONFIG["origin"], R2_INTERNAL_SOURCE_CONFIG["reference"]
        )
        if existing_source is not None:
            expected = R2_INTERNAL_SOURCE_CONFIG
            if (
                existing_source.name != expected["name"]
                or existing_source.source_type != expected["source_type"]
                or existing_source.origin != expected["origin"]
                or existing_source.domain != expected["domain"]
                or existing_source.status != expected["status"]
                or existing_source.priority != expected["priority"]
            ):
                raise ValueError("Existing R2 source identity conflicts with approved configuration")
            source_id = existing_source.source_id
        else:
            source = await repo.register_source(
                {
                    **R2_INTERNAL_SOURCE_CONFIG,
                    "updated_at": now,
                }
            )
            source_id = source.source_id

    results: list[PublicationResult] = []
    for item in R2_CURATED_DOCUMENTS:
        meta = SourceMetadata(
            source_id=item["key"],
            document_id=item["key"],
            title=_curated_title(item["path"]),
            source_type="INTERNAL_DOCUMENT",
            source_class=item["source_class"],
            domain=R2_INTERNAL_SOURCE_CONFIG["domain"],
            approved=True,
            active=True,
        )
        results.append(
            await publish_internal_document(
                database,
                item["path"],
                meta,
                source_id,
                embed_adapter=embed_adapter,
            )
        )
    return results


async def run_smoke_retrieval(
    database: PostgresDatabase,
    query: str,
    *,
    limit: int = 5,
    embed_adapter: FastEmbedAdapter | None = None,
) -> dict[str, list[dict[str, object]]]:
    """Execute smoke lexical and semantic queries and return candidate summaries."""

    adapter = embed_adapter or FastEmbedAdapter()
    query_emb = adapter.embed_query(query)
    emb_array = np.array(query_emb, dtype=np.float32)

    async with database.connection() as connection:
        repo = RAGRepository(connection)
        lex_candidates = await repo.search_lexical_candidates(query, limit)
        sem_candidates = await repo.search_semantic_candidates(emb_array, limit)

    return {
        "lexical": [
            {
                "chunk_id": c.chunk.chunk_id,
                "document_key": c.provenance.document_key,
                "title": c.provenance.title,
                "section": c.chunk.section,
                "score": c.channel_score,
                "rank": c.channel_rank,
                "content_preview": c.chunk.content[:100],
            }
            for c in lex_candidates
        ],
        "semantic": [
            {
                "chunk_id": c.chunk.chunk_id,
                "document_key": c.provenance.document_key,
                "title": c.provenance.title,
                "section": c.chunk.section,
                "score": c.channel_score,
                "rank": c.channel_rank,
                "content_preview": c.chunk.content[:100],
            }
            for c in sem_candidates
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish and verify RAG artifacts in PostgreSQL")
    subparsers = parser.add_subparsers(dest="command", required=True)

    curated = subparsers.add_parser("publish-curated")
    curated.description = "Publish PDD, SDD, and Technical Overview into PostgreSQL"

    curated_r2 = subparsers.add_parser("publish-r2-curated")
    curated_r2.description = "Publish the separate Robot 02 / R2 curated corpus into PostgreSQL"

    smoke = subparsers.add_parser("smoke-test")
    smoke.add_argument("--query", default="cancelamento de venda Robô R1", help="Search query")
    smoke.add_argument("--limit", type=int, default=5, help="Result limit")

    args = parser.parse_args()
    db = PostgresDatabase(load_database_config())

    async def execute() -> None:
        await db.open()
        try:
            if args.command == "publish-curated":
                results = await publish_curated_corpus(db)
                for r in results:
                    print(
                        f"PUBLISHED: doc_key={r.document_key}; operation={r.operation}; "
                        f"status={r.status}; chunks={r.chunks_published}; run_id={r.ingestion_run_id}"
                    )
            elif args.command == "publish-r2-curated":
                results = await publish_r2_curated_corpus(db)
                for r in results:
                    print(
                        f"PUBLISHED: doc_key={r.document_key}; operation={r.operation}; "
                        f"status={r.status}; chunks={r.chunks_published}; run_id={r.ingestion_run_id}"
                    )
            elif args.command == "smoke-test":
                res = await run_smoke_retrieval(db, args.query, limit=args.limit)
                print(f"=== Lexical Search for '{args.query}' ===")
                for item in res["lexical"]:
                    print(f"[{item['rank']}] score={item['score']:.4f} doc={item['document_key']} sec='{item['section']}' preview='{item['content_preview']}...'")
                print(f"\n=== Semantic Search for '{args.query}' ===")
                for item in res["semantic"]:
                    print(f"[{item['rank']}] score={item['score']:.4f} doc={item['document_key']} sec='{item['section']}' preview='{item['content_preview']}...'")
        finally:
            await db.close()

    _run_async(execute())


if __name__ == "__main__":
    main()
