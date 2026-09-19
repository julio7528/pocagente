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

---

## DEC-023 — Expanded public Getnet knowledge scope

**Decision:** The Knowledge Agent's persistent public RAG supports both
specialized cancellation/corporate knowledge and official Getnet
product/service knowledge required by `docs/challenge.md`.

**Rationale:** Preserve internal cancellation expertise while satisfying the
challenge's broader grounded product and service questions.

**Status:** Approved

---

## DEC-024 — General-purpose Web Search

**Decision:** The Knowledge Agent may use controlled Web Search for current or
general external information such as weather, currency rates, news, and
prices, and for Getnet questions when approved RAG is insufficient or freshness
matters.

**Rationale:** `docs/challenge.md` explicitly requires Web Search for
general-purpose questions and includes volatile-information examples.

**Status:** Approved

---

## DEC-025 — Persistent RAG and live-search boundary

**Decision:** Web Search results are live evidence and are never automatically
persisted into RAG. Persistent ingestion requires explicit review, approval,
an exact source record, and controlled ingestion.

**Rationale:** Keep persistent knowledge governed and provenance-complete while
allowing safe use of current external information.

**Status:** Approved

---

## DEC-026 — Customer-specific operational boundary

**Decision:** Protocol, RPA execution, log, transaction, device, and observed
operational-state questions use the Customer Support Agent and controlled
customer/OPS tools rather than public Web Search.

**Rationale:** Public information cannot establish private or observed runtime
facts and must not bypass authorization boundaries.

**Status:** Approved

---

## DEC-027 — Separate challenge evaluation suite

**Decision:** Maintain `evaluation/challenge/scenarios-v1.yaml` as a separate
end-to-end challenge behavior suite, distinct from
`evaluation/rag/dataset-v1.yaml`.

**Rationale:** Routing, agent selection, capability selection, tool boundaries,
multi-agent cooperation, and security behavior require different assertions
from retrieval and grounding quality.

**Status:** Approved

---

## DEC-028 — Router multi-capability cooperation

**Decision:** The Router may sequence or coordinate specialized agents when a
request requires both documented knowledge and observed operational state.

**Rationale:** Questions such as whether a protocol is delayed require an
approved process rule from Knowledge/RAG and current state from Customer
Support/OPS.

**Status:** Approved

---

## DEC-029 — OPS schema responsibility

**Decision:** The `ops` schema represents observed operational behavior and
state and answers what actually happened in the cancellation RPA process.

**Rationale:** Keep operational truth separate from documented RAG knowledge
and security/governance auditing.

**Status:** Approved

---

## DEC-030 — Simplified domain-oriented OPS model

**Decision:** Use the six conceptual structures `ops.automation_runs`,
`ops.incoming_emails`, `ops.email_attachments`, `ops.service_requests`,
`ops.establishments`, and `ops.execution_log` instead of reproducing the
reconstructed Oracle physical schema.

**Rationale:** Model the operational facts required by the POC while avoiding
legacy physical complexity and infrastructure coupling.

**Status:** Approved

---

## DEC-031 — Incoming email as a first-class entity

**Decision:** Represent incoming email independently before protocol generation
because an email may be received and rejected without producing a protocol.

**Rationale:** Preserve the complete observable R1 intake outcome, including
pre-protocol rejection.

**Status:** Approved

---

## DEC-032 — R1 and R2 protocol responsibility

**Decision:** R1 receives the request and creates the cancellation protocol. R2
monitors and continues processing an existing protocol and does not create a
new protocol.

**Rationale:** Preserve the approved process boundary and avoid duplicating a
protocol across robot stages.

**Status:** Approved

---

## DEC-033 — Consolidated operational execution timeline

**Decision:** Use one detailed `ops.execution_log` timeline for R1/R2 events,
errors, and exceptions instead of reproducing separate Oracle-style log,
alert, and processing structures.

**Rationale:** Provide chronological investigation with fewer POC structures
while retaining optional links to the affected operational entities.

**Status:** Approved

---

## DEC-034 — R2 relationship through execution history

**Decision:** Do not store a single `r2_run_id` on
`ops.service_requests`; one protocol may be monitored by multiple R2
executions, which remain observable through execution and log history.

**Rationale:** Avoid an incorrect one-run relationship and preserve repeated
monitoring behavior.

**Status:** Approved

---

## DEC-035 — OPS data minimization for the POC

**Decision:** The current OPS model excludes email body and CC, physical
attachment paths or storage references, environment, machine telemetry, and
Oracle infrastructure-specific metadata unless a future requirement explicitly
approves them.

**Rationale:** Retain only operationally necessary information and avoid
unapproved sensitive or infrastructure-specific data.

**Status:** Approved

---

## DEC-036 — AUDIT schema responsibility

**Decision:** The `audit` schema records security and governance events and
answers what security or governance event occurred and what protective action
the system took.

**Rationale:** Keep security-control outcomes distinct from documented
knowledge and ordinary operational process state.

**Status:** Approved

---

## DEC-037 — Simplified AUDIT model

**Decision:** Use a single conceptual structure, `audit.security_events`, for
the initial POC.

**Rationale:** Support the approved security and governance requirements
without introducing unneeded audit-table complexity.

**Status:** Approved

---

## DEC-038 — Security event categories

**Decision:** `audit.security_events` must support credential requests, secret
requests, database access requests, sensitive infrastructure requests, prompt
injection, authorization bypass attempts, and security policy probes.

**Rationale:** Cover the protected-request categories defined by the internal
security policy without prematurely defining physical database enums.

**Status:** Approved

---

## DEC-039 — Secret-safe audit persistence

**Decision:** Security audit persistence stores only sanitized content and
never stores real passwords, API keys, tokens, cookies, private keys,
connection strings, credentials, secret locations, or other secret values.

**Rationale:** Preserve auditability without turning audit storage into a
secondary disclosure channel; this details and remains aligned with DEC-017.

**Status:** Approved

---

## DEC-040 — OPS and AUDIT boundary

**Decision:** Normal RPA operational logs and process state remain in OPS;
AUDIT stores only security and governance events.

**Rationale:** Keep operational investigation separate from security-control
evidence and governance review.

**Status:** Approved

---

## DEC-041 — AUDIT review metadata

**Decision:** Security events may include conceptual review metadata in
`audit.security_events` for the POC instead of introducing a separate audit
review table.

**Rationale:** Enable later governance review with a minimal conceptual model
while leaving review workflow implementation pending.

