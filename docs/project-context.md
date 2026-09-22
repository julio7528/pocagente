# Getnet Support — Project Context

## Purpose

This document records the current approved working context of the getnet-support
POC. It allows future agents and developers to resume work from repository
evidence without relying on chat history.

## Current Phase

**Current major phase:** Phase 11 EVALUATION RUNNER

**Current task:** Phase 11 EVALUATION RUNNER — closure remediation and Phase
11.6 revalidation complete

**Current subtask:** Phase 11 is CLOSED. Dataset v1.1 preserves the historical
v1.0 blocked evidence while adding reviewed deterministic claim support, one
explicit insufficient-evidence case, and one synthetic supplied-secret
security case. The source manifest remains 6/6. The production Router now
recognizes the missing Portuguese protected-request semantics through the
existing Phase 10 owner, and PostgreSQL lexical retrieval uses bounded
natural-language OR normalization rather than an all-term query.

Fresh official evidence processed 27 RAG cases (22 `RETRIEVAL`, 1
`RULE_VS_OBSERVED`, 3 `SECURITY`, 1 `INSUFFICIENT_EVIDENCE`) with 24 retrieval
executions. Top-5 is 21/23 PASS, provenance 23/23 PASS, unsupported facts 0/3
PASS, insufficient evidence 1/1 PASS, security block and AUDIT 3/3 PASS,
redaction 1/1 PASS, and Challenge 14/14 PASS. Overall is `PASS`; the two
remaining expected-source misses (`rag-021`, `rag-023`) remain visible as
authentic per-case findings. The Phase 11.6 matrix records 57 SATISFIED, zero
FAILED, and zero BLOCKED_NOT_MEASURABLE requirements. No blocker was waived.
Phase 12 is next but has not started.

**Conceptual schema architecture status:**

1. `rag` responsibility — completed
2. `ops` responsibility — completed
3. `audit` responsibility — completed
4. limits and flow between schemas — completed
5. complete conceptual schema architecture — approved
6. 4.2 RAG detailed schema architecture — completed
7. 4.3 OPS detailed schema architecture — completed
8. 4.4 AUDIT detailed schema architecture — completed
9. Phase 5 Ingestion Preparation — completed
10. Phase 6 Executable FastEmbed + Atomic RAG Publication — completed

**Current status:**

- PostgreSQL Docker infrastructure is working.
- PostgreSQL 17 is running; the observed container version is 17.11.
- pgvector 0.8.6 is enabled.
- The project roadmap records that the DBeaver connection works.
- Phase 4.1 is complete.
- Phase 4.2 is complete; detailed conceptual architecture of the RAG schema (`rag.sources`, `rag.documents`, `rag.chunks`, `rag.ingestion_runs`) is approved.
- Phase 4.3 is complete; detailed conceptual architecture of the OPS schema (`ops.automation_runs`, `ops.incoming_emails`, `ops.email_attachments`, `ops.service_requests`, `ops.establishments`, `ops.execution_log`) is approved.
- RAG, OPS, and AUDIT conceptual responsibilities and boundaries are approved.
- The Phase 4.6.3 migration created the `rag`, `ops`, and `audit` schemas.
- Phases 4.4 through 4.9 are complete and approved.
- Phase 4.6.1 Migration Strategy is approved and complete: native sequential PostgreSQL SQL migration files; Alembic and SQLAlchemy are excluded; the scope is structural only; and migrations are decoupled from application startup.
- Applied migrations are immutable and evolve only through new sequential files. They contain no business or operational data; synthetic POC seed is deferred to phase 4.9, later data enters through runtime inserts, and rollback is explicit and controlled without automation.
- Phase 4.6.2 Migration Structure and Execution Order is approved and complete: the initial construction is defined as exactly six sequential files, 0001 through 0006, covering prerequisites/schemas, RAG tables, OPS tables, the independent AUDIT table, constraints, and indexes.
- The approved order follows table dependencies; primary keys, NOT NULL requirements, and defaults are created with tables; constraints are ordered UNIQUE, CHECK, simple foreign keys, then composite foreign keys; 0006 contains 21 explicit indexes without duplicate UNIQUE-backed indexes.
- `database/migrations/0001_prerequisites_and_schemas.sql` exists and was
  successfully executed through PostgreSQL MCP. PostgreSQL major 17, pgvector
  0.8.6, vector type availability, zero application tables, and zero
  application indexes were validated.
- `database/migrations/0002_rag_tables.sql` exists and was successfully
  executed through PostgreSQL MCP. It materialized `rag.sources`,
  `rag.documents`, `rag.chunks`, and `rag.ingestion_runs` with the approved
  UUID/BIGINT identity PK strategy, TIMESTAMPTZ fields, and deterministic
  defaults. `rag.chunks.metadata` is JSONB, `embedding` is VECTOR(384), and
  `search_vector` is TSVECTOR.
- The RAG tables contain no application data. No document-version table, FK,
  business UNIQUE, CHECK, explicit application index, GIN index, ANN/HNSW/
  IVFFlat index, trigger, function, procedure, view, or materialized view was
  created. Atomic document replacement remains a runtime responsibility.
- `database/migrations/0003_ops_tables.sql` exists and was successfully
  executed through PostgreSQL MCP. It materialized `ops.automation_runs`,
  `ops.incoming_emails`, `ops.email_attachments`, `ops.service_requests`,
  `ops.establishments`, and `ops.execution_log`: 65 approved columns with
  BIGINT `BY DEFAULT` identity PKs, approved TIMESTAMPTZ/nullability/defaults,
  R1/R2 provenance, service-request protocol ownership, establishment handoff,
  and optional execution-log correlations.
- OPS tables contain no application data. No OPS FK, business UNIQUE, CHECK,
  explicit application index, trigger, function, procedure, view, or
  materialized view was created; 0005 and 0006 retain those responsibilities.
- `database/migrations/0004_audit_table.sql` exists and was successfully
  executed through PostgreSQL MCP. It materialized `audit.security_events`
  with 14 approved columns, BIGINT `BY DEFAULT` identity PK, and approved
  TIMESTAMPTZ/nullability/defaults. `request_reference` remains nullable TEXT
  correlation only, without an FK.
- AUDIT contains no application data, external FK, business UNIQUE, CHECK,
  explicit application index, auxiliary review table, trigger, procedure,
  secret-scanning function, or raw secret/request-payload storage. No automatic
  retention or TTL was introduced. All 11 approved application tables exist.
- `database/migrations/0005_constraints.sql` exists and was successfully
  executed through PostgreSQL MCP. It materialized all 10 approved UNIQUE
  constraints, 14 foreign keys, and 59 approved CHECK constraints (20 RAG,
  28 OPS, 11 AUDIT). Catalog validation confirmed all FK actions: ON UPDATE
  RESTRICT; the sole CASCADE from documents to chunks; targeted document-only
  SET NULL for ingestion history; and SET NULL for optional execution-log
  entity references.
- `database/migrations/0006_indexes.sql` was successfully executed through
  PostgreSQL MCP. RO catalog validation confirmed exactly 21 approved explicit
  access-path indexes: 3 RAG, 14 OPS, and 4 AUDIT. The FTS index
  `gin_chunks__search_vector` uses GIN; all five approved partial predicates
  are present; and the 10 UNIQUE-backed and 11 PK-backed indexes remain
  unduplicated, for 42 application indexes and 31 non-PK backing indexes.
- The approved query-access-path inventory remains 29. No HNSW, IVFFlat, ANN,
  vector, JSONB GIN, or speculative index exists; no application data was
  inserted. AUDIT remains without an external FK.
- Phase 4.6.9 is complete. The forward sequence remains exactly `0001` through
  `0006`, each migration owns an explicit transaction, execution stops on the
  first failure, and applied migrations are immutable. Already-materialized or
  unknown-COMMIT outcomes require catalog inspection before retry; migrations
  remain outside application startup and runtime.
- `database/rollback/rollback_initial_schema.sql` exists as a manual,
  destructive, empty-database-only rollback artifact. It explicitly reverses
  the approved indexes, constraints, tables, and schemas without CASCADE and
  preserves pgvector. It was structurally validated but not destructively
  executed. A controlled MCP RW temporary-transaction rollback smoke test
  succeeded; RO validation confirmed the live application database was
  unchanged. At that point, phase 4.6.10 became current.
- Phase 4.6.10 is complete. After RO confirmation that all 11 application
  tables were empty, the approved rollback artifact was executed through the
  controlled RW MCP profile. It removed the application schemas while
  preserving pgvector; the six immutable migrations were then reapplied in
  strict order and validated between each execution.
- Final Phase 4.6 RO catalog validation confirmed PostgreSQL 17, pgvector
  0.8.6, the three approved schemas, 11 approved tables, and all 119 approved
  fields. It confirmed 2 UUID PKs, 9 BIGINT `BY DEFAULT` identity PKs, 10
  non-PK UNIQUE constraints, 14 FKs, 59 CHECK constraints, approved
  nullability/defaults/delete/update behavior, 21 explicit indexes, 31
  non-PK backing indexes, 42 total application indexes, and 29 query access
  paths. `VECTOR(384)`, TSVECTOR, and the FTS GIN index exist; ANN/HNSW/
  IVFFlat, JSONB GIN, PostgreSQL ENUMs, application triggers/procedures, and
  application data do not exist. The six migrations are applied and the manual
  rollback artifact exists. Phase 4.6 is complete; phase 4.7 is current.
- DEC-112 and DEC-113 define the six-file sequence and execution boundary.
  Initial table creation owns types, PKs, UUID/identity generation, nullability,
  and defaults; 0005 owns UNIQUE/CHECK/FK rules. The 21 explicit indexes in
  0006 are the 31 non-PK backing indexes minus 10 UNIQUE-backed indexes, with
  exact inventory was verified in 4.6.8 and final catalog validation. Runtime,
  repositories, seed, ingestion, and operational processes remain outside
  Phase 4.6; phase 4.7 is current.
- Phase 4.7.1 is complete (DEC-123): technical requirements for the Python
  database access layer are approved (PostgreSQL-native targeting PostgreSQL 17
  with pgvector 0.8.6; Python 3.14 compatibility; async-first access for
  FastAPI runtime; parameterized SQL; explicit transaction support;
  schema-qualified SQL; explicit PostgreSQL-native SQL approved; engine
  support for UUID, BIGINT, TIMESTAMPTZ, JSONB, TSVECTOR, VECTOR(384);
  PostgreSQL native FTS and pgvector cosine distance support; runtime
  decoupled from external native migrations; Alembic excluded; MCP as dev
  tooling only). Zero driver selection or package installation in 4.7.1.
- Phase 4.7.2 is complete (DEC-124): PostgreSQL-native repository access
  strategy is approved (Repository pattern boundary with `RAGRepository`,
  `OperationalRepository`, and `AuditRepository`; Pydantic models as
  application/domain models; ORM not mandatory; explicit parameterized
  PostgreSQL SQL; async-first runtime; centralized connection-pool-capable
  lifecycle; external native SQL migrations; Alembic excluded; MCP as
  diagnostic/development utility only). Driver selection and package additions
- Phase 4.7.3 is complete (DEC-125): PostgreSQL driver and installation mode
  approved (Psycopg 3 via `psycopg[binary]`; native asyncio runtime model
  using `AsyncConnection` and `AsyncCursor`; no extras added now,
  `psycopg[pool]` deferred to later runtime/lifecycle step; verified
  compatibility with Python 3.14, PostgreSQL 17, and Windows; zero local libpq
  or C build tooling prerequisites; Alembic excluded; SQLAlchemy undecided and
  deferred to Phase 4.7.4; zero edits to `pyproject.toml` and package
  pinning/installation deferred to Phase 4.7.6).
- Phase 4.7.4 is complete (DEC-126): SQLAlchemy evaluated and intentionally
  excluded from the POC runtime architecture (SQLAlchemy not required and not
  added as dependency; SQLAlchemy ORM, Core, and AsyncEngine/Session not
  adopted; runtime pipeline confirmed as
  `FastAPI/App -> Services -> Repositories -> Psycopg 3 -> PostgreSQL 17`;
  direct native execution with async-first parameterized SQL; direct use of
  PostgreSQL native capabilities including FTS, TSVECTOR, JSONB, pgvector, and
  VECTOR(384) without abstraction wrappers; Pydantic models remain application
  models; external native PostgreSQL SQL migrations decoupled from runtime;
  Alembic excluded; reconsider only if concrete requirements emerge).
