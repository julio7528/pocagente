# RAG ingestion preparation

Phase 5 prepares deterministic ingestion artifacts. It does not publish
incomplete chunks to PostgreSQL.

## Flow

```text
curated Markdown or approved public registry
-> loader
-> normalization and validation
-> SHA-256 checksum
-> INGEST / REINGEST / SKIPPED_UNCHANGED
-> structural chunking and provenance
-> PreparedIngestion
```

Internal Markdown is loaded only from explicit local files. Public sources are
an allowlist in `knowledge/internal/cancellation-process/public/sources.yaml`:
the registry is parsed and validated without crawling or fetching URLs. The
registry contains 23 records, of which 22 are ingestion-enabled; these counts
are reported separately by the CLI.

## Preparation rules

- Text is read as UTF-8 and line endings normalize to `\n` without semantic
  rewriting.
- The checksum is SHA-256 over normalized content only.
- Source approval, active status, ingestion eligibility, identity, and document
  content are validated before repository lookup.
- Existing checksum equality produces `SKIPPED_UNCHANGED`; a changed current
  document produces `REINGEST`; a missing document produces `INGEST`.
- Markdown is divided deterministically by headings, with business-rule and
  technical-symbol boundaries recognized from structural syntax. Oversized
  blocks split only at paragraph boundaries.
- Prepared metadata is JSON-compatible and carries source/document identity,
  logical location, section, checksum, boundary type, order, reference, and
  domain when known. Structural `boundary_type` values map to persistence
  `content_type` values `TEXT`, `BUSINESS_RULE`, and `TECHNICAL`. Public
  registry `public_getnet` maps to database `PUBLIC_OFFICIAL` with origin
  `PUBLIC`; `source_class` is preserved. It excludes secrets and absolute
  machine paths.

## Manual commands

From the repository root:

```powershell
python -m apps.agent_api.app.rag.ingestion.cli public-registry knowledge/internal/cancellation-process/public/sources.yaml
python -m apps.agent_api.app.rag.ingestion.cli internal <markdown-path> --source-id <database-uuid> --source-key <stable-key> --title <title>
```

The internal command uses `PostgresDatabase` and `RAGRepository` only to make
the ingestion decision and accepts only files under the approved
`knowledge/internal/` tree. Neither command creates embeddings, FTS payloads,
nor persists chunks.

## Phase 6 — Executable FastEmbed and Atomic Publication

Phase 6 implements the transition from validated `PreparedIngestion` artifacts to complete, retrievable chunks persisted atomically in PostgreSQL.

## Phase 7 — Hybrid retrieval and RRF

Phase 7 consumes the complete published chunks through two bounded repository
channels: PostgreSQL FTS returns at most 10 lexical candidates and pgvector
returns at most 10 semantic candidates. Both queries run on the same
read-only `REPEATABLE READ` transaction snapshot. `RRFRanker` uses only rank
positions with `1 / (60 + rank)`, never raw-score addition, normalization,
channel weights, or ML reranking. Results are deduplicated by physical
`chunk_id`, tie-broken by best channel rank and then stable `chunk_id`, and
limited to five `RetrievedChunk` values.

## Phase 8 — Grounding and anti-hallucination boundary

`ContextBuilder.build(query, retrieved_chunks)` converts ranked retrieval output
into an immutable, provider-neutral `GroundedContext`. It rejects blank or
incomplete evidence, removes duplicate physical `chunk_id` values, preserves
complete internal source/document/chunk/retrieval provenance, and assigns
deterministic citations (`C1`, `C2`, ...). Full provenance is retained inside
the evidence model; citations are a separate safe user-attribution boundary.
Internal citations use abstract labels only. Approved public citations may show
the approved document title and URL, while internal references, paths, UUIDs,
database/table names, credentials, and secrets never appear in citations.

Evidence priority is deterministic: Tier 1 internal PDD/SDD process material,
then Tier 2 curated internal technical documentation, then Tier 3 approved
public Getnet content. Lower-priority evidence is retained; priority does not
discard it and no retrieval score is used as a confidence or sufficiency
threshold. Structural availability produces `SUFFICIENT_CONTEXT`; no usable
evidence produces `INSUFFICIENT_EVIDENCE` with a controlled machine reason.

