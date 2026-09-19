# Getnet Support — Decision Log

This log records durable approved decisions and concise rationale. It does not
contain chat transcripts or internal chain-of-thought.

## DEC-001 — Django and FastAPI separation

**Decision:** Django handles frontend, authentication/session, and admin.
FastAPI handles internal agent, RAG, tool, and provider APIs.

**Rationale:** Keep user-facing web responsibilities separate from agent and
RAG execution.

**Status:** Approved

---

## DEC-002 — PostgreSQL as the primary POC database

**Decision:** Use PostgreSQL for relational persistence in the POC.

**Rationale:** Provide one durable relational platform for knowledge metadata,
operational state, and audit data while preserving schema separation.

**Status:** Approved

---

## DEC-003 — pgvector for semantic storage and search

**Decision:** Use pgvector with PostgreSQL instead of a separate vector
database.

**Rationale:** Keep semantic and relational retrieval in the same governed data
platform for the POC.

**Status:** Approved

---

## DEC-004 — Docker for local database infrastructure

**Decision:** Run PostgreSQL and pgvector through Docker Compose locally.

**Rationale:** Provide reproducible, isolated local infrastructure with a
persistent volume.

**Status:** Approved

---

## DEC-005 — FastEmbed as the embedding provider

**Decision:** Use local FastEmbed instead of the superseded
sentence-transformers implementation for the current POC.

**Rationale:** Keep embeddings local and provider-independent while using an
ONNX-based runtime.

**Status:** Approved; final model/dimension reconciliation remains pending

---

## DEC-006 — Hybrid lexical and semantic retrieval

**Decision:** Combine PostgreSQL Full Text Search with pgvector semantic
retrieval.

**Rationale:** Capture both exact terminology and semantic similarity.

**Status:** Approved

---

## DEC-007 — Reciprocal Rank Fusion

**Decision:** Use RRF to merge lexical and semantic candidate rankings without
an external reranker initially.

**Rationale:** Provide a simple, provider-neutral fusion method suitable for
evaluation and tuning.

**Status:** Approved

---

## DEC-008 — Initial final Top-K of 5

**Decision:** Deliver an initial final Top-K of 5 chunks after fusion.

**Rationale:** Bound context while retaining the most relevant grounded
evidence; the value remains configurable.

**Status:** Approved

---

## DEC-009 — Structural chunking

**Decision:** Chunk by sections, business rules, and technical symbols rather
than relying on arbitrary fixed-size splitting.

**Rationale:** Preserve coherent rules and technical meaning for retrieval and
citation.

**Status:** Approved

---

## DEC-010 — Cancellation-process source priority

**Decision:** Prioritize internal PDD/SDD rules, observed operational data,
curated technical documentation, then approved public Getnet content.

**Rationale:** Distinguish expected business rules, observed execution, expected
technical behavior, and secondary public context.

**Status:** Approved

---

## DEC-011 — Mandatory provenance

**Decision:** Preserve source, current document, chunk, logical location,
retrieval, and checksum provenance as applicable through ingestion and
retrieval.

**Rationale:** Support citations, evaluation, auditability, and source-conflict
analysis.

**Status:** Approved

---

## DEC-012 — Insufficient-evidence policy

**Decision:** Do not replace missing evidence with plausible output; return a
bounded insufficient-evidence response and offer approved human support when
appropriate.

**Rationale:** Prevent unsupported operational or process claims.

**Status:** Approved

---

## DEC-013 — Restrictive public-source allowlist

**Decision:** Ingest only explicitly approved public sources; discovered links
and new domains are never automatically trusted or ingested.

**Rationale:** Keep public evidence controlled, provenance-complete, and
subordinate to internal process rules.

**Status:** Approved

---

## DEC-014 — Tavily web-search adapter

**Decision:** Use Tavily as the initial controlled web-search provider behind a
provider-neutral application interface.

**Rationale:** Allow bounded secondary research without coupling agent logic to
a provider SDK.

**Status:** Approved

---

## DEC-015 — Separate `rag`, `ops`, and `audit` schemas

**Decision:** Separate knowledge/retrieval, operational RPA state, and security
audit concerns into conceptual database schemas.

**Rationale:** Preserve clear data ownership, access boundaries, and lifecycle
responsibilities.

**Status:** Approved concept; physical schema design is pending

---

## DEC-016 — Security audit events

**Decision:** Protected credential, secret, access, infrastructure, injection,
and bypass requests generate security audit events.

**Rationale:** Preserve policy-trigger evidence and reviewability without
inferring malicious intent.

**Status:** Approved

---

## DEC-017 — Secret redaction before audit

**Decision:** Sanitize credential-shaped content before persistence and never
store real secrets in audit logs.

**Rationale:** Audit requirements must not create a secondary secret-disclosure
channel.

**Status:** Approved

---

## DEC-018 — Project virtual environment policy

**Decision:** Execute installation, validation, and tests only with the project
virtual environment interpreter.

**Rationale:** Prevent global dependency changes and interpreter drift.

**Status:** Approved

---

## DEC-019 — RAG schema responsibility

**Decision:** The `rag` schema owns knowledge used for retrieval and grounding,
not operational RPA state or security audit events.

**Rationale:** Separate expected and documented process knowledge from observed
operational state and security auditing.

**Status:** Approved

---

## DEC-020 — Simplified RAG document lifecycle for the POC

**Decision:** Do not maintain historical document versions or
`rag.document_versions` in the POC. Store the current document representation
and optionally use its checksum to detect changes and trigger controlled
re-ingestion.

**Rationale:** The challenge requires a functional RAG pipeline but does not
require historical document-version management; omitting it avoids unnecessary
POC complexity.

**Status:** Approved

---

## DEC-021 — Internal provenance and user-facing attribution

**Decision:** Maintain detailed retrieval provenance internally while exposing
only abstract source categories to users by default.

**Rationale:** Preserve grounding, evaluation, debugging, and auditability
without disclosing internal document names, database structures, or retrieval
implementation details.

**Status:** Approved

---

## DEC-022 — Functional process data exposure

**Decision:** Authorized functional process information such as protocol,
status, dates, related files, and operational results may be returned when
relevant, while persistence and retrieval implementation details remain
internal.

**Rationale:** Functional process information supports customer and operational
work; physical storage details do not need to be exposed.

**Status:** Approved