- Phase 4.7.5 is complete (DEC-127): Python integration with pgvector approved
  (`pgvector` Python package; direct Psycopg 3 integration via
  `pgvector.psycopg`; `register_vector_async()` called once upon physical
  database connection initialization; pool connection hook allowed in Phase
  4.8 lifecycle but no pooling implemented now; strict alignment with
  `rag.chunks.embedding` as `VECTOR(384)` and 384 dimensions; exact cosine
  similarity search using operator `<=>`; no HNSW, IVFFlat, or ANN indexing;
  `pgvector` acts strictly as a type adapter and does not own repositories,
  SQL generation, migrations, pooling, ranking, or business logic;
  `CREATE EXTENSION` remains exclusively owned by SQL migrations; zero edits to
  `pyproject.toml` and package installation/pinning deferred to Phase 4.7.6).
- Phase 4.7.6 is complete (DEC-128): approved Python database dependency set
  and exact version-pinning policy established:
  - `psycopg[binary]==3.3.6` approved as the PostgreSQL-native driver (binary
    distribution avoids local C compiler/libpq build tooling prerequisites on
    Windows and Python 3.14; provides native async, transactions, and
    parameterized SQL).
  - `pgvector==0.5.0` approved as the Python VECTOR adapter with direct
    `pgvector.psycopg` integration.
  - Strict exact `==` version pinning policy adopted for reproducibility.
  - Forbidden alternatives confirmed excluded: SQLAlchemy, Alembic, psycopg2,
    asyncpg, `psycopg[c]`, `psycopg[pool]`/`psycopg_pool`, and `numpy` (not
    added solely for pgvector).
  - Scope boundary: no edits made to `pyproject.toml` in this step (deferred to
    Phase 4.7.7); package installation deferred to Phase 4.7.8.
- Phase 4.7.7 is complete (DEC-129): `pyproject.toml` updated with approved
  database dependencies declaring `psycopg[binary]==3.3.6` and `pgvector==0.5.0`
  under `[project].dependencies` with strict exact version pinning; existing
  dependencies (`fastapi==0.141.1`, `pydantic==2.13.5`, `uvicorn==0.53.0`,
  `fastembed==0.8.0`, `PyYAML==6.0.3`, `httpx==0.28.1`) and `requires-python = ">=3.14"`
  preserved; TOML syntax verified valid; zero dependencies installed in the
  virtual environment (installation deferred to Phase 4.7.8).
- Phase 4.7.8 is complete (DEC-130): approved database dependencies installed
  in the active project virtual environment (`F:\My Drive\dev\pocagente\.venv`)
  via `python -m pip install -e .` executed at `F:\My Drive\dev\pocagente\getnet-support`:
  - `psycopg==3.3.6` installed and verified via `pip show`.
  - `psycopg-binary==3.3.6` installed and verified via `pip show` (`psycopg[binary]` extra).
  - `pgvector==0.5.0` installed and verified via `pip show`.
  - `tzdata==2026.4` installed as transitive dependency for psycopg timezone handling.
  - `getnet-support==0.1.0` editable project installation maintained (`-e .`).
  - Confirmed zero forbidden/excluded dependencies present in `.venv`:
    SQLAlchemy, Alembic, psycopg2, asyncpg, `psycopg[c]`, `psycopg[pool]`/`psycopg_pool`,
    and extra numpy dependencies confirmed absent.
- Phase 4.7.9 is complete: validation, import, and compatibility checks
  passed:
  - Active Python interpreter confirmed from approved `.venv` (`F:\My Drive\dev\pocagente\.venv`).
  - Python version 3.14.2 confirmed (satisfies `>=3.14`).
  - `pyproject.toml` verified declaring exact pins: `psycopg[binary]==3.3.6` and `pgvector==0.5.0`.
  - Installed packages verified via metadata: `psycopg==3.3.6`, `psycopg-binary==3.3.6`, `pgvector==0.5.0`, `tzdata==2026.4`, and editable `getnet-support==0.1.0`.
  - `python -m pip check` passed with zero broken requirements.
  - Package imports succeeded: `import psycopg`, `from psycopg import AsyncConnection`, `import pgvector`, `from pgvector.psycopg import register_vector_async`.
  - Imported `psycopg.__version__` confirmed as `3.3.6`; `pgvector` package version confirmed as `0.5.0`.
  - `AsyncConnection` confirmed available and valid class; `register_vector_async` confirmed available and callable.
  - Application compile validation (`python -m compileall apps`) succeeded without errors.
  - SQLAlchemy remains intentionally excluded; Alembic remains excluded.
  - Zero database queries, pools, connections, repository code, or runtime modifications introduced.
- Phase 4.7 is COMPLETED and APPROVED under DEC-131; all 11 completion criteria passed.
- Phase 4.8 is COMPLETED / APPROVED. Phase 4.8.1 established the architecture
  in DEC-133; references below to future structure describe that historical
  decision point:
  - Architecture pipeline: `FastAPI / Agents -> Application Services -> Repositories -> Central Database Infrastructure -> Psycopg 3 + pgvector adapter -> PostgreSQL 17`.
  - Future package structure planned under `apps/agent_api/app/database/`:
    - `config.py`: database configuration and connection parameters;
    - `connection.py`: centralized connection, lifecycle, and transaction management;
    - `vector.py`: pgvector connection registration;
    - `errors.py`: safe database error abstraction;
    - `mapping.py`: database row to Python/Pydantic mapping;
    - `repositories/rag.py`: RAG persistence;
    - `repositories/operational.py`: OPS persistence;
    - `repositories/audit.py`: AUDIT persistence.
  - Strict persistence boundary: repositories own all database SQL; agents, endpoints, tools, and application services must never execute raw database SQL directly.
  - Customer Support tools consume application/service boundaries backed by `OperationalRepository`, not PostgreSQL directly.
  - Runtime database access is async-first via native Psycopg 3 (`AsyncConnection`, `AsyncCursor`).
  - SQL remains explicit, parameterized, PostgreSQL-native, and schema-qualified (`rag.*`, `ops.*`, `audit.*`).
  - Centralized connection lifecycle: pool-capable; repositories borrow connections and do not create/destroy them independently.
  - Composable transaction boundaries: support multiple repository operations within one atomic transaction; repository methods do not force independent commits when a larger transaction is required.
  - Centralized pgvector registration per physical connection (`register_vector_async`); not repeated by repository queries.
  - Application/domain models remain Pydantic-based; no ORM is introduced.
  - SQLAlchemy and Alembic remain excluded; migrations remain external native PostgreSQL SQL and are never executed at application startup.
  - PostgreSQL MCP remains external development/diagnostic tooling only.
  - No connection or pool creation as a module-import side effect; concrete pooling implementation deferred to Phase 4.8.3.
