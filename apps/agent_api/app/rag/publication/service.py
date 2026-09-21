"""Central application service for atomic RAG publication to PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.repositories.rag import RAGRepository
from apps.agent_api.app.rag.embeddings.fastembed import FastEmbedAdapter
from apps.agent_api.app.rag.ingestion.models import PreparedDocument, PreparedIngestion

from .models import PublicationChunk, PublicationResult


_ALLOWED_DOCUMENT_TYPES = frozenset(
    {"PDD", "SDD", "TECHNICAL_OVERVIEW", "POLICY", "PUBLIC_PAGE", "OTHER"}
)


def resolve_document_type(document: PreparedDocument) -> str:
    """Resolve the document_type string to satisfy ck_documents__document_type_allowed."""

    for candidate in (
        getattr(document.metadata, "source_class", None),
        getattr(document.metadata, "source_type", None),
    ):
        if candidate and candidate.upper() in _ALLOWED_DOCUMENT_TYPES:
            return candidate.upper()

    combined = f"{document.document_id} {document.metadata.title}".lower()
    if "pdd" in combined:
        return "PDD"
    if "sdd" in combined:
        return "SDD"
    if "technical" in combined or "overview" in combined:
        return "TECHNICAL_OVERVIEW"
    if "policy" in combined or document.database_source_type == "INTERNAL_POLICY":
        return "POLICY"
    if document.database_origin == "PUBLIC":
        return "PUBLIC_PAGE"

    return "OTHER"


class RAGPublicationService:
    """Coordinate embeddings, FTS, and atomic PostgreSQL persistence."""

    def __init__(
        self,
        database: PostgresDatabase,
        embed_adapter: FastEmbedAdapter | None = None,
    ) -> None:
        self._database = database
        self._embed_adapter = embed_adapter or FastEmbedAdapter()

    async def publish(
        self,
        prepared: PreparedIngestion,
        source_id: UUID,
    ) -> PublicationResult:
        """Publish a PreparedIngestion candidate atomically to PostgreSQL."""

        # Handle SKIPPED_UNCHANGED: No embeddings, no chunk replacement, no content mutation
        if prepared.operation == "SKIPPED_UNCHANGED":
            async with self._database.transaction() as connection:
                repository = RAGRepository(connection)
                existing = await repository.get_document_by_key(
                    source_id, prepared.document.document_id
                )
                doc_id = existing.document_id if existing else None
                run_id = await repository.start_ingestion_run(
                    source_id=source_id,
                    document_id=doc_id,
                    operation="SKIPPED_UNCHANGED",
                )
                await repository.finish_ingestion_run(
                    run_id,
                    status="SKIPPED",
                    finished_at=datetime.now(UTC),
                    chunks_created=0,
                    result_message=(
                        f"Document '{prepared.document.document_id}' checksum unchanged; "
                        "skipping re-embedding and publication."
                    ),
                )
                return PublicationResult(
                    operation="SKIPPED_UNCHANGED",
                    status="SKIPPED",
                    source_id=source_id,
                    document_id=doc_id,
                    document_key=prepared.document.document_id,
                    chunks_published=0,
                    ingestion_run_id=run_id,
                )

        # Pre-transaction validation and embedding generation (INGEST or REINGEST)
        if not prepared.chunks:
            raise ValueError(
                f"Cannot publish document '{prepared.document.document_id}' with zero chunks"
            )

        texts = [chunk.content for chunk in prepared.chunks]
        embeddings = self._embed_adapter.embed_documents(texts)
        if len(embeddings) != len(prepared.chunks):
            raise ValueError(
                f"Mismatch between chunk count ({len(prepared.chunks)}) "
                f"and embedding count ({len(embeddings)})"
            )

        publication_chunks = [
            PublicationChunk(
                content=chunk.content,
                chunk_order=chunk.chunk_order,
                section=chunk.section,
                boundary_type=chunk.boundary_type,
                content_type=chunk.content_type,
                metadata=dict(chunk.metadata),
                embedding=embeddings[i],
                search_vector=None,
            )
            for i, chunk in enumerate(prepared.chunks)
        ]

        # Atomic PostgreSQL publication transaction
        async with self._database.transaction() as connection:
            repository = RAGRepository(connection)

            source = await repository.get_source_by_id(source_id)
            if source is None:
                raise ValueError(f"Source with id '{source_id}' does not exist in rag.sources")

            existing = await repository.get_document_by_key(
                source_id, prepared.document.document_id
            )
            existing_doc_id = existing.document_id if existing else None

            run_id = await repository.start_ingestion_run(
                source_id=source_id,
                document_id=existing_doc_id,
                operation=prepared.operation,
            )

            now = datetime.now(UTC)
            document_type = resolve_document_type(prepared.document)
            saved_doc = await repository.save_document(
                {
                    "source_id": source_id,
                    "document_key": prepared.document.document_id,
                    "title": prepared.document.metadata.title,
                    "document_type": document_type,
                    "content_checksum": prepared.document.content_checksum,
                    "status": "ACTIVE",
                    "last_ingested_at": now,
                    "updated_at": now,
                }
            )

            chunk_records = [chunk.to_repository_record() for chunk in publication_chunks]
            await repository.replace_document_chunks(saved_doc.document_id, chunk_records)

            await repository.finish_ingestion_run(
                run_id,
                status="SUCCESS",
                finished_at=datetime.now(UTC),
                chunks_created=len(publication_chunks),
                result_message=(
                    f"Successfully published {len(publication_chunks)} chunks "
                    f"for document '{saved_doc.document_key}'."
                ),
            )

            return PublicationResult(
                operation=prepared.operation,
                status="SUCCESS",
                source_id=source_id,
                document_id=saved_doc.document_id,
                document_key=saved_doc.document_key,
                chunks_published=len(publication_chunks),
                ingestion_run_id=run_id,
            )
