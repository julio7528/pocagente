"""Connection-bound persistence adapter for the approved RAG schema."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from uuid import UUID

from psycopg import sql
from pgvector import Vector
from psycopg.types.json import Jsonb
from psycopg.rows import dict_row

from apps.agent_api.app.database.mapping import (
    map_rag_document,
    map_rag_source,
    map_search_candidate,
)
from apps.agent_api.app.database.models import (
    RAGDocumentRecord,
    RAGSourceRecord,
)
from apps.agent_api.app.database.repositories.base import BaseRepository
from apps.agent_api.app.database.repositories.contracts import (
    IngestionOperation,
    IngestionStatus,
    RepositoryRecord,
)
from apps.agent_api.app.rag.models import SearchCandidate


_SOURCE_COLUMNS = (
    "source_id",
    "name",
    "source_type",
    "origin",
    "reference",
    "domain",
    "status",
    "priority",
    "created_at",
    "updated_at",
)
_SOURCE_WRITE_COLUMNS = (
    "source_id",
    "name",
    "source_type",
    "origin",
    "reference",
    "domain",
    "status",
    "priority",
    "updated_at",
)
_SOURCE_REQUIRED_COLUMNS = frozenset(
    {"name", "source_type", "origin", "reference", "status", "updated_at"}
)
_DOCUMENT_COLUMNS = (
    "document_id",
    "source_id",
    "document_key",
    "title",
    "document_type",
    "content_checksum",
    "status",
    "last_ingested_at",
    "created_at",
    "updated_at",
)
_DOCUMENT_WRITE_COLUMNS = (
    "document_id",
    "source_id",
    "document_key",
    "title",
    "document_type",
    "content_checksum",
    "status",
    "last_ingested_at",
    "updated_at",
)
_DOCUMENT_REQUIRED_COLUMNS = frozenset(
    {
        "source_id",
        "document_key",
        "title",
        "document_type",
        "content_checksum",
        "status",
        "last_ingested_at",
        "updated_at",
    }
)
_CHUNK_WRITE_COLUMNS = (
    "content",
    "chunk_order",
    "section",
    "content_type",
    "metadata",
    "embedding",
    "search_vector",
)
_CHUNK_REQUIRED_COLUMNS = frozenset(
    {"content", "chunk_order", "section", "content_type", "metadata", "embedding"}
)
_INGESTION_OPERATIONS = frozenset({"INGEST", "REINGEST", "SKIPPED_UNCHANGED"})
_TERMINAL_INGESTION_STATUSES = frozenset({"SUCCESS", "ERROR", "SKIPPED"})


def _validate_retrieval_limit(limit: int) -> None:
    if not 1 <= limit <= 10:
        raise ValueError("RAG candidate limit must be between 1 and 10")


def _validate_record(
    record: Mapping[str, object],
    *,
    allowed: tuple[str, ...],
    required: frozenset[str],
) -> tuple[str, ...]:
    unknown = set(record) - set(allowed)
    if unknown:
        raise ValueError(f"Unsupported fields: {', '.join(sorted(unknown))}")
    missing = required - set(record)
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(sorted(missing))}")
    return tuple(column for column in allowed if column in record)


class RAGRepository(BaseRepository):
    """Persist and retrieve RAG facts through an injected connection."""

    async def begin_read_only_repeatable_read(self) -> None:
        """Pin subsequent RAG reads to one read-only committed snapshot."""

        async with self._cursor() as cursor:
            await cursor.execute(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
            )

    async def get_source_by_id(self, source_id: UUID) -> RAGSourceRecord | None:
        query = """
            SELECT source_id, name, source_type, origin, reference, domain,
                   status, priority, created_at, updated_at
            FROM rag.sources
            WHERE source_id = %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(query, (source_id,))
            row = await cursor.fetchone()
        return map_rag_source(row) if row is not None else None

    async def get_source_by_reference(
        self,
        origin: str,
        reference: str,
    ) -> RAGSourceRecord | None:
        query = """
            SELECT source_id, name, source_type, origin, reference, domain,
                   status, priority, created_at, updated_at
            FROM rag.sources
            WHERE origin = %s AND reference = %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(query, (origin, reference))
            row = await cursor.fetchone()
        return map_rag_source(row) if row is not None else None

    async def register_source(self, source: RepositoryRecord) -> RAGSourceRecord:
        columns = _validate_record(
            source,
            allowed=_SOURCE_WRITE_COLUMNS,
            required=_SOURCE_REQUIRED_COLUMNS,
        )
        query = sql.SQL(
            "INSERT INTO rag.sources ({columns}) VALUES ({values}) "
            "RETURNING {returning}"
        ).format(
            columns=sql.SQL(", ").join(map(sql.Identifier, columns)),
            values=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
            returning=sql.SQL(", ").join(map(sql.Identifier, _SOURCE_COLUMNS)),
        )
        parameters = tuple(source[column] for column in columns)
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(query, parameters)
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Source registration returned no row")
        return map_rag_source(row)

    async def get_document_by_id(
        self,
        document_id: UUID,
    ) -> RAGDocumentRecord | None:
        query = """
            SELECT document_id, source_id, document_key, title, document_type,
                   content_checksum, status, last_ingested_at, created_at, updated_at
            FROM rag.documents
            WHERE document_id = %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(query, (document_id,))
            row = await cursor.fetchone()
        return map_rag_document(row) if row is not None else None

    async def get_document_by_key(
        self,
        source_id: UUID,
        document_key: str,
    ) -> RAGDocumentRecord | None:
        query = """
            SELECT document_id, source_id, document_key, title, document_type,
                   content_checksum, status, last_ingested_at, created_at, updated_at
            FROM rag.documents
            WHERE source_id = %s AND document_key = %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(query, (source_id, document_key))
            row = await cursor.fetchone()
        return map_rag_document(row) if row is not None else None

    async def document_checksum_changed(
        self,
        document_id: UUID,
        content_checksum: str,
    ) -> bool:
        query = """
            SELECT (content_checksum IS DISTINCT FROM %s OR status <> 'ACTIVE') AS changed
            FROM rag.documents
            WHERE document_id = %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(query, (content_checksum, document_id))
            row = await cursor.fetchone()
        return True if row is None else bool(row["changed"])

    async def save_document(self, document: RepositoryRecord) -> RAGDocumentRecord:
        columns = _validate_record(
            document,
            allowed=_DOCUMENT_WRITE_COLUMNS,
            required=_DOCUMENT_REQUIRED_COLUMNS,
        )
        query = sql.SQL(
            "INSERT INTO rag.documents ({columns}) VALUES ({values}) "
            "ON CONFLICT (source_id, document_key) DO UPDATE SET "
            "title = EXCLUDED.title, document_type = EXCLUDED.document_type, "
            "content_checksum = EXCLUDED.content_checksum, status = EXCLUDED.status, "
            "last_ingested_at = EXCLUDED.last_ingested_at, updated_at = EXCLUDED.updated_at "
            "RETURNING {returning}"
        ).format(
            columns=sql.SQL(", ").join(map(sql.Identifier, columns)),
            values=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
            returning=sql.SQL(", ").join(map(sql.Identifier, _DOCUMENT_COLUMNS)),
        )
        parameters = tuple(document[column] for column in columns)
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(query, parameters)
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Document persistence returned no row")
        return map_rag_document(row)

    async def replace_document_chunks(
        self,
        document_id: UUID,
        chunks: Sequence[RepositoryRecord],
    ) -> None:
        if not chunks:
            raise ValueError("Chunk replacement cannot be empty")

        parameters: list[tuple[object, ...]] = []
        seen_orders: set[object] = set()
        for chunk in chunks:
            _validate_record(
                chunk,
                allowed=_CHUNK_WRITE_COLUMNS,
                required=_CHUNK_REQUIRED_COLUMNS,
            )
            metadata = chunk["metadata"]
            if not isinstance(metadata, Mapping):
                raise ValueError("Chunk metadata must be a JSON object")
            chunk_order = chunk["chunk_order"]
            if chunk_order in seen_orders:
                raise ValueError("Chunk orders must be unique within a replacement")
            seen_orders.add(chunk_order)
            search_vector = chunk.get("search_vector")
            parameters.append(
                (
                    document_id,
                    chunk["content"],
                    chunk_order,
                    chunk["section"],
                    chunk["content_type"],
                    Jsonb(dict(metadata)),
                    chunk["embedding"],
                    search_vector,
                    search_vector,
                    search_vector,
                    chunk["section"],
                    chunk["content"],
                    chunk["content"],
                    document_id,
                )
            )

        delete_query = "DELETE FROM rag.chunks WHERE document_id = %s"
        insert_query = """
            INSERT INTO rag.chunks (
                document_id, content, chunk_order, section, content_type,
                metadata, embedding, search_vector
            )
            SELECT
                %s, %s, %s, %s, %s, %s, %s,
                CASE
                    WHEN %s::text IS NOT NULL AND %s::text <> '' THEN %s::tsvector
                    ELSE (
                        setweight(to_tsvector('portuguese', coalesce(d.title, '')), 'A') ||
                        setweight(to_tsvector('portuguese', coalesce(%s, '')), 'B') ||
                        setweight(to_tsvector('portuguese', coalesce(%s, '')), 'C') ||
                        setweight(to_tsvector('simple', coalesce(%s, '')), 'D')
                    )
                END
            FROM rag.documents d WHERE d.document_id = %s
        """
        async with self._cursor() as cursor:
            await cursor.execute(delete_query, (document_id,))
            await cursor.executemany(insert_query, parameters)

    async def start_ingestion_run(
        self,
        source_id: UUID,
        document_id: UUID | None,
        operation: IngestionOperation,
    ) -> int:
        if operation not in _INGESTION_OPERATIONS:
            raise ValueError("Unsupported ingestion operation")
        query = """
            INSERT INTO rag.ingestion_runs (source_id, document_id, operation)
            VALUES (%s, %s, %s)
            RETURNING ingestion_run_id
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(query, (source_id, document_id, operation))
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Ingestion run creation returned no identity")
        return int(row["ingestion_run_id"])

    async def finish_ingestion_run(
        self,
        ingestion_run_id: int,
        *,
        status: IngestionStatus,
        finished_at: datetime,
        chunks_created: int,
        result_message: str | None,
    ) -> None:
        if status not in _TERMINAL_INGESTION_STATUSES:
            raise ValueError("Ingestion run must finish in a terminal state")
        if chunks_created < 0:
            raise ValueError("chunks_created cannot be negative")
        if status == "SUCCESS" and chunks_created < 1:
            raise ValueError("Successful ingestion must commit at least one chunk")
        if status in {"ERROR", "SKIPPED"} and chunks_created != 0:
            raise ValueError("Error or skipped ingestion cannot commit chunks")
        query = """
            UPDATE rag.ingestion_runs
            SET status = %s, finished_at = %s, chunks_created = %s, result_message = %s
            WHERE ingestion_run_id = %s
        """
        async with self._cursor() as cursor:
            await cursor.execute(
                query,
                (status, finished_at, chunks_created, result_message, ingestion_run_id),
            )

    async def search_lexical_candidates(
        self,
        query: str,
        limit: int,
    ) -> Sequence[SearchCandidate]:
        if not query.strip():
            raise ValueError("Lexical query cannot be blank")
        _validate_retrieval_limit(limit)
        statement = """
            WITH search_query AS (
                SELECT websearch_to_tsquery('portuguese', %s)
                       || websearch_to_tsquery('simple', %s) AS value
            ), ranked AS (
                SELECT c.chunk_id, c.document_id, c.content, c.chunk_order,
                       c.section, c.content_type, c.metadata, c.created_at,
                       d.source_id, d.document_key, d.title, d.document_type,
                       d.content_checksum, d.last_ingested_at,
                       s.name AS source_name, s.source_type, s.origin,
                       s.reference AS source_reference, s.domain, s.priority,
                       ts_rank_cd(c.search_vector, q.value) AS channel_score
                FROM rag.chunks AS c
                JOIN rag.documents AS d ON d.document_id = c.document_id
                JOIN rag.sources AS s ON s.source_id = d.source_id
                CROSS JOIN search_query AS q
                WHERE c.search_vector @@ q.value
                  AND d.status = 'ACTIVE'
                  AND s.status = 'ACTIVE'
            )
            SELECT ranked.*, 'lexical' AS retrieval_channel,
                   row_number() OVER (
                       ORDER BY channel_score DESC, chunk_id ASC
                   ) AS channel_rank
            FROM ranked
            ORDER BY channel_score DESC, chunk_id ASC
            LIMIT %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (query, query, limit))
            rows = await cursor.fetchall()
        return tuple(map_search_candidate(row) for row in rows)

    async def search_semantic_candidates(
        self,
        embedding: Sequence[float],
        limit: int,
    ) -> Sequence[SearchCandidate]:
        embedding_values = (
            embedding.to_list() if isinstance(embedding, Vector) else list(embedding)
        )
        if len(embedding_values) != 384:
            raise ValueError("Semantic query embedding must have 384 dimensions")
        _validate_retrieval_limit(limit)
        statement = """
            WITH ranked AS (
                SELECT c.chunk_id, c.document_id, c.content, c.chunk_order,
                       c.section, c.content_type, c.metadata, c.created_at,
                       d.source_id, d.document_key, d.title, d.document_type,
                       d.content_checksum, d.last_ingested_at,
                       s.name AS source_name, s.source_type, s.origin,
                       s.reference AS source_reference, s.domain, s.priority,
                       c.embedding <=> %s AS channel_score
                FROM rag.chunks AS c
                JOIN rag.documents AS d ON d.document_id = c.document_id
                JOIN rag.sources AS s ON s.source_id = d.source_id
                WHERE d.status = 'ACTIVE'
                  AND s.status = 'ACTIVE'
            )
            SELECT ranked.*, 'semantic' AS retrieval_channel,
                   row_number() OVER (
                       ORDER BY channel_score ASC, chunk_id ASC
                   ) AS channel_rank
            FROM ranked
            ORDER BY channel_score ASC, chunk_id ASC
            LIMIT %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (Vector(embedding_values), limit))
            rows = await cursor.fetchall()
        return tuple(map_search_candidate(row) for row in rows)