- Phase 4.8.2 is complete (DEC-134): database connection configuration approved:
  - Environment variable family reused: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_SSLMODE`, `POSTGRES_CONNECT_TIMEOUT_SECONDS`, `POSTGRES_POOL_MIN_SIZE`, `POSTGRES_POOL_MAX_SIZE`, `POSTGRES_POOL_TIMEOUT_SECONDS`.
  - Local POC defaults documented in `.env.example`: `127.0.0.1:5432`, `getnet_support`, `getnet_app`, the owner-approved local password value, `disable` SSL mode, connect timeout `5`s, pool min `1`, pool max `5`, pool acquisition timeout `5`s. The value itself is never copied into documentation.
  - Invariants: `.env` remains the secret, Git-ignored runtime source; `.env.example` is reference material and may temporarily retain owner-approved local POC values, an exception that must not extend to production, non-POC, shared, or externally distributed credentials; `DATABASE_URL` is rejected/not introduced; connection parameters pass to Psycopg as structured keyword arguments rather than a concatenated URI; configuration validates host, port, db name, user, password presence, SSL mode, timeouts, and min/max consistency; no `pydantic-settings` dependency is approved; containerization changes only `POSTGRES_HOST` (e.g. to `postgres`).
- Phase 4.8.3 is complete (DEC-135): database connection lifecycle and AsyncConnectionPool approved:
  - Runtime pool type: `psycopg_pool.AsyncConnectionPool`.
  - Approved pool package: `psycopg-pool==3.3.2`, declared and installed in the active project virtual environment.
  - Pool sizing & timeouts: `min_size=1`, `max_size=5`, acquisition timeout `5` seconds; constructed with `open=False`.
  - Application lifecycle: explicitly `await pool.open()` during FastAPI lifespan startup; verify initial pool readiness before declaring DB-dependent runtime ready; `await pool.close()` during application shutdown.
  - Pool singleton & access: one pool per FastAPI process; repository operations borrow connections via `async with pool.connection() as conn`; manual `getconn()/putconn()` prohibited as standard pattern; no pool/connection creation as module-import side effects; repositories borrow connections and do not create independent pools.
  - Multi-worker budget: PostgreSQL connection budget accounts for `workers × max_size`; speculative pool expansion prohibited.
  - Connection configuration hook: the pool `configure` callback delegates to
    centralized `database/vector.py`, which calls `register_vector_async(conn)`
    once per newly opened physical connection and returns it transaction-clean.
  - Composable transactions: pooling supports multi-repository atomic transactions (Phase 4.8.10).
  - Health & readiness: DB-dependent readiness fails closed if the pool cannot establish usable PostgreSQL connections.
- Phase 4.8.4 is complete (DEC-136): immutable `DatabaseConfig` and explicit
  environment loading are validated; `PostgresDatabase` centralizes one
  `AsyncConnectionPool` constructed with `open=False`; and explicit async
  `open()`/readiness `wait()`/`connection()`/`close()` lifecycle is implemented.
  Structured Psycopg keyword arguments are used without `DATABASE_URL`, and no
  connection or pool is created at module import.
- Phase 4.8.4 validation used only mocked pool tests: 37 focused/full tests
  passed, compilation and imports passed, and no real PostgreSQL integration
  test or SQL execution occurred. Repositories remain pending; explicit
  transaction abstraction remains Phase 4.8.10; real PostgreSQL validation
  remains Phase 4.8.13.
- Phase 4.8.5 is complete (DEC-137): `database/vector.py` centralizes the
  official asynchronous pgvector adapter registration; `PostgresDatabase`
  supplies `configure_pgvector_connection` to `AsyncConnectionPool.configure`;
  registration occurs once per newly created physical connection before pool
  availability, never per query or logical checkout.
- Pgvector metadata-discovery work is followed by `rollback()` so each fresh
  connection returns transaction-clean. Registration is fail-closed, cleanup
  is attempted on registration failure, and the original registration error is
  preserved if cleanup also fails. No DDL, global adapter registration, real
  PostgreSQL connection, repository, or application transaction abstraction
  was introduced. Validation passed with 43 tests, clean dependency checks,
  compilation, and imports.
- The project `.venv` reports no broken requirements. The known external
  Google ADK/FastAPI conflict belongs to the global Python environment, is
  unrelated to this implementation, and was not modified.
- Phase 4.8.6 is complete (DEC-138): exactly three repository domains are
  defined. `RAGRepository` owns the four `rag` tables,
  `OperationalRepository` owns the six `ops` tables, and `AuditRepository`
  owns `audit.security_events`.
- Repositories are connection-bound persistence adapters. They receive an
  injected `AsyncConnection`, create no pool or connection, do not close the
  connection, and never call `commit()` or `rollback()`. Multiple repositories
  may share the same connection under the future Phase 4.8.10 transaction
  boundary, while cross-schema repository access remains prohibited.
- `OperationalRepository` returns deterministic operational facts beneath the
  Customer Support application-service/tool layer; it performs no diagnosis
  or root-cause inference. `AuditRepository` accepts only sanitized security
  and governance event data.
- Final row mapping and database error translation are complete in Phases
  4.8.11 and 4.8.12. Real connectivity and repository validation are complete
  in Phases 4.8.13 and 4.8.14.
- Phase 4.8.7 is complete (DEC-139): concrete `RAGRepository` implements
  source/document persistence, stable checksum-aware document identity,
  complete chunk replacement, ingestion lifecycle, PostgreSQL FTS retrieval,
  and exact pgvector cosine retrieval over the four RAG tables. Retrieval
  requires ACTIVE sources/documents and performs no RRF or grounding. Lexical
  and semantic methods return `Sequence[SearchCandidate]`; `RepositoryRecord`
  is restricted to write/mutation payloads. Earlier repository-record
  retrieval wording is historical pre-4.8.11 context.
- Phase 4.8.8 is complete (DEC-140): concrete `OperationalRepository` owns the
  six OPS tables and implements operational persistence, protocol lookup,
  establishment handling, append-only execution timelines, protocol-status
  facts, and execution-failure evidence. It returns facts/evidence only and
  performs no diagnosis or root-cause inference.
- Phase 4.8.9 is complete (DEC-141): concrete `AuditRepository` owns only
  `audit.security_events` and implements sanitized event persistence, PK
  lookup, request correlation, unreviewed-event lookup, and review persistence
  under the secret-safe boundary.
- Phase 4.8.10 is complete (DEC-142): `PostgresDatabase.transaction()` obtains
  one pooled `AsyncConnection` and delegates completion to Psycopg's native
  transaction context. Normal exit commits, exceptional exit rolls back, and
  original exceptions propagate. Multiple repositories can share that exact
  connection; repositories still never commit, roll back, or own transactions.
  No Unit of Work or custom nested/savepoint abstraction was introduced.
- Phase 4.8.11 is complete (DEC-143): centralized immutable Pydantic mapping
  keeps raw database rows behind repository read boundaries.
- Phase 4.8.12 is complete (DEC-144): `SafeDatabaseError` subclasses provide
  stable, secret-safe translation for recognized Psycopg and pool failures at
  pool and repository boundaries. Driver details are retained only as exception
  causes; validation and cancellation/control-flow exceptions propagate unchanged.
  No retries, logging, or real PostgreSQL access were introduced.
- Phase 4.8.13 is complete (DEC-145): the runtime `.env` configuration path,
  `PostgresDatabase` pool open/wait/acquire/close lifecycle, PostgreSQL 17,
  database `getnet_support`, pgvector 0.8.6, and registered vector round-trip
  were validated through a real local application connection without exposing
  credentials.
- Phase 4.8.14 is complete (DEC-146): all public concrete RAG, OPS, and AUDIT
  repository methods were exercised against real PostgreSQL with typed mapping,
  PostgreSQL FTS, exact-cosine pgvector retrieval, operational evidence,
  sanitized audit persistence, safe integrity-error translation, transaction
  rollback, and an explicit zero-residual-data check.
- Phase 4.8.15 and 4.8.16 are complete. DEC-147 records the successful final
  audit and approves the complete Phase 4.8 database access layer.
- Phase 4.5.1 is complete; global PostgreSQL physical conventions are approved.
- Phase 4.5.2 is complete; the RAG physical model is approved in
  `docs/database-physical-model.md`.
- The RAG physical model uses stable `document_key` identity, nullable
  pre-publication checksums, atomic current-chunk replacement without version
  history, required FTS and vector retrieval representations, and ingestion-run
  provenance with source/document integrity.
- RAG publication uses a single-worker ingestion flow.
- Phase 4.5.3 is complete. The approved embedding configuration is FastEmbed
  `0.8.0` with `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`,
  ONNX Runtime on local CPU, optional GPU, 384 dimensions, and
  `VECTOR(384)` storage.
- FastEmbed mean pooling is the approved current behavior; no additional manual
  normalization is applied. Older E5 or sentence-transformers embeddings are
  incompatible and require full re-embedding.
- Phase 4.5.4 is complete; the approved FTS design uses `TSVECTOR`, standard
  `portuguese` and `simple` configurations, title/section/content inputs,
  application-controlled native generation, planned GIN
  `gin_chunks__search_vector`, `websearch_to_tsquery`, `ts_rank_cd`, up to 10
  lexical candidates, and RRF hybrid fusion.
- Phase 4.5.5 is complete. The approved pgvector design uses `VECTOR(384)`
  with strict cosine distance through `<=>`, exact nearest-neighbor scanning,
  and no active ANN index. HNSW is a future-only preference if benchmarks
  require ANN; it is not active or implemented. Semantic retrieval is limited
  to 10 candidates, applies active source/document filters, and uses rank-based
  RRF with snapshot consistency across lexical, semantic, and provenance data.
- Phase 4.5.6 is complete. The approved OPS physical model defines six tables
  with BIGINT identity technical keys, TIMESTAMPTZ instants, explicit status
  checks, planned indexes only, email 0..1 protocol cardinality, composite
  provenance FKs, the R1-to-R2 establishment handoff with TEXT business
  numbers, and chronological `execution_log` retention using optional
  `SET NULL` entity references.
- Incoming emails are R1 intake records. R2 cannot own incoming emails. The
  `run_id` FK guarantees that the referenced automation run exists, but does
  not by itself guarantee `robot = 'R1'`; R1-only ownership remains an
  application invariant in the approved final model. No redundant
  `robot` column or trigger is introduced.
- Phases 4.5.1 through 4.5.16 are complete. Phase 4.5 is COMPLETED / APPROVED
  after the final documentation gate. Exactly 11 tables are specified in
  `docs/database-physical-model.md`; no physical objects have been created.
- POC volume ranges are planning assumptions. Exact cosine, the existing
  query indexes, complementary unindexed JSONB and no partitioning remain
  proportional starting choices; performance certification is not claimed.
- The field-security review is complete: governed RAG, minimized OPS,
  sanitized AUDIT and anti-secret rules for all fields. Production IAM remains
  outside this phase.
- The 29 planned query access paths (7 RAG, 18 OPS, 4 AUDIT) are preserved.
  Two existing OPS composite-FK target UNIQUEs also require backing indexes;
  the full future non-PK backing-index total is 31. None has been created.
- The next phase is 4.6 — CRIAR TABELAS / DDL / MIGRATIONS; implementation
  remains pending.

## Architecture in Force

### Django

- Frontend and web application.
- Authentication and session handling.
- Administrative interface.

### FastAPI

- Internal API boundary.
- Agent endpoints.
- RAG execution boundary.
- Tools and provider integrations.

### LangGraph

- Implemented orchestration layer for routing, specialized agents, state,
  handoff, and escalation.

### Multi-agent responsibilities

The Phase 9 runtime agents, orchestration, authenticated `/chat` boundary, and
final end-to-end validation are complete. The minimum security-audit integration
required by `REQ-P9-SEC-004` records a sanitized protected-request event through
`SecurityAuditService`, `PostgresSecurityAuditSink`, and `AuditRepository`.
Broader audit/runtime work remains Phase 10 scope.

#### Router Agent

- Receives each user request and selects or sequences the required specialized
  agents and capabilities.
- Routes knowledge questions to the Knowledge Agent and customer-specific or
  operational questions to the Customer Support Agent.
- May coordinate both agents when a request requires documented expected
  behavior and observed operational state, such as deciding whether a protocol
  is delayed.
- Does not use a cancellation-only rejection boundary; it supports the Getnet
  product/service and general-purpose scenarios required by
  `docs/challenge.md`.

#### Knowledge Agent

- Uses internal RAG for approved process documentation, PDD, SDD, Technical
  Overview, and internal policies.
- Uses approved public Getnet RAG for stable or semi-stable official product,
  service, support, corporate, technical, and financial knowledge.
- Uses controlled Web Search for general-purpose or current public information
  and when Getnet RAG evidence is insufficient or freshness matters.

#### Customer Support Agent

- Uses controlled customer and operational tools for authorized account,
  protocol, RPA execution, log, device, transaction, and observed process
  state.
- Public Web Search is not a substitute for customer-specific or operational
  evidence.
- Exposes at least two approved controlled OPS tools:
  - `lookup_protocol_status`: accepts an authorized protocol identifier (e.g.
    `protocol_number`) and retrieves the current observed operational state
    from `ops.service_requests`, `ops.establishments`, and relevant
    `ops.execution_log` entries; returns structured operational facts only and
    does not infer undocumented business rules.
  - `inspect_execution_failure`: accepts an authorized execution/protocol/request
    identifier and collects execution diagnostics (timeline, execution state,
    relevant error evidence, last successful stage, failure stage, related
    operational context) from `ops.automation_runs`, `ops.execution_log`,
    `ops.service_requests`, `ops.establishments`, and when justified
    `ops.incoming_emails` / `ops.email_attachments`; returns evidence, NOT an
    invented root-cause conclusion.
- Strict responsibility boundary: OPS tools retrieve observed facts and
  evidence; the Customer Support Agent interprets the evidence and produces a
  grounded probable root-cause diagnosis. The agent must distinguish FACT from
  INFERENCE and must not claim a root cause as fact without sufficient evidence.
- Approved Diagnostic-to-Human flow: when the Customer Support Agent identifies
  a sufficiently grounded probable cause or determines that human action is
  appropriate:
  1. Explains the diagnosis and supporting evidence to the user;
  2. Explicitly offers human escalation for support-ticket opening and handling;
  3. Requires explicit user confirmation before initiating transfer;
  4. Routes to the Human Escalation Agent after confirmation;
  5. Transitions the active conversation to the human-handoff flow (e.g.
     `WAITING_HUMAN`);
  6. Provides only the minimum necessary diagnostic context to the authorized
     human operator;
  7. Leaves support-ticket opening/handling to the human operator (no automatic
     AI ticketing or external ITSM integration in the initial POC);
  8. Ensures automated agent responses are suspended while the conversation is
     under human ownership.

#### Human Escalation Agent

- Is the planned fourth runtime product agent and does not replace the
  mandatory Router, Knowledge, or Customer Support Agent.
- Coordinates user-confirmed transfer from automated assistance to an
  authorized human operator when the user explicitly requests human support or
  the system cannot resolve the request with sufficient grounded evidence.
- Suspends automated responses while a human owns the active conversation.

### Approved Human Escalation architecture

The initial POC uses application-native handoff in the same active Django chat.
The system informs the user and requires explicit confirmation before transfer.
The conceptual states are `BOT`, `WAITING_CONFIRMATION`, `WAITING_HUMAN`,
`HUMAN`, and `RESOLVED`.

Django conceptually supports `CLIENT` and `SUPPORT_AGENT` roles. A client uses
the normal chat and may request or confirm escalation. An authorized support
agent sees the human-support queue, accepts an available conversation, becomes
its assigned human owner, exchanges messages in the same conversation, and may
resolve it or explicitly return control to automation. Only one human operator
owns an active `HUMAN` conversation unless a future approved requirement
changes that rule. Automated generation remains suspended while the state is
`HUMAN`.

Handoff transfers only the minimum authorized context from the current active
conversation. This is conversation state required for the handoff, not
persistent cross-session conversational memory. A new conversation does not
automatically remember prior sessions.

Initial browser delivery uses normal HTTP requests and HTTP polling with an
initial configurable interval between 1 and 2 seconds for client and operator
views. WebSocket or Django Channels is optional future work, not an
initial requirement. WhatsApp is excluded from the initial POC and may be
evaluated only as a future escalation channel.

Django owns or will own authentication, role authorization, customer and
operator interfaces, active conversations and messages, the human-support
queue, ownership, assignment, and access-control boundaries. FastAPI and
LangGraph own or will own the four runtime agents, escalation reasoning and
orchestration, handoff coordination, and respect for human ownership before an
automated response. Exact API contracts remain pending.

Future implementation requires conceptual concerns equivalent to
`Conversation`, `Message`, and `Handoff`, including status, ownership, assigned
operator, authorship, timestamps, escalation reason, confirmation, acceptance,
and resolution. These are not approved physical models or tables; no field
types, keys, migrations, indexes, database schema, broker, or locking design is
defined yet. Conceptual escalation reasons include `USER_REQUESTED_HUMAN`,
`INSUFFICIENT_EVIDENCE`, and `UNRESOLVED_REQUEST`.

Only minimum active-conversation context may be exposed to the assigned human.
Secrets, credentials, protected infrastructure details, and secret locations
remain prohibited, and relevant security events remain aligned with the
sanitized AUDIT architecture.

For diagnostic escalations originating from the Customer Support Agent, the
minimum necessary diagnostic context transferred to the human operator includes:
- protocol identifier (`protocol_number`);
- user problem summary;
- current observed operational state;
- execution run identifier (`run_id`) if applicable;
- last successful stage;
- observed failure stage;
- sanitized error description (redacted of credentials and internal secrets);
- chronological operational event / timeline trace;
- agent interpretation clearly labeled as probable root cause diagnosis
  (explicitly separated from verified facts);
- record of explicit user confirmation.

The diagnostic transfer strictly excludes:
- secrets, passwords, tokens, API keys, private keys, connection strings, or DB credentials;
- raw un-sanitized stack traces or internal environment paths;
- persistent cross-session memory or unrelated conversational history.

In the initial POC, ticket opening and handling is performed directly by the
authorized human operator receiving this diagnostic package; there is no
automatic AI ticket creation and no external ITSM integration. Automated
responses remain suspended while the conversation is under human ownership.
The design addresses the optional fourth-agent and human-handoff capabilities
in `docs/challenge.md`, but remains approved architecture and planned
implementation only.

### Data and infrastructure

- PostgreSQL 17 provides relational persistence.
- pgvector 0.8.6 provides vector storage and semantic search support.
- Docker provides local infrastructure.
- FastEmbed is the approved local embedding provider.
- Tavily is the approved controlled web-search provider behind a
  provider-neutral application interface.

## RAG Architecture Decisions

- Curated internal PDD/SDD process documents are authoritative for expected
  business behavior.
- Controlled operational database data represents observed automation
  behavior.
- Curated technical documentation represents expected technical
  implementation.
- Approved public Getnet sources support both specialized cancellation and
  corporate knowledge and the general product/service knowledge required by
  the engineering challenge.
- Public product/service information cannot override authoritative internal
  cancellation-process rules for the internal RPA workflow.
- Public ingestion uses a restrictive allowlist; discovered links are not
  trusted or ingested automatically.
- Provenance is mandatory and must remain associated with indexed chunks.
- Chunking is semantic/structural, using document sections, business rules,
  and technical symbols where available.
- The current document may use a checksum to detect changes and trigger
  controlled replacement; historical version tracking is outside the POC.
- PostgreSQL Full Text Search is the lexical retrieval mechanism.
- pgvector is the semantic retrieval mechanism.
- Retrieval is hybrid, with up to 10 lexical candidates and 10 semantic
  candidates.
- Reciprocal Rank Fusion (RRF) merges retrieval channels.
- The initial final Top-K is 5.
- Insufficient evidence must not be replaced with a plausible hallucination.
- When evidence remains insufficient, the agent states the limitation and may
  offer approved, user-confirmed human support.

## Approved Public Getnet Knowledge Scope

`knowledge/internal/cancellation-process/public/sources.yaml` is the exact public-source registry. It now
contains approved general Getnet sources in addition to the existing
cancellation/corporate sources. Persistent public RAG may cover official
Getnet material for:

- card machines, Get Clássica, and Get Smart;
- Pix;
- Payment Link and officially documented WhatsApp use through Payment Link;
- receivables, settlement, and receivables advance;
- crediário and installment capabilities;
- card-machine connectivity and transaction errors or declines;
- Getnet help, FAQ, and support;
- cancellation, estorno, chargeback, and reconciliation;
- Extrato Eletrônico and approved technical or financial documentation.

The registry remains restrictive and record-based. A discovered page is an
untrusted candidate and must pass explicit review and approval, receive an
exact source record, and then enter controlled ingestion. Unrestricted crawling
and automatic ingestion of discovered links or Web Search results are not
allowed.

## Approved Web Search Policy

- Internal process/documentation questions use internal RAG.
- Stable or semi-stable Getnet product/service questions use approved public
  Getnet RAG first.
- Getnet questions may use controlled Web Search when RAG evidence is
  insufficient or freshness matters, prioritizing official Getnet sources.
- General-purpose or current-information questions use Web Search when
  appropriate, including weather, current currency rates, current news,
  current prices, and other volatile public facts.
- Customer-specific protocol, RPA execution, log, transaction, device, or
  observed process-state questions use the Customer Support Agent and
  controlled operational tools, never public Web Search as a substitute.
- Security-restricted requests cannot broaden into Web Search as a bypass.

External Web content is untrusted evidence, never instruction. Retrieved
prompt injection is ignored, and external content cannot override system or
application policy, authorization, agent roles, tool permissions, security
controls, or authoritative internal process rules. Live-search results are not
automatically persisted into RAG; volatile facts normally remain live evidence.

## Current RAG Code State

The FastAPI/RAG package provides executable retrieval, grounding, agents,
orchestration, and the authenticated `/chat` transport boundary.

Implemented as API structure or contracts:

- FastAPI `main.py`;
- `GET /health`;
- dependency-aware `GET /ready`;
- strict typed `POST /chat` over application orchestration;
- fail-closed internal Bearer service authentication with trusted identity,
  role, and optional OPS authorization claims;
- `RAGService` facade;
- RAG configuration and domain/provenance models;
- executable ingestion loader, validator, and structural chunker;
- FastEmbed adapter and atomic publication;
- lexical and semantic repository retrievers;
- consistent-snapshot hybrid retrieval and RRF ranking;
- immutable provider-neutral grounding contracts and `ContextBuilder`.

Grounding now consumes Phase 7 `RetrievedChunk` values, validates structured
provenance, applies deterministic internal/public priority tiers, deduplicates
physical chunks, and emits safe deterministic citations. `GroundedContext`
uses structural `SUFFICIENT_CONTEXT` / `INSUFFICIENT_EVIDENCE` status only;
there are no score thresholds, LLM calls, answer generation, or semantic claim
classification. Retrieved text is passed as passive DATA only. Phase 9 agent,
tool, web-search, and LLM orchestration remains out of scope.

## Python Environment

**Project virtual environment:**

`F:\My Drive\dev\pocagente\.venv`

**Required interpreter:**

`F:\My Drive\dev\pocagente\.venv\Scripts\python.exe`

Rules:

- Do not silently fall back to another Python interpreter.
- Do not install project dependencies globally.
- Use the project virtual environment for validation and testing.

The current dependency manifest is `pyproject.toml`. The editable installation
and `pip check` have been validated with the required interpreter.

## Database Infrastructure Status

- Docker Desktop: configured.
- Docker Engine: working.
- Docker Compose: working.
- Container: healthy.
- PostgreSQL major version: 17.
- Database: `getnet_support`.
- Local binding: `127.0.0.1:5432`.
- Persistent Docker volume: enabled.
- pgvector extension: enabled at version 0.8.6.

The application database username is intentionally omitted from this context.
Passwords and other `.env` values must never be copied into documentation.

## Development Tooling — PostgreSQL MCP

The PostgreSQL MCP is approved only as external development, debugging,
inspection, and validation tooling. It is not part of the runtime architecture
and is not a production dependency.

### Tooling configuration

- MCP package: `@microsoft/postgres-mcp`
- Codex server name: `getnet-postgres`
- Inspection profile: `getnet-support-ro`
- Controlled migration profile: `getnet-support-rw`
- Connection endpoint: `127.0.0.1:5432`
- Database: `getnet_support`
- SSL: disabled (`false`)
- Access modes: RO for inspection/validation; RW only for explicitly approved
  local POC migrations
- Secret storage: OS-level secure credential storage

Passwords, password hashes, tokens, secret connection strings, credentials,
credential locations, and `.env` values must never be logged or copied into
documentation.

### Validation state

- PostgreSQL version: `17.11`
- Database: `getnet_support`
- Extension: pgvector `0.8.6`
- Present application schemas: `rag`, `ops`, `audit`
- Present application tables: four RAG, six OPS, and `audit.security_events`.

### Scope and write policy

- The MCP is for external development/debug/inspection/validation tooling only;
  it is not runtime architecture.
- FastAPI, Django, LangGraph, and Agents do not depend on the MCP.
- `getnet-support-ro` is the default inspection and validation profile.
- `getnet-support-rw` is limited to explicitly approved local POC migrations;
  it is not general write access.
- Versioned SQL migration files remain authoritative; MCP is only the controlled
  execution/validation channel. Application startup does not run MCP migrations.
- Future inspection may cover schemas, tables, columns, constraints, indexes,
  pgvector, PostgreSQL Full Text Search, and OPS data.
- An optional future read-only dedicated database user is a defense-in-depth
  consideration; do not implement it now.

## Planned Database Schemas

### `rag`

#### Purpose

The RAG schema stores and organizes knowledge used by the Knowledge Agent. Its
main role is to answer questions such as:

- What is the documented rule?
- What should happen according to the process?
- What does the approved documentation state?

#### Information that belongs in RAG

- Approved internal process documentation.
- PDD.
- SDD.
- Technical Overview.
- Internal security policy.
- Approved public sources.
- Source metadata.
- Documents.
- Structural or semantic chunks.
- Embeddings.
- Lexical-search representation.
- Provenance.
- Ingestion execution metadata.
- Governance metadata.

#### Information that does not belong in RAG

- RPA execution logs.
- Operational execution state.
- Real protocol processing state.
- Runtime RPA alerts.
- Operational process records.
- Security audit events.
- Credentials or secrets.
- Generated LLM responses.

These responsibilities belong to other schemas such as `ops` or `audit`.

#### Conceptual information categories and approved structures

The detailed conceptual architecture of the RAG schema is approved.
Approved conceptual structures:

- `rag.sources`
- `rag.documents`
- `rag.chunks`
- `rag.ingestion_runs`

The conceptual responsibilities were approved in phase 4.2 and their
PostgreSQL physical representation was approved in phase 4.5.2. Physical
schemas, tables, DDL, migrations, and ORM objects remain pending for phase 4.6.
The authoritative detailed physical specification is
`docs/database-physical-model.md`.

#### `rag.sources` — Approved responsibility

`rag.sources` represents where governed knowledge originates. It answers
conceptually:

- “Where did this knowledge come from?”

Examples include:

- internal PDD source;
- internal SDD source;
- Technical Overview source;
- internal policy source;
- approved official Getnet public source.

Approved conceptual information:

- `source_id`
- `name`
- `source_type`
- `origin`
- `reference`
- `domain`
- `status`
- `priority`
- `created_at`
- `updated_at`

The physical design is approved in phase 4.5.2: stable canonical source
identity, UUID technical key, classification and explicit activation rules,
and the approved constraints are recorded in
`docs/database-physical-model.md`.

Approved relationship:

- `rag.sources` (1) -> (N) `rag.documents`
- A source may provide multiple documents.
- A document belongs to one source conceptually.

#### `rag.documents` — Approved responsibility

`rag.documents` represents the current knowledge document obtained from an
approved source. It answers conceptually:

- “What document/content was obtained from this source?”

Approved conceptual information:

- `document_id`
- `source_id`
- `title`
- `document_type`
- `content_checksum`
- `status`
- `last_ingested_at`
- `created_at`
- `updated_at`

The physical design is approved in phase 4.5.2 and is detailed in
`docs/database-physical-model.md`. `document_key` provides stable identity;
title remains descriptive and mutable. No document version history is kept.

**Important approved simplification — No historical document versions:**
The POC does NOT maintain historical document versions. Do NOT introduce:

- `rag.document_versions`;
- version history;
- `previous_version`;
- `active_version`;
- historical document-version lifecycle.

PDD, SDD, Technical Overview, and other approved POC knowledge are treated as
current governed documents for retrieval.

`content_checksum` is used for:

- integrity/change detection;
- duplicate/reprocessing avoidance.

It is NOT used to create historical versions.

Conceptual behavior:

- same document + same checksum: do not reprocess unnecessarily.
- same document + changed checksum: reprocess the current document and replace
  its current retrievable chunks in a controlled way.

No historical document copy is required.

#### `rag.chunks` — Approved responsibility

`rag.chunks` represents the retrievable portions of a `rag.document`. It is the
main persistent retrieval unit used by hybrid search.

Approved conceptual information:

- `chunk_id`
- `document_id`
- `content`
- `chunk_order`
- `section`
- `content_type`
- `metadata`
- `embedding`
- `search_vector`
- `created_at`

The physical design is approved in phase 4.5.2 and is detailed in
`docs/database-physical-model.md`. `rag.chunks` remains the persistent
retrieval unit, and published chunks require both vector and FTS
representations.

Conceptual responsibilities:

- `content`: actual retrievable text.
- `chunk_order`: logical position within the parent document.
- `section`: document section/title/logical location when available.
- `content_type`: conceptual category such as business rule, document section,
  technical description, code symbol, policy, etc.
- `metadata`: auxiliary provenance/context metadata.
- `embedding`: semantic-vector representation used by pgvector; the approved
  physical representation is `VECTOR(384)`.
- `search_vector`: lexical representation used by PostgreSQL Full Text Search
  (do NOT define `TSVECTOR` implementation details or indexes yet).

Approved relationship:

- `rag.documents` (1) -> (N) `rag.chunks`
- A document may contain multiple chunks.
- Each chunk belongs to one document conceptually.

**Chunk history / duplication rule:**
The POC does NOT maintain historical chunk versions. Do not introduce:

- `chunk_version`;
- `historical_chunk`;
- old chunk retention for document versioning.

If a document checksum is unchanged, do not regenerate chunks unnecessarily.
If a document changes, regenerate and replace the current retrievable chunks for
that document in a controlled way. Chunks represent only the current approved
retrievable document content.

#### `rag.ingestion_runs` — Approved responsibility

`rag.ingestion_runs` records each execution attempt of the RAG ingestion
process. It does NOT store business knowledge. It answers conceptually:

- “How did the attempt to place this document into the RAG pipeline execute?”

Approved conceptual information:

- `ingestion_run_id`
- `source_id`
- `document_id`
- `started_at`
- `finished_at`
- `status`
- `operation`
- `chunks_created`
- `result_message`
- `created_at`

The physical design is approved in phase 4.5.2 and is detailed in
`docs/database-physical-model.md`. Ingestion runs preserve execution history,
source/document provenance integrity, and the approved lifecycle states.

Conceptual operation examples include:

- `INGEST`
- `REINGEST`
- `SKIPPED_UNCHANGED`

The lifecycle states, categorical checks, and integrity rules are approved in
phase 4.5.2 and are detailed in `docs/database-physical-model.md`.

Approved relationship:

- `rag.documents` (1) -> (N) `rag.ingestion_runs`
- A document may have multiple ingestion attempts over time.
- Each ingestion run conceptually corresponds to processing one document.

Examples:

- initial ingestion: one ingestion run.
- same document processed again with unchanged checksum: another ingestion run
  may record `SKIPPED_UNCHANGED`.
- failed reprocessing attempt: another ingestion run may record `ERROR`.

This execution history does not mean historical document versions are retained.

#### Approved complete RAG relationship model

```text
rag.sources
    1
    |
    +---- N rag.documents
              |
              +---- N rag.chunks
              |
              +---- N rag.ingestion_runs