**Status:** Approved

---

## DEC-042 — Schema ownership boundary

**Decision:** RAG owns knowledge and expected behavior, OPS owns observed
operational facts, and AUDIT owns security and governance events.

**Rationale:** Preserve distinct sources of truth, access boundaries, and data
lifecycles for each conceptual domain while detailing DEC-015.

**Status:** Approved

---

## DEC-043 — No cross-domain duplication

**Decision:** RAG, OPS, and AUDIT remain separate sources of truth and do not
automatically copy or synchronize their domain data into one another.

**Rationale:** Avoid conflicting records and prevent one schema from replacing
another schema's responsibility.

**Status:** Approved

---

## DEC-044 — Multi-schema evidence composition

**Decision:** A request may use evidence from more than one schema, with
cross-domain evidence composition performed by the application and agent
layer.

**Rationale:** Support grounded expected-versus-observed comparisons without
duplicating knowledge or operational state.

**Status:** Approved

---

## DEC-045 — LLM reasoning responsibility

**Decision:** RAG and OPS provide governed evidence; the LLM interprets the
available evidence and produces the grounded user-facing conclusion.

**Rationale:** Keep storage and retrieval responsibilities separate from
interpretation while preserving grounding and insufficient-evidence rules.

**Status:** Approved

---

## DEC-046 — LangGraph orchestration responsibility

**Decision:** LangGraph is the planned orchestration layer for routing,
sequencing, handoff, state, multi-agent cooperation, and final-response flow;
it is not a persistent data store.

**Rationale:** Separate workflow coordination from governed knowledge,
operational state, and security-event persistence.

**Status:** Approved

---

## DEC-047 — AUDIT transversal boundary

**Decision:** AUDIT records a security or governance event when such an event
occurs and is not a general log of every normal request or RPA operation.

**Rationale:** Preserve focused, sanitized security evidence while ordinary
operational history remains in OPS.

**Status:** Approved

---

## DEC-048 — Generated-response persistence boundary

**Decision:** LLM-generated conclusions and responses are not automatically
persisted as RAG knowledge.

**Rationale:** Keep persistent knowledge governed; new knowledge must pass the
approved source, ingestion, and governance process.

**Status:** Approved

---

## DEC-049 — Complete conceptual schema architecture approval

**Decision:** Phase 4.1 conceptual schema architecture is approved. RAG owns governed knowledge and expected behavior, OPS owns observed operational facts and process state, and AUDIT owns security and governance events. The application and agent layer may compose evidence from multiple domains without automatically duplicating data between schemas.

The LLM interprets the governed evidence and produces the grounded user-facing conclusion, while LangGraph remains the planned orchestration layer for routing, sequencing, state, handoff, and multi-agent cooperation.

**Rationale:** The three schemas now have distinct responsibilities, clear lifecycle boundaries, and no relevant conceptual ownership overlap. The model supports the required Router Agent, Knowledge Agent, and Customer Support Agent architecture from `docs/challenge.md`, while also supporting grounding, guardrails, observability, and security auditing.

**Status:** Approved

---

## DEC-050 — Human escalation architecture

**Decision:** The POC will implement a Human Escalation Agent as a fourth
runtime product agent without replacing the mandatory Router, Knowledge, and
Customer Support agents. Human handoff occurs inside the application using the
same active conversation. Django conceptually supports `CLIENT` and
`SUPPORT_AGENT` roles, a human-support queue, conversation ownership, and the
human operator interface. User confirmation is required before transfer, and
automated agents are suspended while a human owns the conversation.

The initial POC uses HTTP polling with an initial configurable interval between
1 and 2 seconds rather than requiring WebSockets, does not implement
persistent cross-session conversational memory, and treats WhatsApp only as a
possible future channel. Only minimum authorized active-conversation context
is transferred, and physical data and API contracts remain pending.

**Rationale:** Satisfy the challenge's optional human-escalation and handoff
capability with a demonstrable, bounded application-native flow while avoiding
unnecessary WhatsApp or WebSocket complexity and preserving clear automated
and human ownership, security, and data minimization.

**Status:** Approved architecture; implementation pending

---

## DEC-051 — Detailed RAG conceptual model

**Decision:** Use `rag.sources`, `rag.documents`, `rag.chunks`, and
`rag.ingestion_runs` as the complete initial POC RAG conceptual model.

**Rationale:** Provide a structured, decoupled conceptual foundation covering
knowledge origin, current documents, retrievable units, and ingestion execution
tracking without premature physical complexity.

**Status:** Approved

---

## DEC-052 — RAG ownership relationships

**Decision:** A source may own multiple documents (`rag.sources` 1:N
`rag.documents`); a document may own multiple retrievable chunks
(`rag.documents` 1:N `rag.chunks`) and multiple ingestion execution records
(`rag.documents` 1:N `rag.ingestion_runs`).

**Rationale:** Represent natural hierarchy and lifecycle: sources provide
documents, documents are split into retrievable chunks, and ingestion attempts
on a document are logged over time.

**Status:** Approved

---

## DEC-053 — No RAG historical document/chunk versioning

**Decision:** The POC retains only the current governed document and its current
retrievable chunks and does not implement historical document versions,
`rag.document_versions`, or historical chunk versions.

**Rationale:** The POC is retrieval-focused and does not require
document-management or historical version-lifecycle complexity.

**Status:** Approved

---

## DEC-054 — Checksum reprocessing boundary

**Decision:** Use document checksum (`content_checksum`) to detect unchanged or
changed content and avoid unnecessary reprocessing; checksum does not create
historical versions. If changed, the document is reprocessed and its current
retrievable chunks are replaced in a controlled manner.

**Rationale:** Enable efficient and deterministic update and deduplication
control without retaining multiple historical versions.

**Status:** Approved

---

## DEC-055 — Chunk retrieval responsibility

**Decision:** `rag.chunks` is the principal persistent retrieval unit and
conceptually carries content, logical provenance/context, lexical
representation, and semantic embedding.

**Rationale:** Chunks are the atomic units searched by PostgreSQL Full Text
Search and pgvector, fused by RRF, and supplied as grounded evidence to the
LLM.

**Status:** Approved

---

## DEC-056 — RAG ingestion execution tracking

**Decision:** `rag.ingestion_runs` records ingestion attempts and outcomes
separately from the knowledge content itself.

**Rationale:** Keep execution tracking, status, and diagnostics observable
without polluting knowledge or operational schemas.

**Status:** Approved

---