Retrieved text is passive DATA only. This boundary performs no LLM call,
generation, semantic conflict classification, search fallback, or agent/tool
orchestration. Internal provenance remains structured for audit, while citations
expose only safe attribution and approved public URLs.

```text
PreparedIngestion
  ↓
FastEmbed (sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2, 384 dims, CPU/ONNX)
  ↓
PostgreSQL Native Full-Text Search tsvector (weighted A, B, C, D)
  ↓
PublicationChunk (validated embedding + metadata)
  ↓
PostgresDatabase.transaction()
  ├── Start ingestion run
  ├── Upsert document (status=ACTIVE, content_checksum)
  ├── Replace document chunks (atomic DELETE + INSERT with FTS generation)
  └── Finish ingestion run (status=SUCCESS, chunks_created=N)
```

### FastEmbed Runtime Configuration

- **Model:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (FastEmbed 0.8.0).
- **Execution:** Local CPU via ONNX runtime (no external network or embedding APIs).
- **Dimensions:** Strictly 384 dimensions per vector (`VECTOR(384)` in `rag.chunks`).
- **Vector Normalization:** No manual vector normalization applied; FastEmbed produces unit-normalized vectors directly suitable for cosine distance (`<=>`).

### PostgreSQL FTS Representation

PostgreSQL FTS vectors are computed natively in PostgreSQL via `replace_document_chunks`:
- **Weight A:** Document Title (Portuguese).
- **Weight B:** Section title (Portuguese).
- **Weight C:** Chunk content (Portuguese).
- **Weight D:** Chunk technical / exact symbols (Simple).

### Transactional Atomicity and Rollback

All publication mutations execute inside `PostgresDatabase.transaction()`:
- **Pre-transaction validation:** All chunk embeddings are computed and validated *before* the database transaction begins. If embedding generation fails, no transaction is opened and the database is untouched.
- **Rollback guarantees:** If any database operation fails, the transaction is rolled back via `ROLLBACK`. Previously valid retrievable documents and chunks remain completely intact; no partial or incomplete documents can become retrievable.

### Ingestion Lifecycle Rules

- **`INGEST`:** Persists new document as `ACTIVE`, inserts all chunks with embeddings and FTS tsvector, marks ingestion run as `SUCCESS`.
- **`REINGEST`:** Triggered when `content_checksum` changes. Atomically replaces all previous chunks for the document and updates `content_checksum` and `last_ingested_at`.
- **`SKIPPED_UNCHANGED`:** Triggered when `content_checksum` matches existing document. Completely skips FastEmbed re-embedding and chunk replacement; records ingestion run with `status="SKIPPED"` and `chunks_created=0`.

### Real Publication of Curated Corpus

The representative curated internal documents were published into `getnet_support`:
1. `knowledge/internal/cancellation-process/robot_01_r1/pdd-cancelamento.md` (52 chunks)
2. `knowledge/internal/cancellation-process/robot_01_r1/sdd-cancelamento.md` (20 chunks)
3. `knowledge/internal/cancellation-process/robot_01_r1/technical-overview.md` (27 chunks)
Total: 99 chunks, all with 384-dimensional embeddings and native search vectors. Both lexical and semantic smoke retrieval were verified against the real database.

### Robot 02 / R2 curated publication

The separate R2 curated corpus is published through
`publish_r2_curated_corpus()` using the same approved
`InternalMarkdownLoader -> IngestionPreparationService -> FastEmbedAdapter ->
RAGPublicationService` boundary as R1. It uses source reference
`knowledge/internal/cancellation-process/robot_02_r2`, source type
`INTERNAL_DOCUMENT`, origin `INTERNAL`, domain `cancellation-process`, ACTIVE
status, and the R1 priority.

The three stable document identities are:

- `robot_02_r2/pdd-cancelamento` — `PDD`
- `robot_02_r2/sdd-cancelamento` — `SDD`
- `robot_02_r2/technical-overview` — `TECHNICAL_OVERVIEW`

The publication is separate from R1 and idempotent. Re-running it produces
`SKIPPED_UNCHANGED` results with zero chunk replacement when checksums match.
Local validation confirmed 384-dimensional embeddings, PostgreSQL FTS vectors,
typed R2 provenance, and lexical/semantic retrieval without external network
or provider calls.