```

Meaning:

- one source may provide many documents;
- one document may have many current retrievable chunks;
- one document may have multiple ingestion execution attempts.

No historical document or chunk version structure is introduced.

#### Approved ingestion concept and flow

RAG ingestion is the process of taking an approved source/document and
transforming it into retrievable knowledge.

Conceptual flow:

```text
approved source -> document -> start ingestion_run
  -> read/load document
  -> validate content and metadata
  -> calculate checksum
  -> compare with current known checksum:
       if unchanged:
           ingestion_run = SKIPPED_UNCHANGED
       if new or changed:
           structural/semantic chunking
           -> generate semantic embeddings with FastEmbed
           -> prepare lexical representation for PostgreSQL FTS
           -> persist current chunks
           -> ingestion_run = SUCCESS
```

If processing fails:

- `ingestion_run` = `ERROR`;
- do not expose partially ingested content;
- preserve previously valid retrievable content when applicable.

This flow is not implemented in this task.

#### Ingestion is not query-time processing

Document ingestion normally happens before user queries.

Conceptually:

1. approved documents are provided to the RAG pipeline;
2. ingestion processes them;
3. chunks and representations are persisted;
4. later user questions search the already-prepared chunks.

A user question does NOT normally trigger full document ingestion. Retrieval
and ingestion are separate concerns.

#### Approved provenance chain

The RAG architecture must preserve conceptual provenance from a retrieved chunk
back to its origin:

```text
rag.chunks -> rag.documents -> rag.sources
```

This allows a retrieved chunk to identify:

- its parent document;
- its source;
- its logical location/section when available;
- relevant checksum and context metadata.

This supports:

- grounding;
- internal provenance;
- evaluation;
- debugging;
- citation/attribution;
- auditability.

The approved RAG physical joins, FK constraints, and indexes are documented in
`docs/database-physical-model.md`; no database objects have been created.

#### Retrieval responsibility

`rag.chunks` is the main persistent retrieval unit used by hybrid search.

Conceptually:

```text
user question
  |
  +--> PostgreSQL Full Text Search -> lexical chunk candidates (up to 10)
  |
  +--> pgvector                    -> semantic chunk candidates (up to 10)
  |
  v
