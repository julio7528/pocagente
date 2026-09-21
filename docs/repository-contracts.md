# Getnet Support — Repository Contracts

## Purpose and authority

This document is the detailed authority for Phase 4.8.6 repository ownership,
connection binding, and persistence boundaries. The physical columns, types,
constraints, keys, indexes, relationships, and nullability remain governed by
`docs/database-physical-model.md`; they are not duplicated here.

The durable architectural context is DEC-132, DEC-133, DEC-136, DEC-137, and
the Phase 4.8.6 decision recorded in `docs/decision-log.md`.

## Architecture

```text
FastAPI / Agents
        |
        v
Application Services
        |
        v
Repository Contracts
        |
        v
Concrete Repositories
        |
        v
Injected AsyncConnection
        |
        v
PostgresDatabase / Pool
        |
        v
Psycopg 3 + pgvector
        |
        v
PostgreSQL 17
```

Agents, endpoints, controlled tools, and application services never execute
raw SQL. Concrete repositories are the exclusive SQL persistence boundary.
PostgreSQL MCP remains external development tooling and is not runtime
architecture.

## Repository ownership matrix

| Repository | Schema | Owned tables | Count |
|---|---|---|---:|
| `RAGRepository` | `rag` | `rag.sources`, `rag.documents`, `rag.chunks`, `rag.ingestion_runs` | 4 |
| `OperationalRepository` | `ops` | `ops.automation_runs`, `ops.incoming_emails`, `ops.email_attachments`, `ops.service_requests`, `ops.establishments`, `ops.execution_log` | 6 |
| `AuditRepository` | `audit` | `audit.security_events` | 1 |

The inventory is exactly three schemas and eleven tables. No repository owns
an unapproved table, lookup table, migration table, conversation table, or
human-handoff table.

## Connection-bound repository contract

Every concrete repository receives one existing
`psycopg.AsyncConnection[Any]` through dependency injection and retains that
exact object for its operations.

A repository:

- does not create or acquire a connection;
- does not create or own an `AsyncConnectionPool`;
- does not own or call `PostgresDatabase.connection()`;
- does not close its injected connection;
- does not call `commit()` or `rollback()`;
- does not create an independent transaction boundary;
- performs no network I/O or SQL during construction;
- has no global singleton instance.

The external application/database transaction boundary owns connection and
transaction lifecycle. Multiple repositories may share the same physical
connection so Phase 4.8.10 can orchestrate one atomic transaction across
repository domains. Repositories do not orchestrate each other.

`BaseRepository` is the minimal common foundation. It stores the injected
connection and centralizes secret-safe translation of recognized driver failures
at the cursor boundary. Concrete SQL implementations were completed in Phases
4.8.7–4.8.9.

## Contract typing and mapping boundary

The async protocols are defined in
`apps/agent_api/app/database/repositories/contracts.py`.

As of Phase 4.8.11, typed database read models are implemented in
`apps/agent_api/app/database/models.py` and mapped centrally through
`apps/agent_api/app/database/mapping.py`. Repository read methods no longer
expose raw Psycopg `Mapping[str, object]` rows. Read-side methods return
typed, immutable Pydantic models (`RAGSourceRecord`, `RAGDocumentRecord`,
`AutomationRunRecord`, `ServiceRequestRecord`, `EstablishmentRecord`,
`ExecutionLogRecord`, `ProtocolStatusFacts`, `ExecutionFailureEvidence`,
and `SecurityEventRecord`).

The RAG candidate retrieval methods (`search_lexical_candidates` and
`search_semantic_candidates`) return `Sequence[SearchCandidate]`, where
`SearchCandidate` pairs a physical `PersistedChunk` with full
`RetrievalProvenance`. Repositories do not return final `RetrievedChunk` objects;
the Phase 7 ranking/RRF layer produces them.

`RepositoryRecord = Mapping[str, object]` remains preserved for repository
write and mutation input payloads.