## DEC-057 — RAG provenance chain

**Decision:** Retrieved evidence preserves conceptual provenance from chunk to
document to source (`rag.chunks` -> `rag.documents` -> `rag.sources`).

**Rationale:** Support grounding, citations, evaluation, debugging, and
auditability by linking every retrievable chunk back to its parent document and
originating source.

**Status:** Approved

---

## DEC-058 — OPS detailed conceptual model approval

**Decision:** Approve the six conceptual structures `ops.automation_runs`,
`ops.incoming_emails`, `ops.email_attachments`, `ops.service_requests`,
`ops.establishments`, and `ops.execution_log`.

**Rationale:** Establish the domain operational model for R1/R2 without
reproducing the legacy Oracle model.

**Status:** Approved

---

## DEC-059 — R1 run and email/request cardinality

**Decision:** An R1 `automation_run` has 1:N `incoming_emails`; an
`incoming_email` has 1:N `email_attachments` and 0..1 `service_request`.
If protocol creation occurs, one email corresponds to exactly one protocol.

**Rationale:** Reflect R1 batching while retaining emails that fail before a
protocol is created.

**Status:** Approved

---

## DEC-060 — Single protocol reused through R1 and R2

**Decision:** R1 creates the protocol and R2 reuses the identical protocol.
R2 never replaces it; N R2 runs may observe the same protocol; `service_requests`
has no `r2_run_id`.

**Rationale:** Preserve end-to-end identity and repeated-polling traceability.

**Status:** Approved

---

## DEC-061 — Service request ownership boundary

**Decision:** `ops.service_requests` represents the email-level protocol, not a
single attachment, and has no `attachment_id` field.

**Rationale:** One email may contain N attachments under one protocol.

**Status:** Approved

---

## DEC-062 — Establishment operational handoff

**Decision:** `ops.establishments` represents the EC/file unit and the current
state handoff from R1 to R2: R1 writes upload state, while R2 reads and updates
processing, download, and return state.

**Rationale:** Use the correct granularity for the external portal and repeated
R2 polling.

**Status:** Approved

---

## DEC-063 — Generated operational filename

**Decision:** Add `generated_file_name` to `ops.establishments`;
`email_attachments.file_name` is the raw attachment name, while
`establishments.generated_file_name` is the R1-transformed portal lookup file.

**Rationale:** Preserve traceability between raw input and the operational
portal file.

**Status:** Approved

---

## DEC-064 — OPS current state versus execution history

**Decision:** Current state belongs in `ops.establishments` and
`ops.service_requests`; immutable history belongs in `ops.execution_log`.
R2 updates state without erasing R1 history.

**Rationale:** Decouple active lifecycle state from the execution log.

**Status:** Approved

---

## DEC-065 — OPS status separation

**Decision:** `establishments.upload_status` represents R1 upload,
`establishments.download_status` represents R2 availability, and
`establishments.processing_status` represents the overall lifecycle. Technical
success is not equivalent to business result readiness; for example,
`execution_log.status` may be `SUCCESS` while `processing_status` is
`WAITING_RESULT` and `download_status` is `NOT_AVAILABLE`.

**Rationale:** Decouple technical execution from domain status.

**Status:** Approved

---

## DEC-066 — OPS complete timestamp semantics

**Decision:** `logged_at`, `started_at`, `finished_at`, `received_at`,
`processed_at`, `upload_at`, `download_at`, `completed_at`, `return_email_at`,
`created_at`, and `updated_at` represent full date-time values. SQL types are
deferred to phase 4.5.

**Rationale:** Preserve chronological fidelity without prematurely selecting SQL
types.

**Status:** Approved

---

## DEC-067 — OPS phase 4.3 approval

**Decision:** Phase 4.3 is approved and closed. OPS responsibilities, handoff,
and history are finalized. No physical OPS tables, DDL, migrations, constraints,
indexes, or SQL types are created in this phase. Advance to phase 4.4 AUDIT.

**Rationale:** Finalize conceptual facts before physical modeling.

**Status:** Approved

---

## DEC-068 — AUDIT conceptual model approval

**Decision:** Approve `audit.security_events` with the conceptual fields
`event_id`, `occurred_at`, `event_type`, `source_component`, `user_identifier`,
`request_reference`, `resource_category`, `sanitized_content`, `action_taken`,
`result`, `review_status`, `reviewed_at`, `review_note`, and `created_at`.

**Rationale:** Establish one focused conceptual structure for sanitized security
and governance evidence without physical database commitments.

**Status:** Approved

---

## DEC-069 — AUDIT resource category

**Decision:** `resource_category` identifies protected categories including
database access/credentials, API keys, passwords, access tokens, secret
locations, protected paths, authentication controls, and internal
infrastructure; real secrets and sensitive locations are never persisted.

**Rationale:** Make the protected-resource boundary explicit without database
enums or checks.

**Status:** Approved

---

## DEC-070 — AUDIT request cardinality

**Decision:** One request produces 0..N `audit.security_events` records: normal
requests produce zero, simple protected requests may produce one, and
multi-threat requests produce N records. Each record has one conceptual
`event_type`; records share `request_reference` when applicable, without arrays,
JSON collections, or junction tables.

**Rationale:** Preserve precise event granularity and request correlation.

**Status:** Approved

---

## DEC-071 — Sanitization before AUDIT persistence

**Decision:** The lifecycle is input -> detection -> sanitization/redaction ->
action -> persistence in `audit.security_events` -> safe response. Sanitized
descriptions only may be persisted; raw passwords, keys, tokens, cookies,
secrets, paths, and credentials are forbidden.

**Rationale:** Prevent audit persistence from becoming a secret-disclosure
channel.

**Status:** Approved

---

## DEC-072 — AUDIT timestamp semantics

**Decision:** `occurred_at`, `reviewed_at`, and `created_at` are full datetime
instants, with `occurred_at` representing event time and `created_at`
representing persistence time. SQL types are deferred to phase 4.5.

**Rationale:** Preserve event and persistence chronology without premature
physical modeling.

**Status:** Approved

---

## DEC-073 — AUDIT review metadata boundary

**Decision:** `review_status`, `reviewed_at`, and `review_note` are optional
conceptual metadata in `audit.security_events`; no review tables, workflows,
queues, admin UI, or physical enums are introduced in phase 4.4.

**Rationale:** Support future governance review without expanding the initial
conceptual model.

**Status:** Approved

---

## DEC-074 — AUDIT phase 4.4 approval