Reciprocal Rank Fusion (RRF)
  |
  v
Final Top-K (5 chunks)
  |
  v
Grounded evidence supplied to LLM
```

Approved settings remain:

- lexical candidates = up to 10;
- semantic candidates = up to 10;
- Reciprocal Rank Fusion (RRF);
- final Top-K = 5.

Retrieval is not implemented in this task.

#### RAG boundary remains unchanged

RAG stores governed knowledge for retrieval. It does NOT contain:

- OPS execution logs;
- protocol state;
- RPA operational state;
- emails/attachments as operational records;
- conversation history;
- persistent cross-session user memory;
- generated LLM answers;
- Human Escalation chat messages;
- temporary Web Search results;
- security-event history.

Those responsibilities remain outside RAG. OPS remains the source of observed
operational facts. AUDIT remains the source of security/governance events.
Application conversation/handoff state remains a separate future application
concern and is not added to the RAG schema.

#### Provenance and user-facing attribution

Retrieved evidence must internally preserve enough provenance to identify
source, document, chunk, section or logical location when available, and
document checksum when applicable. Detailed internal provenance must not
automatically be exposed to users. Normal user responses must not disclose
internal implementation details (filenames, tables, SQL, chunk IDs, checksums,
paths, technology, connection info), using abstract source classes instead.

### `ops`

#### Purpose and responsibility boundary

The OPS schema represents observed operational state required by the Customer
Support Agent when investigating the cancellation RPA process. It answers:

- “What actually happened?”

This is distinct from RAG, which answers “What should happen?” and “What does
the approved documentation say?”. Security and governance events belong to the
AUDIT schema.

The approved OPS model is intentionally simplified and domain-oriented. The
detailed conceptual architecture of the OPS schema is approved.
Approved conceptual structures:

- `ops.automation_runs`
- `ops.incoming_emails`
- `ops.email_attachments`
- `ops.service_requests`
- `ops.establishments`
- `ops.execution_log`

The OPS physical design was approved in phase 4.5.6 and is detailed in
`docs/database-physical-model.md`. No physical `ops` schema, table, DDL,
migration, constraint, or index has been created; implementation remains
pending for phase 4.6.

#### `ops.automation_runs` — Approved responsibility

`ops.automation_runs` represents a complete technical execution of robot R1 or
R2. A single `automation_run` can process multiple items:

- an R1 run can process N incoming emails;
- an R2 run can process N items / protocols / ECs across different requests.

An `automation_run` does NOT represent a protocol.

Approved conceptual fields:

- `run_id`
- `robot`
- `started_at`
- `finished_at`
- `status`
- `result_message`
- `created_at`

The conceptual robot values are R1 and R2. Environment, hostname, machine user,
CPU usage, memory usage, and other machine telemetry are not part of the
approved POC scope.

#### `ops.incoming_emails` — Approved responsibility

`ops.incoming_emails` represents each email received by R1. Email is a
first-class operational entity because it exists before protocol generation; an
email may be received and rejected without ever producing a protocol.

Rules:

- an R1 execution can process N emails (`ops.automation_runs` R1 1:N `ops.incoming_emails`);
- each email belongs to the R1 execution that processed it;
- an email can exist even if rejected before protocol creation (pre-protocol rejection);
- an email has N attachments (`ops.incoming_emails` 1:N `ops.email_attachments`);
- when reaching protocol creation, 1 email generates exactly 1 protocol (`ops.incoming_emails` 0..1 `ops.service_requests`);
- all attachments of that email belong to the same request/protocol.

Incoming emails are strictly R1 intake records; R2 runs must never own them.
The `run_id` FK guarantees only that the referenced automation run exists. It
does not enforce `robot = 'R1'`; R1-only ownership is an application invariant.
No redundant `robot` column or trigger is introduced.

Approved conceptual fields:

- `email_id`
- `run_id`
- `received_at`
- `processed_at`
- `sender`
- `recipient`
- `subject`
- `attachment_count`
- `sender_status`
- `processing_status`
- `rejection_reason`
- `created_at`

This supports investigation of receipt, sender, processing time, attachment
count, sender acceptance, and rejection reason. Email CC and the full email body
are intentionally excluded.

#### `ops.email_attachments` — Approved responsibility

`ops.email_attachments` represents each ORIGINAL file received in the email and
its validation and processing state. An email can have N attachments.

`file_name` here means the name of the original received file.

Approved conceptual fields:

- `attachment_id`
- `email_id`
- `file_name`
- `file_type`
- `received_at`
- `validation_status`
- `validation_message`
- `establishment_count`
- `processing_status`
- `created_at`

Physical Windows paths, filesystem storage paths, and storage references are
outside the approved conceptual scope.

#### `ops.service_requests` — Approved responsibility

`ops.service_requests` represents the cancellation service request and the single
protocol created by R1.

Fundamental rule:

```text
1 email -> 1 protocol -> N attachments -> N operational items/ECs
```

The same `protocol_number` created by R1 continues being used and monitored by
R2. R2 does NOT create another protocol.

A service request may be observed in multiple R2 executions over time.
Therefore:

- there is NO `r2_run_id` field;
- R2 is related to the protocol through executions and `ops.execution_log`.

**Mandatory correction:**
`attachment_id` is removed conceptually from `ops.service_requests`. The
protocol belongs to the entire email/request, and not to only one of the N
attachments.

Approved conceptual fields:

- `request_id`
- `protocol_number`
- `email_id`
- `r1_run_id`
- `created_at`
- `updated_at`
- `status`
- `result`
- `failure_reason`
- `completed_at`
- `return_email_at`

`status` represents the consolidated protocol state across its operational
items:

- while items are pending or waiting, `status` remains `PROCESSING`;
- when all required items are concluded, `status` transitions to completed (`COMPLETED`).

The physical types, constraints, and consolidation rules are approved in phase
4.5.6 and documented in `docs/database-physical-model.md`; no database objects
have been created.

#### `ops.establishments` — Approved responsibility

`ops.establishments` represents each individual EC/operational file involved in
the protocol and functions conceptually as the operational handoff point between
R1 and R2.

Handoff flow:

- R1 validates original file -> identifies/separates by EC Matriz -> generates
  adjusted/operational file -> performs upload -> records operational state.
- Later R2 reads eligible items -> uses the same protocol -> queries portal ->
  checks availability -> downloads when available -> updates operational state.

**Approved field addition:**
`generated_file_name` is added to represent the name of the adjusted/operational
file produced by R1 for that EC and uploaded to the portal.

Explicit distinction:

- `email_attachments.file_name` = original file received by email;
- `establishments.generated_file_name` = operational/adjusted file produced by R1.

R2 uses primarily `protocol_number` + `generated_file_name` to locate the
processing in the portal.

Approved conceptual fields:

- `establishment_id`
- `request_id`
- `attachment_id`
- `establishment_number`
- `generated_file_name`
- `processing_status`
- `upload_status`
- `upload_at`
- `download_status`
- `download_at`
- `return_email_at`
- `result_message`
- `updated_at`

**Meaning of the three operational statuses:**

- `upload_status`: specific result of R1 trying to upload the file to the portal;
- `download_status`: specific situation of R2 when checking or downloading the return;
- `processing_status`: current complete operational cycle state of that item.

Examples:

- after R1: `upload_status = SUCCESS`, `processing_status = WAITING_RESULT`.
- R2 with result not yet released: `upload_status = SUCCESS`, `download_status = NOT_AVAILABLE`, `processing_status = WAITING_RESULT`.
- final state: `upload_status = SUCCESS`, `download_status = DOWNLOADED`, `processing_status = COMPLETED`.

If the portal has not yet made the result available, that does not mean the R2
execution failed technically. If a technical communication failure, timeout, or
HTTP error occurs during an attempt, that represents an error of that attempt,
without destroying the protocol or the previous R1 result.

The same establishment can be queried by multiple R2 executions until reaching a
final state.

#### `ops.execution_log` — Approved responsibility

`ops.execution_log` maintains the detailed chronological operational history of
R1 and R2. This rich timeline replaces, for the POC, the need to reproduce
separate Oracle-style log, alert, and processing structures.

Approved conceptual fields:

- `log_id`
- `run_id`
- `logged_at`
- `robot`
- `event`
- `status`
- `message`
- `email_id`
- `attachment_id`
- `request_id`
- `establishment_id`
- `created_at`

**Mandatory rule on timestamps:**
`logged_at` represents FULL DATE AND TIME of the event (never date only or time
only). The same semantic rule applies to all temporal fields representing an
instant in time:

- `started_at`
- `finished_at`
- `received_at`
- `processed_at`
- `upload_at`
- `download_at`
- `completed_at`
- `return_email_at`
- `created_at`
- `updated_at`

The physical SQL type for all time instants is `TIMESTAMPTZ`, approved in phase
4.5.6. The current decision remains semantic UTC instants; no database object
has been created.

**Difference between log status and process status:**
The approved conceptual statuses of `execution_log` remain:

- `SUCCESS`
- `ERROR`
- `EXCEPTION`

Do NOT add `WAITING` to the execution log merely because a portal result is not
yet available.

Example:

- `event = RESULT_CHECK`, `status = SUCCESS`, `message = "resultado ainda não disponível"`
- while `establishments.processing_status = WAITING_RESULT`, `establishments.download_status = NOT_AVAILABLE`.

`execution_log.status` informs whether the technical operation executed during
that attempt succeeded. `establishments.processing_status` informs the business
cycle state.

The history of R1 is never lost when R2 updates current operational state:

```text
10:15 | R1 | UPLOAD       | SUCCESS
12:00 | R2 | RESULT_CHECK | SUCCESS | resultado não disponível
13:00 | R2 | RESULT_CHECK | SUCCESS | resultado não disponível
14:32 | R2 | RESULT_CHECK | SUCCESS | resultado disponível
14:33 | R2 | DOWNLOAD     | SUCCESS
14:35 | R2 | RETURN_EMAIL | SUCCESS
```

#### Approved complete OPS relationship model

```text
ops.automation_runs
        |
        | R1 1:N
        v
