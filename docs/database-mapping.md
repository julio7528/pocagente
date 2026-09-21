# Database Result Mapping Layer

## Purpose

Raw Psycopg rows (`dict_row` mappings) must not escape the database persistence boundary into application services, workflows, or RAG orchestration.

Phase 4.8.11 establishes a centralized, deterministic, and type-safe result mapping layer that translates raw relational query outputs into immutable Pydantic read models while preserving physical PostgreSQL typing.

---

## Architecture

The result mapping layer sits strictly between the repository persistence boundary and higher-level application components:

```text
PostgreSQL
    |
    v
Psycopg dict_row
    |
    v
Repository (SQL persistence boundary)
    |
    v
apps.agent_api.app.database.mapping
    |
    v
Typed Pydantic/Python Result Models (database.models & rag.models)
    |
    v
Application Service / RAG Pipeline / Handlers
```

### Key Architectural Boundaries

1. **Repositories Remain the SQL Boundary**: Repositories execute parameterized SQL queries and delegate row-to-model conversion to centralized mapping functions.
2. **Centralized Mapping (`database/mapping.py`)**: The exclusive transformation boundary. It contains no SQL statements, no cursor calls, no connection/pool management, and no transaction logic.
3. **Dedicated Result Models (`database/models.py`)**: Strict, immutable Pydantic models (`extra="forbid", frozen=True`). These are not ORM entities; they do not open connections or mutate database state.
4. **No ORM**: No SQLAlchemy, no Alembic, no psycopg2, no asyncpg, and no dynamic table reflection.

---

## Result-Model Matrix

All physical types and schemas conform authoritatively to [database-physical-model.md](database-physical-model.md).

| Repository | Method | SQL Result Source | Centralized Mapper | Result Model | Return Cardinality |
|---|---|---|---|---|---|
| `RAGRepository` | `get_source_by_id` | `rag.sources` SELECT | `map_rag_source` | `RAGSourceRecord` | `RAGSourceRecord \| None` |
| `RAGRepository` | `get_source_by_reference` | `rag.sources` SELECT | `map_rag_source` | `RAGSourceRecord` | `RAGSourceRecord \| None` |
| `RAGRepository` | `register_source` | `rag.sources` RETURNING | `map_rag_source` | `RAGSourceRecord` | `RAGSourceRecord` |
| `RAGRepository` | `get_document_by_id` | `rag.documents` SELECT | `map_rag_document` | `RAGDocumentRecord` | `RAGDocumentRecord \| None` |
| `RAGRepository` | `get_document_by_key` | `rag.documents` SELECT | `map_rag_document` | `RAGDocumentRecord` | `RAGDocumentRecord \| None` |
| `RAGRepository` | `save_document` | `rag.documents` RETURNING | `map_rag_document` | `RAGDocumentRecord` | `RAGDocumentRecord` |
| `RAGRepository` | `search_lexical_candidates` | `rag.chunks` JOIN docs & sources | `map_search_candidate` | `SearchCandidate` | `Sequence[SearchCandidate]` |
| `RAGRepository` | `search_semantic_candidates` | `rag.chunks` JOIN docs & sources | `map_search_candidate` | `SearchCandidate` | `Sequence[SearchCandidate]` |
| `OperationalRepository` | `get_automation_run` | `ops.automation_runs` SELECT | `map_automation_run` | `AutomationRunRecord` | `AutomationRunRecord \| None` |
| `OperationalRepository` | `get_service_request_by_protocol` | `ops.service_requests` SELECT | `map_service_request` | `ServiceRequestRecord` | `ServiceRequestRecord \| None` |
| `OperationalRepository` | `list_establishments_for_request` | `ops.establishments` SELECT | `map_establishment` | `EstablishmentRecord` | `Sequence[EstablishmentRecord]` |
| `OperationalRepository` | `list_execution_timeline_for_run` | `ops.execution_log` SELECT | `map_execution_log` | `ExecutionLogRecord` | `Sequence[ExecutionLogRecord]` |
| `OperationalRepository` | `list_execution_timeline_for_request` | `ops.execution_log` SELECT | `map_execution_log` | `ExecutionLogRecord` | `Sequence[ExecutionLogRecord]` |
| `OperationalRepository` | `get_protocol_status_facts` | `ops.service_requests` + JSONB aggs | `map_protocol_status_facts` | `ProtocolStatusFacts` | `Sequence[ProtocolStatusFacts]` |
| `OperationalRepository` | `get_execution_failure_facts` | JOIN sr, log, runs + JSONB prev | `map_execution_failure_evidence` | `ExecutionFailureEvidence` | `Sequence[ExecutionFailureEvidence]` |
| `AuditRepository` | `get_security_event` | `audit.security_events` SELECT | `map_security_event` | `SecurityEventRecord` | `SecurityEventRecord \| None` |
| `AuditRepository` | `list_security_events_by_request_reference` | `audit.security_events` SELECT | `map_security_event` | `SecurityEventRecord` | `Sequence[SecurityEventRecord]` |
| `AuditRepository` | `list_unreviewed_security_events` | `audit.security_events` SELECT | `map_security_event` | `SecurityEventRecord` | `Sequence[SecurityEventRecord]` |

---

## RAG Retrieval Mapping

### Complete RAG Model Hierarchy and Responsibilities

Ingestion-time chunking, database persistence mapping, candidate retrieval, and post-ranking results serve distinct architectural concerns:

```text
Chunk
    structural ingestion representation

PersistedChunk
    physical persisted/retrieved rag.chunks representation

SearchCandidate
    per-channel lexical/semantic candidate

RetrievedChunk
    final fused/ranked retrieval result

RAGResult
    final retrieval output
```

- `Chunk` (`apps.agent_api.app.rag.models.Chunk`): Represents a pre-ingestion document fragment used by chunkers, with string identifiers and structural `boundary_type` (`section`, `business_rule`, `technical_symbol`). It is never used as a database row model.
- `PersistedChunk` (`apps.agent_api.app.rag.models.PersistedChunk`): Represents a physical chunk row read from `rag.chunks`, containing `chunk_id: int` (BIGINT PK), `document_id: UUID`, `content: str`, `chunk_order: int`, `section: str | None`, `content_type: str`, `metadata: Mapping[str, object]`, and `created_at: datetime`. It does not contain ranking, score, or fused channel attributes.
- `RetrievalProvenance` (`apps.agent_api.app.rag.models.RetrievalProvenance`): Captures joined document and source provenance fields (`source_id: UUID`, `source_name`, `origin`, `source_reference`, `priority`, `document_key`, `title`, `document_type`, `content_checksum`, `last_ingested_at`).
- `SearchCandidate` (`apps.agent_api.app.rag.models.SearchCandidate`): Pairs `PersistedChunk` with `RetrievalProvenance`, channel identification (`Literal["lexical", "semantic"]`), `channel_rank: int` (ge=1), and `channel_score: float | None`. Database mapping constructs `SearchCandidate` containing `PersistedChunk`.
- `RetrievedChunk` (`apps.agent_api.app.rag.models.RetrievedChunk`): The final fused and ranked retrieval result produced by the future RRF ranking layer. It combines `chunk: PersistedChunk`, `provenance: RetrievalProvenance`, `rank: int` (ge=1), `score: float`, and `matched_channels: tuple[Literal["lexical", "semantic"], ...]`. Grounding (`ContextBuilder`) consumes `RetrievedChunk`. Database mapping does **not** construct `RetrievedChunk`.
- `RAGResult` (`apps.agent_api.app.rag.models.RAGResult`): Provider-neutral final output holding `query: str`, `chunks: list[RetrievedChunk]`, and `top_k: int`.

Both `search_lexical_candidates` and `search_semantic_candidates` return `Sequence[SearchCandidate]`. Database mapping creates `PersistedChunk` and `SearchCandidate`, not final `RetrievedChunk` objects.

---

## OPS Mapping & Nested Fact Aggregates

Operational queries return deterministic facts without interpretation:

- `ProtocolStatusFacts`: Provides a structured factual aggregate of a protocol's request attributes, establishments (`tuple[EstablishmentRecord, ...]`), and chronological execution events (`tuple[ExecutionLogRecord, ...]`). The mapper individually validates each item inside the PostgreSQL `jsonb_agg` array.
- `ExecutionFailureEvidence`: Captures failure log facts joined with run and request state. When an earlier successful event exists on the same request, it is mapped to `last_successful_evidence: ExecutionLogRecord | None`.
- No root-cause analysis, escalation logic, or LLM interpretation is introduced in mapping.

---

## AUDIT Mapping

- `SecurityEventRecord`: Represents sanitized audit events from `audit.security_events`.
- Mapping validates physical row structure only.
- Prohibited secret keys and sensitive payload fields are strictly forbidden by database and repository constraints.

---

## Write Payloads vs. Read Results Distinction

`RepositoryRecord = Mapping[str, object]` remains approved and preserved for repository **write** payloads:
- `register_source(source: RepositoryRecord)`
- `save_document(document: RepositoryRecord)`
- `replace_document_chunks(..., chunks: Sequence[RepositoryRecord])`
- `create_automation_run(run: RepositoryRecord)`
- `update_automation_run(..., changes: RepositoryRecord)`
- `create_incoming_email(email: RepositoryRecord)`
- `update_incoming_email(..., changes: RepositoryRecord)`
- `create_email_attachment(attachment: RepositoryRecord)`
- `update_email_attachment(..., changes: RepositoryRecord)`
- `create_service_request(request: RepositoryRecord)`
- `update_service_request(..., changes: RepositoryRecord)`
- `upsert_establishment(establishment: RepositoryRecord)`
- `update_establishment(..., changes: RepositoryRecord)`
- `append_execution_log(event: RepositoryRecord)`
- `write_sanitized_security_event(event: RepositoryRecord)`

This phase intentionally avoids expanding into an unnecessary write-side command DTO redesign.

---

## Failure Policy

Mapping errors are validation failures at this phase:
- Pydantic `ValidationError` propagates directly if unexpected fields, missing required fields, or malformed data are encountered.
- Custom database exceptions, Psycopg exception wrapping, and retry classification are deferred to Phase 4.8.12 (`TRATAMENTO DE ERROS DE BANCO`).

---

## Exclusions & Non-Goals

1. No real PostgreSQL connections are opened (Phase 4.8.13).
2. No real repository execution against live PostgreSQL (Phase 4.8.14).
3. No custom database exception hierarchy (Phase 4.8.12).
4. No ORM models or dynamic reflection.
5. No changes to transaction lifecycle or pool management (DEC-142 remains authoritative).