**Decision:** Phase 4.4 is approved and complete. AUDIT ownership, fields,
cardinality, sanitization flow, and boundaries are finalized. No physical
structures, SQL types, enums, constraints, indexes, migrations, or DDL are
created. Advance to phase 4.5 physical database modeling.

**Rationale:** Finalize conceptual AUDIT facts before physical modeling.

**Status:** Approved

---

## DEC-075 — Hybrid physical primary-key and identifier generation strategy

**Decision:** Use a hybrid physical primary-key strategy. RAG domain entities
use `UUID` when globally unique and externally transferable identifiers are
beneficial, while internal/high-volume RAG structures such as `rag.chunks` may
use `BIGINT` identity keys. OPS uses `BIGINT` identity primary keys for its
operational structures, and `audit.security_events` uses a `BIGINT` identity
primary key. Business identifiers such as `protocol_number` and
`establishment_number` remain separate from database primary keys.

PostgreSQL generates primary-key identifiers whenever possible. `BIGINT` keys
use PostgreSQL identity generation (`GENERATED ... AS IDENTITY`), with the
exact `ALWAYS` versus `BY DEFAULT` form deferred to table-level physical
specification. `UUID` keys use the PostgreSQL UUID-generation capability
selected for the final DDL. Application components must not manually
coordinate or increment primary-key values.

**Rationale:** UUIDs provide appropriate decoupling for domain entities that may
move across application boundaries, while sequential BIGINT keys improve direct
database inspection, troubleshooting, and operational traceability for OPS and
log-oriented structures. Database-side generation preserves identifier
integrity independently of application execution paths.

**Status:** Approved

---
## DEC-076 — Global PostgreSQL physical conventions

**Decision:** Approve the phase 4.5.1 global PostgreSQL physical conventions.
Every table uses a technical primary key independent from business identifiers.
DEC-075 is refined so that PostgreSQL-generated UUID keys use
`DEFAULT gen_random_uuid()` and BIGINT keys use
`GENERATED BY DEFAULT AS IDENTITY`. PK/FK columns use entity-specific names;
FK columns reuse the referenced PK name when they represent that entity directly.

Constraints use deterministic names (`pk_`, `fk_`, `uq_`, `ck_`) and indexes
use deterministic names (`idx_`, with technology-specific prefixes such as
`gin_` or `hnsw_` where useful). All physical identifiers use lowercase
`snake_case`.

All event instants use `TIMESTAMPTZ`; PostgreSQL and application runtime operate
in UTC, with local-time conversion at presentation/integration boundaries.
Timestamp columns end in `_at`. `created_at` uses `NOT NULL DEFAULT now()` where
conceptually present. `updated_at` is application-maintained only on mutable
entities; no global update trigger is introduced. Domain-event timestamps remain
distinct from persistence timestamps, and native PostgreSQL timestamp precision
is preserved.

Boolean values use PostgreSQL `BOOLEAN`. `TEXT` is the default textual type;
`VARCHAR(n)` is reserved for real domain or external-integration length limits.
Nullability represents real lifecycle states: required-at-creation values are
`NOT NULL`, while legitimate not-yet-occurred or not-applicable states may be
`NULL`. Status and small categorical fields use `TEXT + CHECK`; PostgreSQL
`ENUM` and domain lookup tables are not the default strategy for POC status
sets.

Mandatory FKs are `NOT NULL`; optional FKs are nullable. Delete behavior is
restrictive by default (`NO ACTION` / `RESTRICT`). `CASCADE` is reserved for
explicitly approved true-composition relationships, and `SET NULL` may be used
for justified historical/log references that must survive parent deletion.
Primary keys are immutable, so update behavior remains restrictive rather than
cascading key changes. Database defaults are used for deterministic technical
values and only for business/boolean/counter values with one unambiguous initial
state; otherwise the application must provide the value explicitly.

**Rationale:** Establish one consistent physical convention set before detailed
RAG, OPS, and AUDIT table modeling, improving schema readability, operational
troubleshooting, temporal consistency, integrity, and migration maintainability
without introducing premature database objects.

**Status:** Approved; phase 4.5.1 complete

---

## DEC-077 — RAG physical tables and stable document identity

**Decision:** Approve the phase 4.5.2 physical representation of
`rag.sources`, `rag.documents`, `rag.chunks`, and `rag.ingestion_runs`.
Sources use canonical stable `(origin, reference)` identity. Documents use a
stable nonblank `document_key` under `UNIQUE(source_id, document_key)`;
`title` remains mutable descriptive data. RAG domain identifiers use UUIDs,
while chunks and ingestion runs use `BIGINT GENERATED BY DEFAULT AS IDENTITY`.

**Rationale:** Preserve governed provenance and stable document replacement
without introducing document or chunk version history.

**Status:** Approved; phase 4.5.2 in force

---

## DEC-078 — RAG atomic publication and reingestion lifecycle

**Decision:** A successfully published checksum represents the bytes associated
with the last published chunk set. Unchanged usable content is recorded as
`SKIPPED_UNCHANGED` with zero chunks and leaves current chunks untouched.
Changed content or an explicit rebuild is prepared outside the publication
transaction, then current chunks, document publication metadata, and successful
run outcome are committed atomically. A single ingestion worker serializes
publication per document. Failure or zero usable chunks rolls back and leaves
previous valid chunks available; the error run is recorded after rollback.

**Rationale:** Preserve availability and prevent partially published retrieval
content while retaining execution history.

**Status:** Approved

---

## DEC-079 — RAG chunk completeness and retrieval boundary

**Decision:** `rag.chunks` is the persistent retrieval unit. Published chunks
require content, a nonnegative order, object metadata, `embedding VECTOR(N)`,
and `search_vector TSVECTOR`; an empty `TSVECTOR` is valid. FTS language,
generation, weighting, and GIN decisions remain in 4.5.4. Vector model,
dimension, normalization, metric, and index decisions remain in 4.5.3 and
4.5.5 respectively.

**Rationale:** Ensure complete hybrid retrieval units without moving model or
index decisions into the RAG table subsection.

**Status:** Approved

---

## DEC-080 — RAG ingestion lifecycle, provenance, and composite integrity

**Decision:** Ingestion runs use explicit `RUNNING`, `SUCCESS`, `ERROR`, and
`SKIPPED` states with terminal completion timestamps and committed chunk counts.
`source_id` is mandatory; optional `document_id` is linked together with
`source_id` to the matching document through a composite foreign key. Source
deletion is restrictive. Document deletion preserves run history by nulling
only `document_id`. Approved history indexes are source/time and partial
document/time; status and checksum indexes are deferred without a concrete
query.