ops.incoming_emails
        |
        +---- 1:N ----> ops.email_attachments
        |                        |
        |                        | 1:N (quando aplicável)
        |                        v
        |               ops.establishments
        |                        ^
        |                        | 1:N
        +---- 0..1 ---> ops.service_requests
```

Conceitualmente:

- uma execução técnica R1 processa N e-mails;
- cada e-mail possui N anexos originais;
- cada e-mail pode gerar zero ou um protocolo (`0..1`);
- se houver protocolo, ele é único para aquele e-mail;
- o protocolo continua sendo o mesmo no R2;
- um protocolo pode possuir N establishments/itens operacionais;
- cada establishment pode ser originado de um attachment;
- um mesmo protocolo/item pode ser observado por múltiplas execuções R2;
- `execution_log` correlaciona essas execuções e entidades ao longo do tempo.

The physical OPS PK/FK constraints and joins are approved in phase 4.5.6 and
documented in `docs/database-physical-model.md`; no database objects have been
created.

#### Detailed R1 and R2 execution flow

R1:

- automation run processa N e-mails;
- cada e-mail pode possuir N anexos originais;
- valida e-mail, remetente e anexos;
- cria um protocolo único por e-mail processável;
- identifica e separa ECs;
- gera arquivos operacionais ajustados (`generated_file_name`);
- realiza uploads no portal;
- atualiza estado operacional inicial;
- registra `execution_log` detalhado.

R2:

- automation run lê N itens operacionais elegíveis do banco;
- reutiliza o protocolo único criado pelo R1;
- consulta o portal por protocolo + arquivo operacional (`generated_file_name`);
- verifica prazo e status de disponibilização;
- se resultado não disponível: mantém aguardando (`WAITING_RESULT` / `NOT_AVAILABLE`);
- se resultado disponível: realiza download, atualiza estado (`COMPLETED` / `SUCCESS`), comunica cliente quando aplicável;
- em falha técnica: registra erro da tentativa no `execution_log`, preservando o protocolo e o estado anterior necessário;
- registra `execution_log` detalhado.

Uma execução R2 pode processar múltiplos itens de múltiplos protocolos. Um mesmo
item pode ser processado novamente por execuções R2 futuras até atingir o estado
final.

#### Oracle reference boundary

The reconstructed Oracle model remains useful only as a functional reference
for concepts such as RPA execution, logs, alerts, processing, emails,
attachments, ECs, temporary validation, and consolidated cancellation state.
It is not an authoritative production schema, and its physical names and table
separation are not adopted as the POC model. The six approved OPS structures
intentionally consolidate and simplify those concepts.

#### Information outside OPS

OPS does not contain:

- RAG documents, chunks, embeddings, or lexical/vector search structures;
- persistent Web Search results;
- generated LLM responses as knowledge;
- credentials, passwords, API keys, or tokens;
- security or governance audit events.

Security and governance events belong to the AUDIT schema.

### `audit`

#### Purpose and responsibility boundary

The AUDIT schema represents security and governance events generated by agent
or application security controls. It answers:

- “Was there a security or governance event, what happened, and what action did
  the system take?”

This is distinct from RAG, which owns knowledge and retrieval information and
answers what should happen or what approved documentation says, and from OPS,
which owns observed operational state and answers what actually happened
operationally. AUDIT is not used for ordinary RPA operational logs and does not
determine business process state.

The initial POC uses one approved conceptual and physical table model:

- `audit.security_events`

The physical model is approved in phase 4.5.7 and detailed in
`docs/database-physical-model.md`. No physical `audit` schema or table has
been created, and multiple audit tables must not be introduced unless a future
approved requirement requires them.

#### `audit.security_events`

Responsibility: represent security and governance events detected by
application or agent security controls.

Approved conceptual fields:

- `event_id`
- `occurred_at`
- `event_type`
- `source_component`
- `user_identifier`
- `request_reference`
- `resource_category`
- `sanitized_content`
- `action_taken`
- `result`
- `review_status`
- `reviewed_at`
- `review_note`
- `created_at`

`event_id` identifies the event and `occurred_at` records when it occurred.
`event_type` identifies its security/governance category.
`source_component` identifies the detecting or generating component, such as a
Router Agent, Knowledge Agent, Customer Support Agent, tool gateway, security
guardrail, or application boundary; it is nonblank TEXT without a fixed
category CHECK or PostgreSQL ENUM.

`user_identifier` identifies the related user only when available and
authorized. `request_reference` provides correlation to the originating
request, session, or conversation without storing the entire request payload.
`sanitized_content` contains only a sanitized description of the relevant
request or detected content and may be null when safe persistence is not
possible. Approved `action_taken` values are `BLOCK`, `DENY_ACCESS`, `REDACT`,
`SAFE_RESPONSE`, and `ESCALATE`. Approved `result` values are `SUCCESS`,
`PARTIAL`, and `ERROR`; both use TEXT + CHECK rather than PostgreSQL ENUM.

`review_status` is mandatory with default `UNREVIEWED`; `reviewed_at` and
`review_note` are optional. A reviewed event requires `reviewed_at >=
occurred_at`; an unreviewed event has no review timestamp. No separate review
table, queue implementation, review workflow, or Django Admin behavior is
approved. `created_at` records persistence of the audit record.

#### Approved conceptual event categories

`audit.security_events` must support at least:

- `CREDENTIAL_REQUEST`
- `SECRET_REQUEST`
- `DATABASE_ACCESS_REQUEST`
- `SENSITIVE_INFRASTRUCTURE_REQUEST`
- `PROMPT_INJECTION`
- `AUTHORIZATION_BYPASS_ATTEMPT`
- `SECURITY_POLICY_PROBE`

These categories use the approved TEXT + CHECK physical strategy.

`resource_category` is nullable, including for prompt-injection events, and
uses the approved values `DATABASE_CREDENTIAL`, `API_KEY`, `PASSWORD`,
`ACCESS_TOKEN`, `PRIVATE_KEY`, `COOKIE`, `CONNECTION_STRING`,
`SECRET_LOCATION`, `PROTECTED_PATH`, `AUTHENTICATION_CONTROL`,
`INTERNAL_INFRASTRUCTURE`, and `OTHER_PROTECTED_RESOURCE`. Real secrets,
tokens, keys, paths, connection strings, and credentials are never persisted.

`event_id` identifies one individual security/governance event. `occurred_at`
is the full event datetime instant; `created_at` is the distinct persistence
datetime. `user_identifier` is optional and is used only when available,
authorized, and appropriate, without redundant PII. `request_reference`
correlates a request, session, or conversation; one request may reference
multiple event records, and the full request payload is never stored.

#### Sanitization and secret handling

AUDIT must never persist passwords, API keys, access or refresh tokens,
cookies, private keys, connection strings, database credentials, raw secret
values, secret locations, or other credential-shaped sensitive values. When
sensitive content is detected, the conceptual flow is:

`sensitive input -> detection -> sanitization/redaction -> security action -> audit.security_events`

Only a sanitized description may be stored. For example, the audit description
may state that credential-like sensitive content was detected and removed; it
must never reproduce the value itself.

### AUDIT cardinality and lifecycle

One request produces zero to N `audit.security_events` records: a normal
request produces zero, a simple protected request may produce one, and a
multi-threat request may produce multiple records. Each event record has one
conceptual `event_type`; multi-threat records share `request_reference` and do
not use arrays, JSON collections, or junction tables.

The conceptual lifecycle is:

`input -> detection -> sanitization/redaction -> action -> persist audit.security_events -> safe response`

`action_taken` records the applied control, while `result` records the distinct
decision outcome. Review metadata follows the approved phase 4.5.7 nullability
and timestamp checks; no review workflow is implemented.

#### Information outside AUDIT

AUDIT does not contain ordinary R1/R2 execution logs, email receipt events,
attachment processing, protocol status, EC processing, upload or download
events, or ordinary RPA errors and exceptions unrelated to security or
governance. Those remain in OPS.

AUDIT also does not contain RAG documents, chunks, embeddings, lexical or
vector retrieval structures, source content, or persistent Web Search results.
Knowledge and retrieval data remain in RAG, while volatile Web Search evidence
remains live unless separately approved for governed ingestion.

Full user prompts and conversations, normal agent responses, secrets, and
credentials are not audit content by default. A security event records the
control outcome and protective action; it does not itself create an OPS event
unless there is an independent operational reason.

## Approved Complete Conceptual Schema Architecture

Phase 4.1 is complete. The following model is the approved complete conceptual
schema architecture and is the input to the detailed schema-architecture phases.

### RAG

RAG is the source of governed knowledge, documentation, rules, provenance,
retrieval evidence, and expected behavior. It conceptually answers:

- What should happen?
- What does the approved documentation say?
- What is the documented rule?

Approved conceptual structures:

- `rag.sources`
- `rag.documents`
- `rag.chunks`
- `rag.ingestion_runs`

RAG does not own observed RPA operational state, protocol runtime state,
ordinary RPA logs, security or governance audit events, credentials, or
secrets.

### OPS

OPS is the source of observed operational facts and process state. It
conceptually answers:

- What actually happened?
- What is the current state of the request or protocol?
- What occurred during R1 or R2 execution?

Approved conceptual structures:

- `ops.automation_runs`
- `ops.incoming_emails`
- `ops.email_attachments`
- `ops.service_requests`
- `ops.establishments`
- `ops.execution_log`

R1 receives and validates email and attachments, identifies establishments,
creates the cancellation protocol, starts operational processing, and records
execution history. R2 works with an existing protocol, does not create a new
protocol, monitors processing and return state, updates operational state, and
records completion, errors, and exceptions.

OPS does not own persistent RAG knowledge or security and governance audit
events.

### AUDIT

AUDIT is the source of security and governance events. It conceptually
answers:

- Was there a security or governance event?
- What protective action was taken?
- Was sensitive content blocked, denied, ignored, redacted, or sanitized?

Approved conceptual structure:

- `audit.security_events`

AUDIT is not a general application or RPA execution log. Ordinary R1/R2
operational history remains in OPS. Real credentials, passwords, API keys,
access tokens, refresh tokens, cookies, private keys, connection strings,
database credentials, secret locations, and other secret values must never be
persisted in AUDIT. Only sanitized security-event information may be stored.

### Final ownership boundaries

The schemas have distinct ownership and lifecycle responsibilities:

- RAG owns governed knowledge, rules, documentation, retrieval evidence, and
  expected behavior. It answers what should happen, what the approved
  documentation says, and what the documented rule is.
- OPS owns observed operational facts and process state. It answers what
  actually happened, the current protocol state, and what occurred during R1
  or R2 execution.
- AUDIT owns security and governance events. It answers whether such an event
  occurred, what protective action the system took, and whether sensitive
  content was sanitized or blocked.

RAG does not own protocol state, R1/R2 execution state, operational email or
attachment processing, establishment state, upload/download state, or security
audit events. OPS does not own the approved knowledge corpus, RAG documents,
chunks, embeddings, retrieval representations, or security/governance events.
AUDIT is not a general system or operational log and does not own ordinary RPA
events, process state, or RAG knowledge and retrieval data. Credentials and
secrets belong to none of the schemas.

No physical RAG, OPS, or AUDIT schema or table has been created.

### Application-coordinated information flow

The schemas remain separate sources of truth for their domains. They do not
directly copy or synchronize domain data into one another: operational facts
are not copied into RAG, knowledge is not copied into OPS, ordinary OPS logs
are not duplicated in AUDIT, and security events are not duplicated as OPS
history.

The application and agent layer coordinates access according to responsibility:

- consult RAG for documented knowledge and expected behavior;
- consult OPS for observed operational facts;
- write or read AUDIT for security and governance events when applicable.

A single request may consult more than one schema. The application may
correlate evidence from different domains when needed, but this conceptual
approval does not define physical foreign keys, cross-schema constraints,
identifiers, indexes, views, materialized views, joins, or SQL queries. Those
decisions remain for later architecture and physical-model phases.

### LLM interpretation and grounding

RAG, OPS, and AUDIT do not reason. They provide governed knowledge, evidence,
state, and security/governance records. Specialized agents and tools retrieve
the evidence required for the request, and the LLM interprets the supplied
evidence, compares it when necessary, and produces the grounded user-facing
conclusion.

The LLM must not invent missing evidence. Existing grounding and
insufficient-evidence rules remain in force. Generated conclusions and
responses do not automatically become RAG documents, chunks, embeddings, or
approved persistent knowledge. Any future addition to RAG must follow the
approved source, ingestion, and governance process.

### Multi-schema reasoning example

For a question such as “Is protocol X delayed?”, RAG may provide the documented
expected processing time while OPS provides the protocol creation time,
current status, and observed processing history. The application and agent
layer supplies both evidence sets to the reasoning flow, and the LLM may
compare expected with observed behavior to produce a grounded conclusion.

The comparison result is not persisted back into RAG, and OPS facts are not
duplicated into RAG.

### Router, specialized agents, and LangGraph

The approved conceptual flow is:

```text
                     User
                      |
                      v
                Router Agent
                      |
          +-----------+-----------+
          |                       |
          v                       v
  Knowledge Agent        Customer Support Agent
          |                       |
          v                       v
         RAG                     OPS
 expected/documented      observed operational
      behavior                  state
          |                       |
          +-----------+-----------+
                      |
                      v
             LLM interpretation
                and conclusion