All contract methods are asynchronous. None is a generic SQL interface:
`execute_sql(...)`, arbitrary `query(...)`, and table/filter APIs are forbidden.
Transaction architecture remains DEC-142 (`PostgresDatabase.transaction()`).
Database error translation is implemented by the infrastructure layer in Phase
4.8.12; application/domain validation errors remain unchanged.

## RAGRepository contract

### Ownership

`RAGRepository` accesses only the four `rag` tables in the ownership matrix.
It never accesses OPS or AUDIT.

### Approved source and document operations

| Operation | Contract method | Approved key or requirement |
|---|---|---|
| Source lookup | `get_source_by_id` | `rag.sources.source_id` PK |
| Canonical source lookup | `get_source_by_reference` | `UNIQUE(origin, reference)` |
| Governed source registration | `register_source` | Stable source identity requirement |
| Document lookup | `get_document_by_id` | `rag.documents.document_id` PK |
| Stable document lookup | `get_document_by_key` | `UNIQUE(source_id, document_key)` |
| Change detection | `document_checksum_changed` | Document PK plus approved current checksum |
| Controlled current-document persistence | `save_document` | Approved current-document lifecycle |

Checksum comparison is anchored by document identity; it does not introduce a
checksum index or global checksum uniqueness.

### Approved chunk and ingestion operations

- `replace_document_chunks` persists the complete current structural chunk set
  for one approved document lifecycle. It preserves chunk provenance but does
  not chunk content, generate embeddings, build FTS input, or commit.
- `start_ingestion_run` records one approved `INGEST`, `REINGEST`, or
  `SKIPPED_UNCHANGED` run.
- `finish_ingestion_run` records an approved terminal status, completion time,
  committed chunk count, and sanitized result information.

Atomic current-chunk replacement and document/run updates are orchestrated by
the future external transaction boundary. The repository never commits the
operation independently.

### Approved retrieval operations

- `search_lexical_candidates(query, limit)` is the PostgreSQL FTS
  candidate boundary backed by `rag.chunks.search_vector` and its GIN access
  path.
- `search_semantic_candidates(embedding, limit)` is the exact pgvector
  cosine candidate boundary over `rag.chunks.embedding`.

Callers supply bounded limits. Temporary repository records preserve physical
provenance until Phase 4.8.11 maps them to final RAG models. Retrieval
implementations must enforce active source and active document eligibility.
RRF, grounding, LLM reasoning, embeddings, and chunk generation remain above
repository persistence. Phase 7 retrieves at most 10 candidates per channel,
uses one read-only repeatable-read snapshot for both channels, applies rank-only
RRF with k=60, deduplicates by physical `chunk_id`, and emits at most five
`RetrievedChunk` results. Grounding remains a later phase.

## OperationalRepository contract

### Ownership

`OperationalRepository` accesses only the six `ops` tables in the ownership
matrix. It never accesses RAG or AUDIT.

### Approved persistence operations

The contract defines deterministic create/update boundaries for automation
runs, incoming emails, attachments, service requests, establishments, and
append-only execution-log facts. These operations preserve the lifecycle,
provenance, and sanitization rules from the physical model. They do not commit
or create transactions.

### Approved lookup and evidence operations

| Requirement | Contract methods | Approved key/access path |
|---|---|---|
| Automation-run facts | `get_automation_run` | `run_id` PK |
| Protocol identity | `get_service_request_by_protocol` | `UNIQUE(protocol_number)` |
| Establishments for request | `list_establishments_for_request` | Request-leading approved UNIQUE indexes |
| Run chronology | `list_execution_timeline_for_run` | `(run_id, logged_at DESC)` |
| Request chronology | `list_execution_timeline_for_request` | Partial `(request_id, logged_at DESC)` |
| Protocol status evidence | `get_protocol_status_facts` | Protocol UNIQUE plus request-related OPS facts |
| Failure evidence | `get_execution_failure_facts` | Protocol UNIQUE and optional run chronology |

The final two operations support future application services behind the
approved controlled tools without exposing repositories directly as tools:

```text
Customer Support Agent
        |
        v
lookup_protocol_status / inspect_execution_failure
        |
        v
Customer Support Application Service
        |
        v
OperationalRepository
        |
        v
PostgreSQL OPS
```

The repository returns observed operational facts and sanitized evidence. It
does not diagnose root cause, label probable cause, make LLM conclusions,
decide human escalation, or perform handoff.

## AuditRepository contract

### Ownership

`AuditRepository` accesses only `audit.security_events`. It never accesses RAG
or OPS and is not a general operational log.

### Approved operations

- `write_sanitized_security_event` persists an already sanitized event.
- `get_security_event` retrieves one event by its approved PK.
- `list_security_events_by_request_reference` uses the approved request
  correlation access path.
- `list_unreviewed_security_events` supports the approved review index.
- `update_security_event_review` records authorized review state supported by
  the physical model.

The required upstream security flow is:

```text
input
  -> security detection
  -> sanitization / redaction
  -> AuditRepository
  -> audit.security_events
```

AuditRepository receives only secret-safe persistence input. It does not
inspect raw prompts, discover secrets, or sanitize content itself. Passwords,
API keys, tokens, cookies, private keys, connection strings, database
credentials, secret locations, and raw unsanitized protected content must
never reach its write contract.

## Cross-domain composition rule

A repository directly queries only the schema and tables it owns. RAG, OPS,
and AUDIT repositories never query each other's tables. Cross-domain business
composition occurs in application services using separate repositories, which
may share one externally managed connection and transaction.

No tool or agent receives raw SQL access. No repository exposes arbitrary SQL,
table names, or caller-defined filters.

## Transaction boundary

`PostgresDatabase` owns explicit transaction orchestration. The approved
application entry point is:

```python
async with database.transaction() as connection:
    ...
```

One `AsyncConnectionPool.connection()` checkout supplies one
`AsyncConnection`, and Psycopg's `connection.transaction()` context owns the
completion semantics: normal exit commits and exceptional exit rolls back while
the original exception propagates. The pool receives the borrowed connection
back after the transaction context exits.

Multiple repositories may receive that exact yielded connection for one atomic
operation. Repositories never commit, roll back, close the connection, or
create a transaction themselves. `connection()` remains the lower-level pooled
borrowing primitive; `transaction()` is used when operations must succeed or
fail together, including future RAG publication replacement plus document/run
updates.

The initial POC has no custom nested-transaction, savepoint, ambient-context,
or Unit-of-Work abstraction. Application services already inside a transaction
reuse its injected connection and repositories.

## Deferred implementation boundaries

- Concrete RAG SQL: implemented in Phase 4.8.7.
- Concrete OPS SQL: implemented in Phase 4.8.8.
- Concrete AUDIT SQL: implemented in Phase 4.8.9.
- Explicit application transaction orchestration: implemented in Phase 4.8.10.
- Final row-to-model mapping: implemented in Phase 4.8.11.
- Database error translation: implemented in Phase 4.8.12.
- Real PostgreSQL connectivity validation: completed in Phase 4.8.13.
- Real repository/basic-operation validation: completed in Phase 4.8.14.

All concrete statements are parameterized, schema-qualified, connection-bound,
and limited to each repository's owned tables. Validation remains mock-based:
no real database connection, migration, schema change, or database object was
introduced. Lexical and semantic retrieval return `Sequence[SearchCandidate]`;
`RepositoryRecord = Mapping[str, object]` is restricted to write and mutation
payloads. The pre-4.8.11 repository-record retrieval wording is historical
context only. Phase 4.8.14 exercised every public concrete repository method
against real PostgreSQL, including typed mappings, RAG FTS/exact-cosine search,
OPS factual evidence, AUDIT review flows, safe integrity-error translation, and
transaction rollback. A final read-only check confirmed zero synthetic
integration records remained.

Phase 4.8 is complete under DEC-147. These repository contracts remain the
authoritative persistence boundary for subsequent phases; Phase 4.9 seed-data
work is next and was not started by the Phase 4.8 validation.