**Rationale:** Keep ingestion provenance valid, distinguish committed output
from failed work, and avoid speculative physical indexes.

**Status:** Approved

---

## DEC-081 — RAG physical model completion

**Decision:** Phase 4.5.2 RAG Physical Model is approved and complete. The
approved specification covers columns, types, nullability, defaults, keys,
foreign keys, checks, uniqueness, deletion behavior, lifecycle publication,
retrieval completeness, and justified indexes. Phase 4.5.3 Final FastEmbed
Model is the current next subsection; phase 4.5 remains incomplete.

**Rationale:** Close the table-level RAG physical design before selecting the
embedding model and vector dimension.

**Status:** Approved; phase 4.5.2 complete

---

## DEC-082 — Final FastEmbed embedding configuration

**Decision:** Approve FastEmbed `0.8.0` with
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` as the final
POC embedding model. It runs through ONNX Runtime on local CPU, with GPU
optional, produces 384-dimensional embeddings, and is stored as `VECTOR(384)`.
FastEmbed mean pooling is retained and no additional manual normalization is
applied. No external embedding API or credential is used.

`intfloat/multilingual-e5-small` is superseded as the active candidate.
Embeddings from E5, earlier sentence-transformers runtime configurations, or
any incompatible model, dimension, pooling, normalization, or semantic-input
configuration require full re-embedding and must not be mixed with the
approved representation.

**Rationale:** Cached-run local CPU validation confirmed the model is suitable
for the POC while preserving a multilingual, provider-independent embedding
path. The validation confirmed a 384-dimensional output and adequate cached-run
throughput; initial download/load time is not treated as steady-state latency.

**Status:** Approved

---

## DEC-083 — FastEmbed phase 4.5.3 completion

**Decision:** Phase 4.5.3 is approved and complete. `VECTOR(384)` resolves the
earlier `VECTOR(N)` placeholder. FTS configuration remains for phase 4.5.4;
vector distance metric, vector indexes, their parameters, and semantic query
implementation remain for phase 4.5.5. Phase 4.5 remains incomplete.

**Rationale:** Finalize the embedding representation before selecting FTS or
pgvector query/index behavior.

**Status:** Approved; phase 4.5.3 complete

---

## DEC-084 — Dual PostgreSQL FTS configuration and generation

**Decision:** Use standard PostgreSQL `portuguese` and `simple` text-search
configurations. `portuguese` serves stemming, morphology, and business rules;
`simple` serves exact technical identifiers, acronyms, and field names. The
application controls generation through native `to_tsvector(...)`; Python
stemming, database triggers, generated columns, custom parsers, thesauri, and
synonym configurations are not used.

**Rationale:** Support Portuguese business language and exact technical terms
without introducing custom FTS infrastructure in the POC.

**Status:** Approved

---

## DEC-085 — RAG FTS inputs and weight hierarchy

**Decision:** Generate `rag.chunks.search_vector` from
`rag.documents.title`, `rag.chunks.section`, and `rag.chunks.content` only.
Assign PostgreSQL weights `A` to title, `B` to section, `C` to Portuguese
content, and `D` to technical/exact text processed with `simple`. Keys, FKs,
checksums, statuses, timestamps, embeddings, metadata JSONB, and operational
fields are excluded. Positions are retained.

**Rationale:** Prioritize document and section context while preserving
technical identifier matching and term proximity.

**Status:** Approved

---

## DEC-086 — RAG lexical query, ranking, and candidate boundary

**Decision:** Parse user input with native
`websearch_to_tsquery('portuguese', user_query)` combined with
`websearch_to_tsquery('simple', user_query)`; raw `to_tsquery()` is forbidden
for user input. Rank lexical candidates with `ts_rank_cd`. Retrieve at most 10
lexical candidates, combine with at most 10 semantic candidates through RRF,
and produce final Top-K 5 without an ML reranker. Candidates require active
source and document statuses.

**Rationale:** Provide safe web-style lexical parsing, positional ranking, and a
bounded hybrid retrieval contract.

**Status:** Approved

---

## DEC-087 — Planned RAG FTS GIN index

**Decision:** Plan the GIN index `gin_chunks__search_vector` on
`rag.chunks.search_vector`. FTS preparation occurs before atomic publication,
and title, section, or content changes regenerate affected search vectors. The
index remains planned only; no DDL, migration, index creation, or database
object is created in phase 4.5.4.

**Rationale:** Establish the intended lexical access path while preserving the
documentation-only and no-premature-index boundary.

**Status:** Approved; index planned only

---

## DEC-088 — PostgreSQL FTS phase 4.5.4 completion

**Decision:** Phase 4.5.4 PostgreSQL Full Text Search is approved and complete.
`rag.chunks.search_vector` is `TSVECTOR NOT NULL` for published chunks, with
the approved dual configuration, application-controlled native generation,
inputs, weights, parser, ranking, active filters, and candidate limits. Advance
to phase 4.5.5 pgvector Physical Model. Vector metric and pgvector index
decisions remain deferred.

**Rationale:** Close the lexical physical model without deciding semantic
vector operations reserved for 4.5.5.

**Status:** Approved; phase 4.5.4 complete

---

## DEC-089 — pgvector cosine metric

**Decision:** Use cosine distance as the initial semantic metric, through the
pgvector `<=>` operator, ordered ascending so lower distance means higher
similarity. Inner product and L2 distance are not used, and metric selection
is not dynamic. The raw distance is not converted into a user-facing
percentage or normalized score.

**Rationale:** Keep the approved `VECTOR(384)` representation and semantic
ranking contract explicit without mixing incompatible score scales.

**Status:** Approved

---

## DEC-090 — Exact pgvector search and future ANN preference

**Decision:** The initial POC uses exact nearest-neighbor scanning with no
active vector ANN index. If benchmarks later require ANN, evaluate HNSW before
IVFFlat. The HNSW reference baseline is `vector_cosine_ops`, `m=16`,
`ef_construction=64`, and `ef_search=40`; it is not active, validated, or
implemented now.

**Rationale:** Preserve full recall and avoid premature index tuning at the
current POC volume.

**Status:** Approved; no index created

---

## DEC-091 — Semantic candidate boundary and active filtering

**Decision:** Semantic retrieval applies `source.status = 'ACTIVE'` and
`document.status = 'ACTIVE'`, orders by cosine distance ascending, and returns
at most 10 semantic candidates.

**Rationale:** Restrict retrieval to governed active content and keep the
hybrid candidate set bounded.

**Status:** Approved

---

## DEC-092 — Rank fusion and retrieval snapshot consistency

**Decision:** Hybrid retrieval combines lexical and semantic rank positions 1
through 10 with Reciprocal Rank Fusion (RRF). Raw scores are not combined or
normalized across channels, and no ML reranker is introduced. Lexical,
semantic, and provenance retrieval for one request observes one consistent
committed chunk set through a single statement/CTE or a read-only
`REPEATABLE READ` transaction.

**Rationale:** Make cross-channel ranking deterministic without pretending
that lexical and vector distances share a score scale, while preventing
provenance drift within one request.

**Status:** Approved

---

## DEC-093 — pgvector phase 4.5.5 completion

**Decision:** Phase 4.5.5 pgvector Physical Model is approved and complete.
It establishes `VECTOR(384)`, cosine `<=>`, exact search with no active ANN
index, the active-content filter, semantic Top 10, rank-based RRF, and
snapshot consistency. Phase 4.5.6 OPS Physical Model is the next subsection;
phase 4.5 remains incomplete.

**Rationale:** Close the semantic physical-model decisions while deferring
database object creation and executable retrieval implementation.

**Status:** Approved; phase 4.5.5 complete

---

## DEC-094 — OPS physical table models and identity strategy

**Decision:** Approve the physical models for
`ops.automation_runs`, `ops.incoming_emails`, `ops.email_attachments`,
`ops.service_requests`, `ops.establishments`, and `ops.execution_log`.
Each table uses a `BIGINT GENERATED BY DEFAULT AS IDENTITY` technical primary
key. Instants use `TIMESTAMPTZ`; statuses and categories use `TEXT` with
checks; deterministic defaults, nullability, restrictive FKs, and planned
indexes follow the approved PostgreSQL conventions.

**Rationale:** Establish the six-table OPS physical boundary without
reproducing the legacy Oracle schema or creating database objects.

**Status:** Approved

---

## DEC-095 — OPS run, email, and attachment lifecycle

**Decision:** An automation run identifies `R1` or `R2` and has many incoming
emails. Each incoming email has many attachments and retains its own
pre-protocol lifecycle, sender validation, processing status, and counts. No
email deduplication key or `external_message_id` is invented. Planned indexes
are documentation only.

**Rationale:** Preserve R1 batching and failed-before-protocol intake without
introducing an unsupported integration identity.

**Status:** Approved

---

## DEC-096 — OPS protocol cardinality and provenance

**Decision:** An incoming email creates zero or one service request, enforced
by unique `service_requests.email_id`; `protocol_number` is a unique business
ID. The request provenance uses the composite FK
`(email_id, r1_run_id) -> incoming_emails(email_id, run_id)` with restrictive
deletion. `service_requests` contains neither `attachment_id` nor `r2_run_id`.

**Rationale:** One email owns one protocol across all its attachments, while
the same protocol may be observed by multiple R2 runs.

**Status:** Approved

---

## DEC-097 — Establishment identity and R1-to-R2 handoff

**Decision:** `ops.establishments` is the operational handoff unit between R1
and R2. It references both the service request and source attachment, stores
`establishment_number` as TEXT to preserve leading zeros, and stores R1's
`generated_file_name`. Approve unique keys on
`(request_id, attachment_id, establishment_number)` and
`(request_id, generated_file_name)`. Do not add redundant `email_id`.

**Rationale:** Preserve EC/file identity and provide a stable protocol-plus-file
lookup for repeated R2 processing.

**Status:** Approved

---

## DEC-098 — OPS execution-log retention and optional references

**Decision:** `ops.execution_log` is the chronological history of normal R1/R2
operations, failures, and timeouts, distinct from AUDIT security events. Its
run anchor is mandatory through the composite FK `(run_id, robot)`, while
email, attachment, request, and establishment references are optional and use
`ON DELETE SET NULL` to preserve historical log rows. Messages are sanitized.

**Rationale:** Keep operational history durable without making every event
depend on a child entity or moving RPA logs into AUDIT.

**Status:** Approved

---

## DEC-099 — OPS phase 4.5.6 completion

**Decision:** Phase 4.5.6 OPS Physical Model is approved and complete. The six
table models, lifecycle/status rules, email/request cardinality, composite
provenance FKs, establishment handoff, execution-log retention, and planned
indexes are documented. Phase 4.5.7 AUDIT Physical Model is the next
subsection; phase 4.5 remains incomplete and no database object is created.

**Rationale:** Close the OPS physical model while preserving the documentation-
only boundary and deferring physical implementation to phase 4.6.

**Status:** Approved; phase 4.5.6 complete

---

## DEC-100 — AUDIT security-events physical model

**Decision:** Approve `audit.security_events` as the single AUDIT physical
table with a BIGINT identity PK, application-supplied `occurred_at`, separate
`created_at`, TEXT + CHECK categories, nullable opaque request/user/resource
correlation, sanitized content, protective action/result, and optional review
metadata. `request_reference` is non-unique correlation text, not an FK. One
request may produce zero to many events.

Sanitization occurs before persistence. No raw secrets, tokens, keys,
credentials, dumps, or protected payloads are stored; no trigger/procedure
performs secret scanning, and no review table, workflow, queue implementation,
or admin UI is introduced.

**Rationale:** Preserve sanitized security/governance evidence without turning
AUDIT into general logging or coupling it to application request storage.

**Status:** Approved; phase 4.5.7 complete

---

## DEC-101 — Cross-schema physical index inventory

**Decision:** Approve the named index inventory documented in
`docs/database-physical-model.md`: 7 RAG, 18 OPS, and 4 AUDIT non-PK access
paths, including constraint-backed unique indexes. PostgreSQL FTS uses the
planned GIN index; semantic retrieval initially has no vector ANN index.
Partial indexes cover nullable document/request/establishment references and
unreviewed AUDIT events. Speculative checksum, source classification/status,
email content, and broad AUDIT categorical indexes are rejected.

**Rationale:** Tie every planned access path to a concrete identity, history,
queue, lookup, or investigation use case while avoiding duplicate or
speculative indexes.

**Status:** Approved; phase 4.5.8 complete; indexes planned only

---

## DEC-102 — Cross-schema constraints and integrity

**Decision:** Approve deterministic names and integrity rules for PKs, FKs,
UNIQUE constraints, CHECK constraints, and defaults across RAG, OPS, and
AUDIT. Mandatory FKs are NOT NULL and restrictive by default; nullable
historical references use targeted SET NULL. The sole approved cascade is
`rag.documents -> rag.chunks`. Composite FKs preserve RAG ingestion and OPS
run/email provenance. Technical PKs are immutable with `ON UPDATE RESTRICT`.

Checks enforce governed categories, nonblank required text, nonnegative counts,
timestamp lifecycle consistency, RAG chunk completeness, and sanitized AUDIT
review state. They do not implement cross-table email-chain validation,
deduplication, or secret scanning.

**Rationale:** Enforce durable row-level and relational invariants without
triggers, duplicated keys, or application-specific logic hidden in the DB.

**Status:** Approved; phase 4.5.9 complete

---

## DEC-103 — Lifecycle-driven nullability

**Decision:** Approve the cross-schema nullability matrix. Mandatory identity,
ownership, content, status, and persistence fields are NOT NULL. Nullable
fields represent legitimate states such as pre-publication checksum, active
run, unresolved document, unknown count, not-yet-uploaded/downloaded/completed,
optional operational correlation, absent safe AUDIT content, or unreviewed
security event. Empty strings do not substitute for null.

**Rationale:** Model partial lifecycle states explicitly without weakening
mandatory provenance or forcing fabricated values.

**Status:** Approved; phase 4.5.10 complete

---

## DEC-104 — Delete, retention, and cascade boundaries

**Decision:** Use `ON DELETE RESTRICT` for normal RAG and OPS ownership,
`ON DELETE CASCADE` only for `rag.documents -> rag.chunks`, and `ON DELETE SET
NULL` for ingestion/execution-log references that must survive parent deletion.
Normal withdrawal uses status rather than routine physical deletion. AUDIT has
no automatic TTL or arbitrary 30/90/365-day purge and is retained until an
authorized administrative action.

**Rationale:** Preserve provenance and operational/security history while
allowing composition cleanup only where the child has no independent meaning.

**Status:** Approved; phase 4.5.11 complete

---

## DEC-105 — Physical-model transition to performance and volume

**Decision:** Phases 4.5.7 through 4.5.11 are approved and complete. The
current next subsection is 4.5.12 Performance and POC Volume. Phase 4.5 remains
incomplete, and no schema, table, index, DDL, migration, trigger, procedure,
ORM model, repository, or runtime code is created by these decisions.

**Rationale:** Close the AUDIT, index, integrity, nullability, and retention
designs before validating POC volume and performance assumptions.

**Status:** Approved; advance to phase 4.5.12

---

## DEC-106 — R1 ownership boundary for incoming emails

**Decision:** Clarify that `ops.incoming_emails` contains R1 intake records;
R2 cannot own incoming emails. Its mandatory `run_id` remains a foreign key to
`ops.automation_runs.run_id ON DELETE RESTRICT`, which guarantees referenced
run existence only and does not enforce `robot = 'R1'`. R1-only ownership is
currently an application invariant pending the 4.5.9 integrity evaluation.
No redundant `robot` column and no trigger are introduced.

**Rationale:** Preserve the approved OPS model while distinguishing relational
existence integrity from the cross-column robot-role invariant.

**Status:** Clarification recorded; 4.5.9 evaluation pending

---

## DEC-107 — Proportional POC performance and volume

**Decision:** Approve 4.5.12 planning ranges in the physical specification as
order-of-magnitude assumptions, not capacity limits, SLAs, measured production
volume, or certified retrieval latency. Retain exact cosine Top 10, the
approved 29 query access paths, unindexed complementary JSONB, and no
partitioning, sharding, materialized views, CQRS, event sourcing, or automatic
archival. HNSW requires representative workload latency and recall evidence
against exact search; row count alone is insufficient.

**Rationale:** Measure first, optimize second; preserve a proportional POC.

**Status:** Approved; 4.5.12 complete

---

## DEC-108 — Physical field security and minimization

**Decision:** Approve the 4.5.13 review of all 11 table models. The anti-secret
rule applies to every field, including free text, references, filenames and
JSONB. RAG is governed knowledge; OPS retains necessary operational data with
sanitized messages and filenames only; AUDIT persists sanitized evidence and
uses NULL when safe content cannot be produced. No email body/CC/path,
credential-bearing dumps, scanning triggers/procedures, production IAM,
GRANT/RLS, Vault, or credential-rotation architecture is introduced.

**Rationale:** Field flexibility never grants permission to persist secrets.
Enforcement implementation remains future work.

**Status:** Approved; 4.5.13 complete

---

## DEC-109 — Final eleven-table physical specification

**Decision:** Approve the consolidated 4.5.14 specification and documentation
authority in 4.5.15. Preserve exactly four RAG, six OPS and one AUDIT table;
hybrid PKs; 14 FKs; 10 UNIQUE constraints; status/check/default/nullability
rules; timestamps; FTS; FastEmbed; exact cosine; RRF; deletion and retention.
Table sections remain the single authoritative column definitions.

DEC-106's open wording is resolved: R1-only incoming-email intake remains
application-enforced. The FK verifies run existence only. No redundant robot
column, trigger, or FK change is approved.

The 29-entry query inventory is unchanged (7 RAG, 18 OPS, 4 AUDIT). Counting
all future non-PK backing indexes additionally includes the two already
approved OPS composite-FK target UNIQUEs, giving 31; these are not new indexes
or constraints. This clarifies the earlier shorthand counts in DEC-101.

**Rationale:** Consolidate approved decisions with explicit enforcement and
accounting boundaries, without creating physical objects or duplicating models.

**Status:** Approved; 4.5.14 and 4.5.15 complete

---

## DEC-110 — Phase 4.5 completion and transition to physical creation

**Decision:** The 4.5.16 documentation gate passed after checking all 11
table models and 119 fields, hybrid PKs, 14 FKs, 10 UNIQUEs, lifecycle checks,
nullability, timestamp/status strategy, approved query paths, retrieval,
security and conceptual ownership. Phase 4.5 is COMPLETED / APPROVED.
The next phase is 4.6 — CRIAR TABELAS / DDL / MIGRATIONS.

The 29-query-path inventory and the 31 total future non-PK backing-index
count are distinguished as clarified in DEC-109. Performance ranges are
planning assumptions, not measured retrieval guarantees. Application R1-only
validation remains the final approved boundary, resolving DEC-106's pending
wording without changing its historical record.

**Rationale:** Close the conceptual-to-physical documentation chain only after
the final gate; reserve all physical implementation for phase 4.6 and later.

**Status:** Approved; phase 4.5 complete; phase 4.6 current, not implemented.
No schema, table, DDL, migration, index, trigger, procedure, ORM, repository,
runtime logic, Docker/.env change, commit or push was produced by this task.

---

## DEC-111 — Native PostgreSQL SQL migration strategy

**Decision:** Approve native PostgreSQL SQL migration files as the Phase 4.6
migration engine. Files use sequential numeric names such as
`0001_<desc>.sql`, `0002_<desc>.sql`; applied migrations are immutable and
evolve only through new files. The scope is structural only: schemas, tables,
columns, constraints, indexes, and approved Phase 4.5 physical specifications.
Migrations contain zero business or operational data; production data copying is
forbidden, synthetic POC seed is deferred to Phase 4.9, and later data enters
through runtime inserts. Seed runs once and is not automatically reapplied to a
populated database. Rollback is explicit and controlled, not automated.

Alembic and SQLAlchemy are excluded from Phase 4.6; no Python database
dependencies are introduced. Migration execution is decoupled from FastAPI,
repositories, agents, and application startup; no automatic migration runs on
boot. The strategy preserves all approved Phase 4.5 decisions.

**Rationale:** Keep the migration boundary explicit, dependency-free, auditable,
and proportional to the approved physical design.

**Status:** Approved; Phase 4.6.1 complete; Phase 4.6 incomplete.

---

## DEC-112 — Initial SQL migration structure and deterministic execution order

**Decision:** Approve exactly six sequential native PostgreSQL SQL migration
files for the initial database construction, executed in order:

1. `database/migrations/0001_prerequisites_and_schemas.sql` — PostgreSQL
   prerequisites and the `rag`, `ops`, and `audit` schemas; pgvector creation
   versus verification remains deferred to 4.6.3.
2. `database/migrations/0002_rag_tables.sql` — RAG tables in dependency order:
   `rag.sources`, `rag.documents`, `rag.chunks`, `rag.ingestion_runs`.
3. `database/migrations/0003_ops_tables.sql` — OPS tables in dependency order:
   `ops.automation_runs`, `ops.incoming_emails`, `ops.email_attachments`,
   `ops.service_requests`, `ops.establishments`, `ops.execution_log`.
4. `database/migrations/0004_audit_table.sql` — the independent
   `audit.security_events` table, with no external foreign keys.
5. `database/migrations/0005_constraints.sql` — the ten UNIQUE constraints,
   approved CHECK constraints, fourteen foreign keys and delete/update rules.
   The order is UNIQUE, CHECK, simple foreign keys, then composite foreign
   keys, including the approved composite-FK target keys.
6. `database/migrations/0006_indexes.sql` — the 21 explicit non-UNIQUE access
   indexes, including the planned `gin_chunks__search_vector`; UNIQUE-backed
   indexes are not duplicated. No ANN, JSONB GIN, or speculative indexes are
   included.

Primary keys, NOT NULL requirements, and deterministic defaults are placed in
the table-creation migrations. The six files are the complete initial
construction boundary: the database may be structurally incomplete between
files, and seed, runtime inserts, and ingestion are allowed only after 0006 is
applied. Migrations contain zero business or synthetic data; production data
copying remains forbidden and synthetic seed remains deferred to Phase 4.9.
Rollback remains explicit and manual under 4.6.9. The structure preserves all
approved Phase 4.5 physical-model decisions and does not constitute physical
implementation in this documentation task.

**Rationale:** A deterministic dependency order keeps initial construction
auditable, avoids duplicate UNIQUE indexes, and makes the structural boundary
explicit without introducing runtime or migration-tool complexity.

**Status:** Approved; Phase 4.6.2 complete; Phase 4.6.3 current; Phase 4.6
incomplete.

---

## DEC-113 — Migration structure approval: placement and execution boundaries

**Decision:** Reaffirm DEC-112 and its exact six-file sequence under
`database/migrations/`: `0001_prerequisites_and_schemas.sql` ->
`0002_rag_tables.sql` -> `0003_ops_tables.sql` -> `0004_audit_table.sql` ->
`0005_constraints.sql` -> `0006_indexes.sql`. The responsibilities and RAG/OPS
table dependency orders recorded in DEC-112 remain unchanged.

Table creation in 0002–0004 owns columns, PostgreSQL types, PKs, approved
UUID/identity generation, both nullable and NOT NULL definitions, and defaults.
0005 owns all 10 UNIQUEs, approved CHECKs, and 14 FKs, including approved
ON DELETE actions and ON UPDATE RESTRICT. Its strict order is UNIQUE -> CHECK
-> simple FKs -> composite FKs. These UNIQUE targets must precede their
dependent composite FKs:

- `rag.documents(document_id, source_id)` for
  `rag.ingestion_runs(document_id, source_id)`;
- `ops.automation_runs(run_id, robot)` for `ops.execution_log(run_id, robot)`;
- `ops.incoming_emails(email_id, run_id)` for
  `ops.service_requests(email_id, r1_run_id)`.

The approved accounting is 29 query access paths and 31 future non-PK backing
indexes: 10 UNIQUE-backed plus 21 explicit indexes assigned to 0006. Verify the
exact inventory against `docs/database-physical-model.md` during 4.6.8.
0006 includes `gin_chunks__search_vector` on `rag.chunks.search_vector` and
does not duplicate PK/UNIQUE backing indexes. ANN (HNSW/IVFFlat), JSONB GIN,
speculative indexes, FTS triggers, generated FTS columns, and global timestamp
triggers remain excluded.

The database is structurally ready only after all six migrations succeed.
Application runtime, repositories, seed, ingestion, and operational processes
must not depend on intermediate construction states. Migrations contain no
synthetic, business, operational, or RAG corpus data. Synthetic seed belongs to
4.9; production data is forbidden. Explicit manual rollback implementation
remains deferred to 4.6.9. The pgvector creation-versus-verification decision
remains deferred to 4.6.3. All Phase 4.5 physical decisions and the native SQL
strategy from DEC-111 are preserved.

**Rationale:** Make the approved placement, index accounting, and readiness
conditions explicit without rewriting DEC-112 or advancing implementation.

**Status:** Approved; 4.6.2 complete; 4.6.3 current; Phase 4.6 incomplete.
No directory, SQL migration file, or database object was created by this task.