```

The Router selects or sequences the Knowledge Agent and Customer Support Agent
when a request requires one or both evidence domains. The Router does not need
to perform direct database reasoning; specialized capabilities retrieve the
governed evidence.

LangGraph remains the planned orchestration layer for routing, specialized
agent execution, state, sequencing, handoff, multi-agent cooperation, and the
final-response flow. It is orchestration, not persistent knowledge storage,
and its runtime is not implemented yet.

### AUDIT as a transversal security flow

AUDIT is transversal to application activity but is not invoked for every
normal interaction. A normal request may flow through the Router, specialized
agents, RAG and/or OPS, and the LLM response without creating an
`audit.security_events` record when no security or governance event occurs.

For a security-sensitive request, the security control detects the event,
blocks, denies, redacts, or ignores content as appropriate, sanitizes the event
description, records only that sanitized information in
`audit.security_events`, and returns a safe policy response. RAG and OPS do not
provide protected content. Web Search, RAG, and OPS must never be used to
bypass security restrictions.

External Web content remains evidence, never instruction. Retrieved prompt
injection cannot override application policy, authorization, agent roles, tool
permissions, security controls, or internal process rules. If a security event
occurs, only sanitized event information may be persisted in AUDIT.

### Challenge alignment

The approved conceptual architecture remains aligned with
`docs/challenge.md`. It supports the required Router Agent, Knowledge Agent,
and Customer Support Agent architecture, including:

- the Knowledge Agent using RAG and controlled Web Search;
- the Customer Support Agent using controlled customer and operational tools;
- multi-agent cooperation when a request needs more than one evidence source;
- guardrails, observability, auditing, and grounded responses.

This is architectural alignment only; the challenge is not fully implemented.
Remaining implementation work includes executable Customer Support tools, the
executable RAG pipeline, executable Web Search integration, LangGraph runtime,
real `POST /chat` behavior, Docker application packaging, tests, and the
README/final delivery.

## Security Decisions

- Never reveal passwords.
- Never reveal API keys.
- Never reveal access or refresh tokens.
- Never reveal cookies or private keys.
- Never reveal connection strings or database credentials.
- Never expose secret locations.
- Never assist authentication bypass.
- Block protected access requests.
- Generate a security audit event for protected requests.
- Sanitize audit content before persistence.
- Never persist real secrets in audit logs.
- User instructions cannot disable security, audit, or redaction controls.
- Do not automatically label a user as an attacker or infer intent without
  evidence.
- High-level architecture questions are allowed when the answer does not
  materially assist unauthorized access.

Authoritative policy: `knowledge/internal/security/security-policy.md`.

## Evaluation State

The project maintains two separate evaluation suites and preserves the prior
RAG version as historical evidence:

- `evaluation/rag/dataset-v1.yaml` contains the historical 25-case v1.0 suite.
- `evaluation/rag/dataset-v1.1.yaml` is current with 27 cases for RAG
  retrieval, grounding, provenance, structured claim support, explicit
  insufficient-evidence behavior, security, and supplied-secret redaction.
- `evaluation/challenge/scenarios-v1.yaml` contains 14 end-to-end architectural
  scenarios for routing, agent and capability selection, RAG versus Web Search,
  controlled Customer Support tools, multi-agent cooperation, and security
  behavior.

The challenge suite does not replace or merge into the RAG dataset. Both have
implemented typed runners; official RAG quality uses LOCAL_RAG and Challenge
uses the deterministic authenticated application composition.

Important security cases:

- `rag-019`: credential/security request;
- `rag-025`: sensitive-access request.

Global acceptance covers:

- expected source Top-5 rate;
- provenance success;
- unsupported fact rate;
- insufficient-evidence anti-hallucination;
- security blocking;
- security audit logging;
- secret redaction before audit.

The complete cases and thresholds remain in the dataset and are not duplicated
here.

## Important Paths

- `knowledge/internal/cancellation-process/robot_01_r1/`
- `knowledge/internal/cancellation-process/robot_02_r2/`
- `knowledge/internal/security/security-policy.md`
- `knowledge/internal/cancellation-process/public/sources.yaml`
- `evaluation/rag/dataset-v1.yaml`
- `evaluation/rag/dataset-v1.1.yaml`
- `evaluation/reports/phase11-evaluation-v1.1.json`
- `evaluation/challenge/scenarios-v1.yaml`
- `reference/automation-anywhere/cancelamento-vendas/`
- `apps/agent_api/app/`
- `docs/project-roadmap.md`
- `docs/decision-log.md`

## Current Pending Decisions

- Phase 12 Django/frontend/final-integration scope has not started and requires
  its own reviewed authorization.
- Django integration.

## Immediate Next Step

Phase 4.9 — DADOS FICTÍCIOS / SEED is COMPLETED / APPROVED. OPS seeds are
data-driven JSON definitions under `database/seed/ops/scenarios/`, discovered
automatically, validated by Pydantic, and executed through:

```text
JSON scenario -> loader / Pydantic validation -> generic scenario executor
-> PostgresDatabase.transaction() -> OperationalRepository -> PostgreSQL OPS
```

Protocol number is the idempotency key; existing protocols are skipped without
mutation. Each scenario is atomic. R1 supports success or error termination,
R2 may be absent after an R1 failure, and R2 supports success and failure
outcomes. Seed content is synthetic development/POC data and remains within
repository boundaries. Phase 4.10 validation and Phase 5 ingestion are
complete. Phase 6 publication, Phase 7 hybrid retrieval, and Phase 8 grounding
are complete; Phase 9 multi-agent/RAG/tools orchestration is now current and
has not started.

Phase 4.5 is COMPLETED / APPROVED: the final gate validated all 11 table
models, relationships, hybrid PKs, integrity, lifecycle nullability, planned
indexes, retention, retrieval configuration and physical field security.
The detailed authority is `docs/database-physical-model.md`; historical
decisions remain in `docs/decision-log.md`. R1-only intake is application-
enforced; its FK verifies run existence only.

Phase 4.6 physical implementation is complete and validated.

Phase 4.7 is COMPLETED / APPROVED under DEC-123 through DEC-131. All 11
completion criteria passed: Python >=3.14 confirmed; `pyproject.toml`
declares approved exact pins (`psycopg[binary]==3.3.6`, `pgvector==0.5.0`);
`psycopg==3.3.6`, `psycopg-binary==3.3.6`, `pgvector==0.5.0`, `tzdata==2026.4`,
and editable `getnet-support==0.1.0` are installed and verified in the active
virtual environment; `pip check` passed with zero broken requirements; imports
of `psycopg`, `AsyncConnection`, `pgvector`, and callable `register_vector_async`
succeeded; application compile validation (`compileall apps`) passed; SQLAlchemy,
Alembic, psycopg2, asyncpg, and pooling remain excluded; no repository or
runtime DB code was introduced; and zero database objects, migrations, commits,
or pushes occurred.

Phase 4.8 is COMPLETED / APPROVED. Phase 4.8.1 (DEC-133), Phase 4.8.2 (DEC-134),
Phase 4.8.3 (DEC-135), Phase 4.8.4 (DEC-136), Phase 4.8.5 (DEC-137), and
Phase 4.8.6 (DEC-138), Phase 4.8.7 (DEC-139), Phase 4.8.8 (DEC-140),
Phase 4.8.9 (DEC-141), Phase 4.8.10 (DEC-142), Phase 4.8.11 (DEC-143),
Phase 4.8.12 (DEC-144), Phase 4.8.13 (DEC-145), and Phase 4.8.14 (DEC-146) are
COMPLETED / APPROVED:
- 4.8.1 approved access pipeline (`FastAPI / Agents -> Services -> Repositories -> Database Infrastructure -> Psycopg 3 + pgvector -> PostgreSQL 17`), strict repository boundary, and Pydantic models with zero ORM.
- 4.8.2 approved connection configuration reusing PostgreSQL environment variables (`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, etc.), structured keyword argument passing, `.env` as the runtime source, and `.env.example` as local POC reference material without `DATABASE_URL`.
- 4.8.3 approved connection lifecycle and `AsyncConnectionPool` (`psycopg-pool==3.3.2` approved dependency, min_size 1, max_size 5, acquisition timeout 5s, lifespan management with `await pool.open()` and `await pool.close()`, per-connection `configure` callback for pgvector, single pool per process, and fail-closed readiness).
- 4.8.4 implemented and validated `DatabaseConfig` and centralized
  `PostgresDatabase` with an `open=False` pool and explicit
  open/wait/connection/close lifecycle. No real connection, SQL, pgvector
  registration, repository, or transaction abstraction was introduced.
- 4.8.5 implemented centralized `register_vector_async` integration through
  `AsyncConnectionPool.configure`, once per new physical connection, with
  transaction cleanup and fail-closed error propagation. Mocked validation
  passed without a real PostgreSQL connection.
- 4.8.6 defined `RAGRepository`, `OperationalRepository`, and
  `AuditRepository` contracts plus a connection-bound `BaseRepository`.
  Repositories receive an injected `AsyncConnection`, own neither pools nor
  transactions, do not commit or roll back, and remain isolated to their
  assigned schema. At the 4.8.6 completion point, mapping, error translation,
  and real database validation were deferred to Phases 4.8.11, 4.8.12, and
  4.8.13 respectively; those phases are now complete.
- 4.8.7 implemented parameterized PostgreSQL persistence and FTS/exact-cosine
  retrieval over the four RAG tables, with ACTIVE eligibility. The earlier
  pre-4.8.11 implementation used temporary `RepositoryRecord` retrieval
  results; current retrieval methods return `Sequence[SearchCandidate]`.
- 4.8.8 implemented parameterized persistence and factual evidence queries
  over the six OPS tables, without diagnosis or inference.
- 4.8.9 implemented secret-safe, sanitized security-event persistence and
  review/correlation queries over `audit.security_events` only.
- 4.8.10 implemented `PostgresDatabase.transaction()` with one pool checkout,
  one injected connection, and Psycopg native commit/rollback semantics.
  Repositories remain transaction-free; no Unit of Work, nesting framework, or
  real PostgreSQL validation was introduced.
- 4.8.11 implemented the centralized database-row-to-Python/Pydantic result
  mapping layer in `apps/agent_api/app/database/mapping.py` backed by immutable
  Pydantic read models in `apps/agent_api/app/database/models.py`. Raw Psycopg
  `dict_row` dictionaries no longer cross the repository read boundary. The
  persisted RAG chunk model read from the database is `PersistedChunk`, while
  structural chunking domain model `Chunk` remains untouched.
  `SearchCandidate` combines `PersistedChunk`, `RetrievalProvenance`, and
  channel evidence (`retrieval_channel`, `channel_rank`, `channel_score`).
  Final `RetrievedChunk` remains the post-RRF ranked retrieval result combining
  `PersistedChunk`, `RetrievalProvenance`, final `rank`, final `score`, and
  `matched_channels`, consumed by `ContextBuilder`/grounding. RRF runtime and
  grounding runtime remain unimplemented. OPS factual models
  (`AutomationRunRecord`, `ServiceRequestRecord`, `EstablishmentRecord`,
  `ExecutionLogRecord`, `ProtocolStatusFacts`, `ExecutionFailureEvidence`) and
  AUDIT model (`SecurityEventRecord`) strictly represent database read results.
  Write payloads continue to use `RepositoryRecord = Mapping[str, object]`.
  DEC-142 composable transaction architecture remains intact. At the 4.8.11
  completion point no real DB connection had been opened; Phases 4.8.13 and
  4.8.14 have since completed that validation. No ORM was introduced.
- 4.8.12 implemented centralized, secret-safe translation of recognized
  Psycopg/pool failures into stable application-facing errors. Pool availability
  failures are conservatively retryable; integrity and query failures are not.
  Original driver failures are preserved as causes, while Pydantic validation,
  application, and cancellation/control-flow exceptions remain unchanged. No
  retries, automatic logging, real PostgreSQL connection, or SQL execution was
  introduced.
- 4.8.13 validated the real local runtime connection path through
  `load_database_config()` and `PostgresDatabase`: pool open/wait/acquire/close,
  PostgreSQL major version 17, database `getnet_support`, pgvector 0.8.6, and a
  registered-adapter vector round-trip all passed without exposing secrets.
- 4.8.14 validated every public concrete repository method against real
  PostgreSQL. RAG persistence, lifecycle, typed mappings, FTS and exact cosine
  retrieval passed; OPS lifecycle and evidence queries passed; AUDIT sanitized
  persistence/review passed; a real UNIQUE violation mapped to
  `SafeIntegrityError` with the original Psycopg cause; all synthetic writes
  rolled back and the final read-only cleanliness check found zero test records.
- 4.8.15 reconciled the roadmap, project context, repository contracts, and
  decision log with the real validation evidence.
- 4.8.16 completed the final audit: the six-test real integration suite and
  complete 189-test fast suite passed, six real tests remained opt-in/skipped
  during the fast run, compilation/dependency/import/whitespace checks passed,
  protected files remained unchanged, and DEC-147 approved Phase 4.8.

Phase 4.9 — DADOS FICTÍCIOS / SEED is COMPLETED / APPROVED. Its JSON-driven
seed architecture, validation, generic executor, repository-backed persistence,
transaction-per-scenario behavior, and lifecycle variation support are complete.
Phase 4.10 VALIDAÇÃO DO BANCO is COMPLETED / APPROVED. Real connection,
transaction, representative FK/constraint, pgvector, FTS, OPS factual-read,
AUDIT, regression, compilation, dependency, and whitespace validation passed.
Phase 5 INGESTION EXECUTÁVEL is complete. It implements UTF-8 curated Markdown
and approved public-registry loading, deterministic normalization and SHA-256
checksums, eligibility validation, ingestion decisions, structural chunking,
JSON-compatible provenance, immutable prepared-ingestion contracts, a shared
preparation service, and manual CLI paths. It prepares artifacts only: no
embedding, FTS payload, or incomplete chunk publication occurs.

Phase 6 FASTEMBED EXECUTÁVEL is COMPLETED / APPROVED under DEC-156 through DEC-159.
It implements the local FastEmbed adapter (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`,
384 dims, local ONNX CPU), native weighted PostgreSQL FTS vector generation (weights A, B, C, D),
publication contracts (`PublicationChunk`, `PublicationResult`), centralized `RAGPublicationService`,
and atomic publication via `PostgresDatabase.transaction()`. Embeddings are computed and validated
pre-transaction; failures trigger full transaction rollback, preserving previous retrievable state.
`SKIPPED_UNCHANGED` avoids re-embedding and replacement when checksum is identical; `REINGEST`
atomically replaces all chunks. Real representative internal documents (PDD, SDD, Technical Overview)
are published in `getnet_support` (1 active source, 3 active documents, 99 chunks). Real lexical and
semantic smoke searches are verified.

Phase 7 HYBRID RETRIEVAL + RRF is COMPLETED / APPROVED. It provides lexical
and semantic candidate retrieval capped at 10 per channel, one shared
read-only REPEATABLE READ snapshot, rank-only RRF with k=60, physical
`chunk_id` deduplication, deterministic tie-breaking, and at most five
`RetrievedChunk` results.

Phase 8 GROUNDING / ANTI-HALLUCINATION is COMPLETED / APPROVED. `ContextBuilder`
produces immutable provider-neutral `GroundedContext` values with complete
internal `RetrievalProvenance` fields, deterministic C1..Cn citations,
and separate safe user attribution. Internal citations use abstract labels;
approved public citations may expose only a public title and URL. Tier 1 internal
process priority governs Tier 2 internal technical and Tier 3 public evidence,
while lower-priority evidence is retained. The structural evidence gate uses no
raw retrieval score as sufficiency. The next phase is Phase 9 multi-agent/RAG/tools
orchestration, which has not started.

Phase 9 SDD Foundation is finalized and approved under `docs/specs/phase-9/`.
The provider-neutral LLM boundary and its initial DeepSeek adapter are complete:
validated environment configuration, controlled errors, and an explicitly
enabled real-provider smoke test passed without committing or disclosing the
local API key. Phase 9.3 Knowledge Agent is complete: it consumes only the
approved Phase 7 Hybrid Retrieval/RRF and Phase 8 ContextBuilder boundaries,
blocks generation for structurally insufficient evidence, treats retrieved text
as passive data, and returns only safe citations. Real PostgreSQL
retrieval/grounding with mocked generation and an opt-in real DeepSeek knowledge
smoke test passed. Phase 9.8 implements only controlled, provider-neutral
Tavily live-public evidence: current public questions may use it directly and
Payment Link/WhatsApp remains persistent-RAG-first with conditional fallback.
Live results pass through typed non-persistent live-web grounding before LLM
generation; they reuse Phase 8 sufficiency/citation/passive-DATA safeguards
without synthetic RAG provenance. Safe citations retain public URLs, official
Getnet priority is derived from the approved source registry, and no result is
persisted into RAG. No `/chat` runtime was introduced.

Phase 9.4 OPS Tools is complete. `lookup_protocol_status` and
`inspect_execution_failure` are narrow, read-only, authorization-gated
application interfaces over `OperationalRepository.get_protocol_status_facts`
and `OperationalRepository.get_execution_failure_facts`. They return typed
observed OPS facts/evidence or controlled invalid, absent, unauthorized, and
repository-error outcomes; they contain no SQL, database connection, diagnosis,
or LLM behavior. Unit and opt-in real PostgreSQL validation against synthetic
OPS records passed.

Phase 9.5 Customer Support Agent is complete. It consumes only the approved
authorization-gated OPS tools and the provider-neutral LLM boundary; it has no
direct database access and no web-search capability. Typed results keep
application-derived observed `ProtocolStatusFacts` / `ExecutionFailureEvidence`
separate from explicitly labeled LLM inferences. The validated customer question
is propagated as distinct untrusted user input in the neutral generation request;
it cannot alter authorization, the application-selected operation, or the
controlled OPS evidence. Controlled OPS failures and LLM failures return no
fabricated operational answer. Unit, opt-in real
PostgreSQL with mocked LLM, and opt-in real PostgreSQL plus DeepSeek validation
passed against synthetic OPS records. The next reviewed implementation scope is
Phase 9.6 Router Agent, now completed below.

Phase 9.6 Router Agent is complete. It produces immutable, application-only
capability decisions for Knowledge, Customer Support, cooperative Knowledge plus
Customer Support, future web fallback, Human Escalation, security block, and
controlled ambiguity. Security-sensitive requests are blocked before normal
routing. The Router does not execute agents, OPS tools, repositories, web search,
human handoff, or LLM calls. Its deterministic routing matrix covers all fourteen
approved challenge scenarios. The next reviewed implementation scope is Phase 9.7
LangGraph orchestration.

Phase 9.7 LangGraph orchestration is complete. An acyclic graph invokes the
approved Router once, then coordinates the existing Knowledge and Customer
Support capabilities without duplicating their behavior. Cooperative requests
retain both typed results, Knowledge citations, and Customer Support
FACT/INFERENCE separation. Security-block and ambiguous routes terminate without
downstream capability calls; web and human routes preserve explicit deferred
markers for Phases 9.8 and 9.9. Real PostgreSQL integrations and an opt-in real
DeepSeek smoke for Knowledge-only, Customer-Support-only, and cooperative paths
passed without database mutation. Phase 9.8 adds bounded Tavily public web
fallback through injected typed contracts while preserving the acyclic graph,
security terminals, OPS privacy, and non-persistence. Phase 9.11 completed
end-to-end validation. Phase 9.9 adds only the typed,
non-persistent human-handoff state machine: explicit offer, confirmation,
`WAITING_HUMAN`, authorized operator acceptance, human ownership, and explicit
return/resolution. It does not implement Django, a physical queue, polling,
ticket automation, or persistence. Phase 9.10 replaces the FastAPI placeholder
with an authenticated, typed adapter over `LangGraphOrchestrator`. Internal
Bearer service authentication runs before orchestration; body `user_id` alone
grants no trust. Responses and errors are allowlisted for a future Django
consumer without exposing graph, provider, repository, RAG, or database
internals. Protected requests now remain Router-blocked while their sanitized
event is persisted only through `SecurityAuditService`,
`PostgresSecurityAuditSink`, and `AuditRepository`; audit failure fails closed.
Phase 9 is complete. No Django, conversation persistence, queue, or database
schema is introduced; broader Security / Audit Runtime work is Phase 10 scope.

## Documentation Maintenance Rules

- `project-roadmap.md` tracks execution status, phases, and sequencing.
- `project-context.md` tracks the current approved working state.
- `decision-log.md` tracks durable approved decisions and concise rationale.
- Chat messages and transcripts are discussion artifacts, not authoritative
  project documentation.
- Approved conclusions should be persisted in the appropriate project document
  when they materially change project state.
- Routine tests, formatting, temporary experiments, and non-semantic cleanup do
  not require continuity-document updates.
- Secrets and protected access details must never be persisted in continuity
  documentation.
