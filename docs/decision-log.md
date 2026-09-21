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

---

## DEC-114 — PostgreSQL prerequisites and application schema creation

**Decision:** Create and execute `database/migrations/0001_prerequisites_and_schemas.sql`
as the sole Phase 4.6.3 migration. It validates PostgreSQL major version 17,
uses `CREATE EXTENSION IF NOT EXISTS vector`, validates pgvector 0.8.6 and the
available vector type, and fails closed on incompatible versions without
automatic upgrade or downgrade. No `pgcrypto`, `uuid-ossp`, other extension,
custom IAM, RLS, tables, indexes, triggers, procedures, or data are introduced.
Exactly the `rag`, `ops`, and `audit` schemas are created without
`IF NOT EXISTS`.

The migration executed successfully through PostgreSQL MCP against the local
Getnet Support POC database. Read-only validation confirmed PostgreSQL 17,
pgvector 0.8.6, vector type availability, the three schemas, zero application
tables, zero application indexes, and no application data insertion.
Phase 4.6.3 is complete; 4.6.4 is current.

**Rationale:** Establish only the approved physical foundation while keeping
table creation, indexes, IAM, runtime migration application, and seed data in
their separately approved phases.

**Status:** Approved; Phase 4.6.3 complete; Phase 4.6.4 current; Phase 4.6
incomplete.

---

## DEC-115 — RAG physical tables materialized

**Decision:** Create and execute `database/migrations/0002_rag_tables.sql`
from the authoritative `docs/database-physical-model.md`. In the order
sources -> documents -> chunks -> ingestion_runs, it materializes exactly the
four approved RAG tables: UUID PKs for sources/documents; BIGINT `BY DEFAULT`
identity PKs for chunks/ingestion runs; JSONB only for chunk metadata;
VECTOR(384); TSVECTOR; and the approved TIMESTAMPTZ, nullability, and defaults.
Stable current-document identity, provenance columns, and ingestion lifecycle
fields are retained; version-history structures are not introduced.

FK, business UNIQUE, and CHECK enforcement remain assigned to 0005; explicit
application and GIN indexes remain assigned to 0006. No ANN/HNSW/IVFFlat,
trigger, timestamp automation, function, procedure, view, or application data
was introduced. Atomic document replacement remains a runtime responsibility.
The migration succeeded through the authorized PostgreSQL MCP RW profile, and
RO catalog validation confirmed the four 10-column tables, all approved PKs,
types, nullability, defaults, and absence of premature objects. Phase 4.6.4 is
complete; Phase 4.6.5 is current.

**Rationale:** Materialize the approved RAG foundation without advancing
integrity, indexing, runtime, or data responsibilities into this migration.

**Status:** Approved; Phase 4.6.4 complete; Phase 4.6.5 current; Phase 4.6
incomplete.

---

## DEC-116 — OPS physical tables materialized

**Decision:** Create and execute `database/migrations/0003_ops_tables.sql`
from the authoritative `docs/database-physical-model.md`. In the approved
order, it materializes the six OPS tables with 65 validated columns, BIGINT
`BY DEFAULT` identity PKs, and approved types, nullability, and defaults.
R1/R2 provenance is retained; service requests retain `email_id` and
`r1_run_id` without `attachment_id` or `r2_run_id`; establishments retain
request/attachment/business-number/generated-filename handoff data without
redundant `email_id`; execution logs retain optional entity correlations.

FK, business UNIQUE, and CHECK rules remain assigned to 0005; explicit and
partial indexes remain assigned to 0006. No trigger, other premature object,
or application data was introduced. The migration executed through the
controlled local PostgreSQL MCP RW profile; RO catalog validation confirmed
the physical result. RO remains the default MCP inspection mode, while RW is
limited to explicitly approved local POC migrations. Phase 4.6.5 is complete;
Phase 4.6.6 is current.

**Rationale:** Materialize the approved OPS foundation without advancing
integrity, indexing, runtime, or data responsibilities into this migration.

**Status:** Approved; Phase 4.6.5 complete; Phase 4.6.6 current; Phase 4.6
incomplete.

---

## DEC-117 — AUDIT security-events table materialized

**Decision:** Create and execute `database/migrations/0004_audit_table.sql`
from the authoritative `docs/database-physical-model.md`. It materializes
`audit.security_events` with 14 validated columns, a BIGINT `BY DEFAULT`
identity `pk_security_events`, and approved TIMESTAMPTZ, nullability, and
defaults. `request_reference` remains nullable TEXT correlation only, with no
external AUDIT FK or business UNIQUE.

CHECK rules remain assigned to 0005 and explicit indexes to 0006. No trigger,
procedure, function, auxiliary review table, raw secret/payload storage, TTL,
automatic retention, or application data was introduced. The migration
executed through controlled PostgreSQL MCP RW access; RO catalog validation
confirmed the physical result and all 11 approved application tables. Phase
4.6.6 is complete; Phase 4.6.7 is current.

**Rationale:** Materialize the approved sanitized AUDIT evidence structure
without advancing integrity, indexing, retention, runtime, or data work.

**Status:** Approved; Phase 4.6.6 complete; Phase 4.6.7 current; Phase 4.6
incomplete.

---

## DEC-118 — Physical constraints and integrity materialized

**Decision:** Create and execute `database/migrations/0005_constraints.sql`
from the authoritative `docs/database-physical-model.md`. It materializes
the 10 approved UNIQUE constraints, 14 FKs, and approved RAG/OPS/AUDIT CHECK
invariants. Composite UNIQUE targets precede dependent FKs; PostgreSQL created
the associated UNIQUE backing indexes automatically.

All FKs use ON UPDATE RESTRICT. The sole CASCADE is
`rag.documents -> rag.chunks`; ingestion document deletion sets only
`document_id` to NULL while retaining `source_id`; and optional
`ops.execution_log` entity references use SET NULL. Mandatory ownership and
provenance references use RESTRICT; AUDIT remains without an FK. Application-
enforced invariants remain outside SQL. No trigger, explicit 4.6.8 access-path
index, ENUM, or application data was introduced. The migration executed
through controlled RW MCP and was structurally validated through RO MCP.
Phase 4.6.7 is complete; Phase 4.6.8 is current.

**Rationale:** Add the approved integrity boundary without advancing indexing,
runtime, or seed-data responsibilities into this migration.

**Status:** Approved; Phase 4.6.7 complete; Phase 4.6.8 current; Phase 4.6
incomplete.

---

## DEC-119 — Approved access-path indexes materialized

**Decision:** Create and execute `database/migrations/0006_indexes.sql` from
the authoritative `docs/database-physical-model.md`. It materializes exactly
21 explicit indexes: 3 RAG, 14 OPS, and 4 AUDIT. The FTS access path
`gin_chunks__search_vector` uses GIN, and the five approved partial-index
predicates are preserved.

The 10 UNIQUE-backed and 11 PK-backed indexes remain present without
duplication. The approved query-access-path inventory remains 29, with 31
non-PK backing indexes and 42 application indexes in total. No vector ANN,
HNSW, IVFFlat, JSONB GIN, speculative index, trigger, function, procedure,
view, or application data was introduced. The migration executed through the
controlled PostgreSQL MCP RW profile and structural validation completed
through the RO profile. Phase 4.6.8 is complete; Phase 4.6.9 is current.

**Rationale:** Materialize only the approved access paths while retaining the
POC's exact vector-search strategy and avoiding premature optimization.

**Status:** Approved; Phase 4.6.8 complete; Phase 4.6.9 current; Phase 4.6
incomplete.

---

## DEC-120 — Migration execution, transaction, and manual rollback policy

**Decision:** Retain the initial forward sequence as exactly six immutable
migrations, `0001` through `0006`, executed numerically and independently in
their explicit transactions. Execution stops on the first failure. Existing or
unknown-COMMIT state requires PostgreSQL catalog inspection before retry; no
Alembic or migration metadata table is introduced, and application startup
does not execute migrations.

Create `database/rollback/rollback_initial_schema.sql` as the explicit manual
rollback artifact. It is destructive, refuses populated application tables,
reverses the approved indexes, constraints, tables, and schemas by name, uses
no CASCADE, and intentionally preserves pgvector. The rollback script was
created and structurally validated, not destructively executed. A controlled
MCP RW temporary-transaction rollback smoke test succeeded; RO validation
confirmed that the live database remained unchanged. Phase 4.6.9 is complete;
Phase 4.6.10 is current.

**Rationale:** Establish deterministic recovery behavior without changing the
approved physical model or risking the local POC database.

**Status:** Approved; Phase 4.6.9 complete; Phase 4.6.10 current; Phase 4.6
incomplete.

---

## DEC-121 — Local migration chain rebuild verified

**Decision:** Exercise the approved local rebuild for Phase 4.6.10. All 11
application tables were confirmed empty before the approved rollback artifact
was executed through controlled PostgreSQL MCP RW access. The rollback removed
the application schemas and preserved pgvector; no data deletion or production
data access occurred.

The immutable migrations `0001` through `0006` were then reapplied in strict
order, with RO validation before advancing after every migration. The approved
schemas, tables, constraints, indexes, VECTOR(384), TSVECTOR, and FTS GIN
access path were reconstructed with no seed/application data and no new
forward migration. Phase 4.6.10 is complete; Phase 4.6.11 is current.

**Rationale:** Demonstrate reproducibility of the local POC physical build
from its versioned artifacts without replacing the subsequent exact structural
audit.

**Status:** Approved; Phase 4.6.10 complete; Phase 4.6.11 current; Phase 4.6
incomplete.

---

## DEC-122 — Phase 4.6 physical database implementation completed and validated

**Decision:** Final RO PostgreSQL catalog validation (4.6.11) matches
`docs/database-physical-model.md`: PostgreSQL 17 with pgvector 0.8.6; the
three approved schemas; 11 tables; and 119 approved fields. The hybrid key
strategy is materialized as 2 UUID PKs and 9 BIGINT `BY DEFAULT` identity PKs,
with 10 non-PK UNIQUE constraints, 14 FKs, 59 CHECK constraints, and approved
nullability, defaults, and delete/update behavior.

The validated index accounting is 21 explicit indexes, 31 non-PK backing
indexes, 42 total application indexes, and 29 approved query access paths.
`VECTOR(384)`, TSVECTOR, and the FTS GIN access path are present. No ANN,
HNSW, IVFFlat, JSONB GIN, PostgreSQL ENUM, application trigger, procedure,
function, unapproved relation, seed data, or production data exists. The six
native migrations are present and applied; the manual rollback artifact exists;
no new migration was required. Documentation was synchronized under 4.6.12
and the 4.6.13 completion gate passed.

**Rationale:** Close the verified physical implementation without changing the
authoritative model or expanding into runtime/database-dependency work.

**Status:** Approved; Phase 4.6.11, 4.6.12, and 4.6.13 complete; Phase 4.6
complete; Phase 4.7 current.

---

## DEC-123 — Python database access requirements approved

**Decision:** Formally approve the technical requirements for the Python
database access layer under Phase 4.7.1:

1. **Runtime & Engine Compatibility:** PostgreSQL-native access targetting
   PostgreSQL 17 with pgvector 0.8.6. Full compatibility with Python 3.14 runtime
   environment. Asynchronous database access designed specifically for the
   FastAPI async runtime.
2. **Execution & Transaction Integrity:** All queries must execute via
   parameterized SQL to guarantee injection safety. Explicit transaction support
   (atomic blocks with commit and rollback) across multi-step repository
   operations. Schema-qualified SQL referencing explicit database schemas
   (`rag`, `ops`, `audit`). Explicit PostgreSQL-native SQL approved.
3. **Data Types & Feature Support:** Native engine-level handling for all
   approved physical schema types: UUID (RFC 4122 strings/objects), BIGINT
   (identity primary keys), TIMESTAMPTZ (timezone-aware UTC datetimes), JSONB
   (structured dictionary metadata and payloads), TSVECTOR (full-text search
   vectors), and VECTOR(384) (dense embeddings). Full support for PostgreSQL
   native Full Text Search (`portuguese` dictionary tsquery/tsvector) and
   pgvector similarity distance operations (`<=>` cosine distance).
4. **Tooling & Migration Decoupling:** Runtime database interaction is strictly
   isolated from migration lifecycle. Database migrations remain external native
   PostgreSQL SQL files (Alembic excluded). MCP servers remain developer and
   diagnostic inspection tooling only. No driver selection or package installation
   is performed in this step (deferred to Phase 4.7.3+).

**Rationale:** Establish formal baseline technical requirements for the database
layer before selecting drivers or evaluating libraries, ensuring strict alignment
with the validated physical model and Python 3.14 / FastAPI runtime without
premature dependency decisions.

**Status:** Approved; Phase 4.7.1 complete; Phase 4.7.2 complete; Phase 4.7.3
current.

---

## DEC-124 — PostgreSQL-native repository access strategy approved

**Decision:** Formally approve the PostgreSQL-native database access strategy
under Phase 4.7.2:

1. **Persistence Boundary:** Repository pattern (`RAGRepository`,
   `OperationalRepository`, `AuditRepository`) serves as the strict architectural
   boundary between business/agent services and database persistence. No domain
   or routing logic leaks into queries, and no raw database queries exist
   outside repositories.
2. **Application & Domain Data Models:** Pydantic models serve directly as the
   application and domain models across the system. An ORM is not mandatory;
   avoiding full ORM abstraction eliminates impedance mismatch with
   specialized PostgreSQL types and avoids unnecessary overhead.
3. **Query Strategy:** Explicit, parameterized PostgreSQL SQL statements inside
   repository implementations. Allows full, unconstrained use of PostgreSQL-native
   capabilities, including pgvector cosine distance (`<=>`), Portuguese FTS
   (`websearch_to_tsquery`), schema qualification, and hybrid key handling.
4. **Concurrency & Lifecycle:** Asynchronous-first (async-first) execution model
   with centralized, connection-pool-capable connection lifecycle compatible with
   FastAPI lifespan and dependency injection.
5. **Migrations & Tooling Invariants:** Database migrations remain external,
   sequential native PostgreSQL SQL files executed out-of-band; Alembic is
   excluded. MCP tools remain external diagnostic/development utilities only,
   not runtime dependencies. Driver selection and package installation are
   deferred to Phase 4.7.3+.

**Rationale:** Maintain a lightweight, high-performance, async-native data
boundary centered on Pydantic domain models and the Repository pattern, avoiding
the friction and overhead of heavy ORMs while fully supporting PostgreSQL 17,
pgvector, and FTS capabilities.

**Status:** Approved; Phase 4.7.2 complete; Phase 4.7.3 current; Phase 4.7
incomplete.

---

## DEC-125 — Psycopg 3 binary async driver approved

**Decision:** Formally approve Psycopg 3 (`psycopg` package) with `psycopg[binary]`
installation mode as the PostgreSQL database driver under Phase 4.7.3:

1. **Driver Selection:** Psycopg 3 (`psycopg` package) is approved as the
   PostgreSQL driver. `psycopg2` is legacy and strictly excluded due to lack
   of native asyncio support.
2. **Installation Mode:** `psycopg[binary]` (self-contained binary package
   including precompiled `libpq`) is approved. It avoids any requirement for
   local C compilers, build tools, or system `libpq` installations on Windows
   and target environments. `psycopg[c]` and pure-Python modes are excluded.
3. **Extras & Scope:** No extras added now. Specifically, `psycopg[pool]` is
   deferred to a later runtime/lifecycle step.
4. **Runtime Concurrency Model:** Native asynchronous model using
   `AsyncConnection` and `AsyncCursor` natively integrated with FastAPI's
   asyncio event loop. Synchronous connections and blocking execution are
   excluded.
5. **Environment & Engine Compatibility:** Fully compatible with Python 3.14,
   PostgreSQL 17, and the local Windows development environment.
6. **Ecosystem & Lifecycle Boundaries:**
   - SQLAlchemy: Undecided, evaluation deferred to Phase 4.7.4; premature
     adoption or exclusion is avoided.
   - Alembic: Excluded; migrations remain external sequential native PostgreSQL
     SQL files.
   - Dependencies & Packaging: Zero edits to `pyproject.toml` and zero package
     installations at this step; package pinning and installation are deferred
     to Phase 4.7.6.

**Rationale:** Psycopg 3 provides native asyncio (`AsyncConnection` /
`AsyncCursor`), native PostgreSQL 17 support, verified compatibility with
Python 3.14 on Windows, and zero requirement for local `libpq` or build
tooling via `psycopg[binary]`.

**Status:** Approved; Phase 4.7.3 complete; Phase 4.7.4 current; Phase 4.7
incomplete.

---

## DEC-126 — SQLAlchemy evaluated and excluded from runtime architecture

**Decision:** Formally evaluate and intentionally exclude SQLAlchemy from the
POC runtime architecture under Phase 4.7.4:

1. **SQLAlchemy Exclusion:** SQLAlchemy is not required and is not added as a
   dependency. Neither SQLAlchemy ORM, SQLAlchemy Core, nor
   `AsyncEngine`/`AsyncSession` are adopted.
2. **Approved Runtime Pipeline:** The runtime architecture flow is confirmed as:
   `FastAPI/App -> Services -> Repositories -> Psycopg 3 -> PostgreSQL 17`.
3. **Database Access & Concurrency Model:** PostgreSQL-native, async-first
   execution using explicit, parameterized SQL queries executed directly
   through Psycopg 3 (`AsyncConnection` / `AsyncCursor`).
4. **Native Capabilities Without Abstraction:** Direct engine-level utilization
   of PostgreSQL capabilities—Full Text Search (`portuguese` dictionary),
   `TSVECTOR`, `JSONB`, pgvector similarity (`<=>`), and `VECTOR(384)`—without
   ORM mapping overhead or intermediary abstraction layers.
5. **Domain & Application Models:** Pydantic models remain the application and
   domain models throughout services and repositories.
6. **Migrations & Invariants:** Database migrations remain external, sequential
   native PostgreSQL SQL files executed out-of-band; Alembic is excluded.
   Reconsideration of SQLAlchemy will occur only if a concrete, compelling
   architectural requirement emerges in a future phase.

**Rationale:** Introducing SQLAlchemy would add an unnecessary layer of
abstraction, complexity, and performance overhead without tangible benefits for
the POC's focused Repository architecture, Pydantic domain models, and
specialized PostgreSQL 17 / pgvector / FTS access patterns. Direct async Psycopg 3
access satisfies all technical and functional requirements cleanly.

**Status:** Approved; Phase 4.7.4 complete; Phase 4.7.5 current; Phase 4.7
incomplete.

---

## DEC-127 — Python integration with pgvector approved

**Decision:** Formally approve the Python integration strategy for pgvector
under Phase 4.7.5:

1. **Adapter Package:** The official `pgvector` Python package is approved.
   Manual serialization/deserialization methods (e.g., via `TEXT`, `JSON`,
   `JSONB`, or `BYTEA`) are strictly excluded.
2. **Integration Module:** `pgvector.psycopg` is approved for direct native
   integration with Psycopg 3. Adapters for SQLAlchemy, psycopg2, or asyncpg
   are excluded.
3. **Connection Registration:** Registration is executed via
   `register_vector_async()` called once upon physical database connection
   initialization. The application never creates or manages the extension;
   `CREATE EXTENSION IF NOT EXISTS vector` remains strictly owned by external
   native SQL migrations.
4. **Lifecycle & Pooling Boundary:** Connection-level registration hooks
   compatible with future connection pooling are permitted in Phase 4.8;
   no connection pool is implemented or introduced at this step.
5. **Vector Target & Dimension:** Strict alignment with the physical schema
   specification: target column `rag.chunks.embedding` defined as `VECTOR(384)`
   with exactly 384 dimensions matching the approved FastEmbed model.
   Arbitrary `VECTOR(N)` and non-384 dimensions are excluded.
6. **Search Metric & Distance Operator:** Cosine distance using the native
   operator `<=>` with exact nearest-neighbor search. HNSW, IVFFlat, and
   approximate nearest neighbor (ANN) indexes remain excluded.
7. **Adapter Scope & Responsibilities:** `pgvector` serves exclusively as a
   binary/text type adapter for vector casting. It does not own repository
   boundaries, SQL generation, database migrations, connection pooling,
   candidate ranking, or business logic.
8. **Dependencies & Pinning:** Zero edits to `pyproject.toml` and zero package
   installations at this step; dependency specification, version pinning, and
   installation are deferred to Phase 4.7.6+.

**Rationale:** `pgvector.psycopg` provides clean, transparent, async-native
type conversion between Python lists/numpy arrays and PostgreSQL `VECTOR(384)`
over Psycopg 3 connections without manual serialization or ORM dependencies,
strictly adhering to the validated physical database model and exact cosine
distance search requirements.

**Status:** Approved; Phase 4.7.5 complete; Phase 4.7.6 current; Phase 4.7
incomplete.

---

## DEC-128 — Python database dependency set and exact version pins approved

**Decision:** Formally approve the Python database dependency set and exact
version-pinning policy under Phase 4.7.6:

1. **Approved Dependency Specifications:**
   - `psycopg[binary]==3.3.6`: PostgreSQL-native driver with self-contained
     binary precompiled `libpq`. Provides native async execution, explicit
     transactions, and parameterized SQL for Python 3.14 on Windows without
     local build tooling prerequisites.
   - `pgvector==0.5.0`: Official Python adapter for PostgreSQL `VECTOR` types,
     enabling native type conversion and direct integration via `pgvector.psycopg`.
2. **Exact Version Pinning Policy:** Strict exact `==` version pinning is
   mandated in `pyproject.toml` for all runtime database dependencies to
   guarantee reproducible environments and prevent silent runtime/driver drift.
3. **Excluded & Forbidden Alternatives:**
   - `SQLAlchemy`: Excluded (unnecessary abstraction; Pydantic models and
     repositories handle data access natively).
   - `Alembic`: Excluded (migrations remain external native PostgreSQL SQL files).
   - `psycopg2`: Excluded (legacy driver without native asyncio support).
   - `asyncpg`: Excluded (unapproved driver; incompatible with Psycopg 3 ecosystem).
   - `psycopg[c]`: Excluded (source compilation requires local C/libpq toolchain).
   - `psycopg[pool]` / `psycopg_pool`: Excluded at this stage (connection
     pooling evaluated/deferred to Phase 4.8).
   - `numpy`: Excluded from database dependencies (not added solely for pgvector
     unless an independent application requirement emerges).
4. **Execution Boundary:** Zero edits to `pyproject.toml` are performed in
   this decision (deferred to Phase 4.7.7); dependency installation in the
   virtual environment is deferred to Phase 4.7.8.

**Rationale:** Exact pinning of `psycopg[binary]==3.3.6` and `pgvector==0.5.0`
secures a minimal, robust, async-first database stack for Python 3.14 on
Windows without native C build friction or unneeded ORM/migration dependencies.

**Status:** Approved; Phase 4.7.6 complete; Phase 4.7.7 current; Phase 4.7
incomplete.

---

## DEC-129 — Database dependencies declared in pyproject.toml

**Decision:** Formally record the addition of approved Python database
dependencies to `pyproject.toml` under Phase 4.7.7:

1. **Declared Dependencies:** Appended `psycopg[binary]==3.3.6` and
   `pgvector==0.5.0` to the `[project].dependencies` array with strict exact
   `==` version pins.
2. **Preservation of Existing State:** Preserved all pre-existing project
   dependencies (`fastapi==0.141.1`, `pydantic==2.13.5`, `uvicorn==0.53.0`,
   `fastembed==0.8.0`, `PyYAML==6.0.3`, `httpx==0.28.1`), optional dev
   dependencies (`pytest==8.4.2`), and python requirement `requires-python = ">=3.14"`.
3. **Syntax Validation:** Successfully validated `pyproject.toml` TOML syntax
   via Python's standard `tomllib` parser.
4. **Exclusions Maintained:** No unapproved dependencies (SQLAlchemy, Alembic,
   psycopg2, asyncpg, `psycopg[c]`, `psycopg[pool]`, `numpy`) were added.
5. **Execution Boundary:** Zero packages installed in the virtual environment
   during this step; installation and editable re-install validation are
   deferred to Phase 4.7.8.

**Rationale:** Maintain declarative configuration integrity by explicitly
manifesting approved database dependencies and exact version pins in
`pyproject.toml` before modifying the runtime virtual environment.

**Status:** Approved; Phase 4.7.7 complete; Phase 4.7.8 current; Phase 4.7
incomplete.

---

## DEC-130 — Python database dependencies installed in active environment

**Decision:** Formally record the installation and verification of approved
database dependencies in the active virtual environment under Phase 4.7.8:

1. **Environment & Installation Execution:** Executed `python -m pip install -e .`
   within the active project virtual environment (`F:\My Drive\dev\pocagente\.venv`)
   from `F:\My Drive\dev\pocagente\getnet-support`.
2. **Installed Package Specifications Confirmed:**
   - `psycopg==3.3.6`: Core PostgreSQL-native driver.
   - `psycopg-binary==3.3.6`: Precompiled binary wheel providing bundled `libpq`.
   - `pgvector==0.5.0`: Python adapter for PostgreSQL `VECTOR` types.
   - `tzdata==2026.4`: Transitive dependency for PostgreSQL timezone support.
   - `getnet-support==0.1.0`: Project root installed in editable mode (`-e .`).
3. **Confirmed Absence of Excluded Dependencies:** Verified zero instances of
   SQLAlchemy, Alembic, psycopg2, asyncpg, `psycopg[c]`, `psycopg[pool]`/`psycopg_pool`,
   or unneeded extra packages in the active virtual environment.
4. **Execution Boundary:** No database queries, migrations, or application code
   modifications were performed. Import verification and runtime compatibility
   checks are deferred to Phase 4.7.9.

**Rationale:** Fulfill the declarative dependencies defined in `pyproject.toml`
by providing verified, reproducible runtime packages within the designated
virtual environment, maintaining exact versions and zero unapproved dependencies.

**Status:** Approved; Phase 4.7.8 complete; Phase 4.7.9 current; Phase 4.7
incomplete.

---

## DEC-131 — Python database dependency stack validated

**Decision:** Formally validate and approve the Python database dependency stack,
closing Phase 4.7 (`4.7.9`, `4.7.10`, `4.7.11`):

1. **Validation Gates Completed:**
   - Active Python interpreter confirmed in `F:\My Drive\dev\pocagente\.venv`.
   - Python version `>=3.14` confirmed (`3.14.2`).
   - Declarative dependencies in `pyproject.toml` verified with exact pins
     `psycopg[binary]==3.3.6` and `pgvector==0.5.0`.
   - Package metadata and environment confirmed: `psycopg==3.3.6`,
     `psycopg-binary==3.3.6`, `pgvector==0.5.0`, `tzdata==2026.4`, and editable
     `getnet-support==0.1.0`.
   - `python -m pip check` passed with zero broken requirements.
   - Core imports verified: `import psycopg`, `from psycopg import AsyncConnection`,
     `import pgvector`, `from pgvector.psycopg import register_vector_async`.
   - Attribute validation: `psycopg.__version__ == "3.3.6"`, `pgvector` package
     metadata matches `"0.5.0"`, `AsyncConnection` is available, and
     `register_vector_async` is callable.
   - Application compilation check passed cleanly (`python -m compileall apps`).
2. **Approved Final Dependency Architecture:**
   - Psycopg 3 with `psycopg[binary]` self-contained installation.
   - `pgvector` official Python adapter with `pgvector.psycopg` integration.
   - Async-first access model using native `AsyncConnection` and `AsyncCursor`.
   - Explicit parameterized PostgreSQL SQL; Pydantic models as domain models.
   - Repository pattern persistence boundary planned for Phase 4.8 (`RAGRepository`,
     `OperationalRepository`, `AuditRepository`).
3. **Invariants & Exclusions Reaffirmed:**
   - SQLAlchemy remains intentionally excluded from runtime architecture.
   - Alembic remains excluded; migrations remain external sequential native
     PostgreSQL SQL files decoupled from application startup.
   - `psycopg2`, `asyncpg`, `psycopg[c]`, `psycopg[pool]`, and unneeded dependencies
     remain excluded from the environment.
   - Zero database objects, migrations, or runtime query implementations were
     modified or introduced.

**Rationale:** The Python database dependency stack is fully installed, validated,
and import-tested under Python 3.14 on Windows, satisfying all 11 completion
criteria of Phase 4.7 without introducing unnecessary ORM or migration complexity.

**Status:** Approved; Phase 4.7 complete; Phase 4.8 current.

---

## DEC-132 — Customer Support OPS tools and diagnostic-to-human escalation approved

**Decision:** Approve the runtime tool contracts for the Customer Support Agent,
the operational fact vs. diagnostic inference boundary, the diagnostic-to-human
escalation flow, minimum handoff context, and the challenge scenario suite update:

1. **Approved Customer Support OPS Tools:**
   - `lookup_protocol_status(protocol_number: str)`: Queries observed operational
     state, timestamps, and status history across `ops.service_requests`,
     `ops.establishments`, and `ops.execution_log`. Returns structured operational
     facts only; does not infer undocumented business rules.
   - `inspect_execution_failure(protocol_number: str, run_id: Optional[str] = None)`:
     Queries chronological execution logs, stage of failure, last successful stage,
     and sanitized error messages across `ops.execution_log` and `ops.automation_runs`.
     Returns structured operational failure facts only; does not fabricate root causes.
2. **Fact vs. Diagnostic Inference Boundary:**
   - OPS tools are deterministic query interfaces returning verified operational
     evidence from PostgreSQL `ops` tables.
   - The Customer Support Agent reasons over observed operational facts and
     curated process rules (from RAG) to produce grounded probable root-cause
     diagnoses, maintaining strict separation between verified FACT and probabilistic
     INFERENCE.
3. **Diagnostic-to-Human Escalation Workflow:**
   - Step 1: Explain diagnosis and supporting evidence clearly to the user.
   - Step 2: Explicitly offer human escalation for support-ticket opening and handling.
   - Step 3: Require explicit user confirmation before initiating handoff.
   - Step 4: Route to the Human Escalation Agent upon user confirmation.
   - Step 5: Transition conversation state to the human handoff queue (e.g. `WAITING_HUMAN`).
   - Step 6: Transfer only the minimum necessary diagnostic context to the authorized
     human operator.
   - Step 7: Ticket opening and handling is performed by the human operator in the
     initial POC (no automatic AI ticketing; no external ITSM integration).
   - Step 8: Ensure automated agent responses remain suspended while under human ownership.
4. **Minimum Handoff Context & Exclusions:**
   - Transferred context includes: protocol identifier, user problem summary,
     current operational state, run identifier (if applicable), last successful
     stage, observed failure stage, sanitized error message, timeline trace,
     labeled diagnosis/probable cause, and user confirmation record.
   - Strictly excludes: secrets, credentials, passwords, tokens, API keys, DB
     connection strings, raw un-sanitized stack traces, and cross-session memory.
5. **Challenge Scenario Suite:**
   - `evaluation/challenge/scenarios-v1.yaml` updated from 13 to 14 scenarios.
   - `challenge-011` and `challenge-012` explicitly expect `lookup_protocol_status`.
   - `challenge-014` added to validate end-to-end failure diagnosis, explicit user
     confirmation, minimum context handoff, and automation suspension.

**Rationale:** Define clear, grounded tool contracts for customer support operations
and a secure, human-in-the-loop escalation pathway that protects credentials and
avoids premature ITSM automation, while keeping Phase 4.8 as the current roadmap step.

**Status:** Approved; Phase 4.8 current.

---

## DEC-133 — Database access layer architecture approved

**Decision:** Formally approve the architecture, component structure, and operational
rules for the Python database access layer (Phase 4.8.1):

1. **Approved Architecture Pipeline:**
   `FastAPI / Agents -> Application Services -> Repositories -> Central Database Infrastructure -> Psycopg 3 + pgvector adapter -> PostgreSQL 17`

2. **Approved Future Structure under `apps/agent_api/app/database/`:**
   - `config.py`: database configuration and connection settings;
   - `connection.py`: centralized connection lifecycle, pool acquisition, and transaction infrastructure;
   - `vector.py`: centralized pgvector adapter registration on physical connections;
   - `errors.py`: safe database exception abstraction and translation;
   - `mapping.py`: raw database row/record mapping to Python/Pydantic domain models;
   - `repositories/rag.py`: RAG schema persistence (`rag.sources`, `rag.documents`, `rag.chunks`);
   - `repositories/operational.py`: OPS schema persistence (`ops.automation_runs`, `ops.incoming_emails`, `ops.email_attachments`, `ops.service_requests`, `ops.establishments`, `ops.execution_log`);
   - `repositories/audit.py`: AUDIT schema persistence (`audit.security_events`).

3. **Core Architectural Invariants and Rules:**
   - **Strict Repository Boundary:** Repositories form the exclusive persistence boundary; agents, API endpoints, tools, and application services must never execute raw database SQL directly.
   - **Customer Support Tool Isolation:** Customer Support tools consume application services backed by `OperationalRepository`, never querying PostgreSQL directly.
   - **Async-First Execution:** Runtime database access is purely async-first using native Psycopg 3 (`AsyncConnection`, `AsyncCursor`).
   - **Explicit Native Parameterized SQL:** SQL queries remain explicit, parameterized, native to PostgreSQL, and schema-qualified (`rag.*`, `ops.*`, `audit.*`).
   - **Centralized Lifecycle & Pool-Readiness:** Infrastructure connection acquisition is centralized; repositories borrow connections and do not independently instantiate or close connections.
   - **Composable Transactions:** Transaction boundaries support multiple repository operations across schemas within one atomic unit of work; repository methods must not enforce independent commits when a broader transaction is required.
   - **Centralized pgvector Registration:** `register_vector_async` is registered once per physical connection lifecycle and must not be repeated in individual repository queries.
   - **Pydantic Domain Models:** Models remain Pydantic-based without ORM integration.
   - **Strict Exclusions Reaffirmed:** SQLAlchemy, Alembic, psycopg2, and asyncpg remain excluded. Migrations remain external native PostgreSQL SQL scripts never executed on application startup.
   - **PostgreSQL MCP Role:** MCP database tools remain external developer/diagnostic utilities only.
   - **Import Safety:** No connection or pool creation may occur as a module-import side effect.
   - **Deferred Pooling:** The concrete connection pool implementation remains intentionally deferred to Phase 4.8.3.

4. **Scope Boundary:** This decision represents architectural and structural approval only. No runtime database access files, database objects, migrations, or live database connections were created during this step.

**Rationale:** Provide a clean, robust, and maintainable data access architecture that decouples database mechanics and SQL persistence from domain and agent logic, enabling composable transactions, async concurrency, and type-safe mappings without ORM overhead.

**Status:** Approved; Phase 4.8.1 complete; Phase 4.8.2 current; Phase 4.8 in progress.

---

## DEC-134 — Database connection configuration and environment mapping approved

**Decision:** Formally approve the database connection configuration schema, environment
variable naming, validation rules, and default values (Phase 4.8.2):

1. **Approved Environment Variable Family:**
   Reuse the existing PostgreSQL environment variables without introducing a duplicate `DATABASE_URL`:
   - `POSTGRES_HOST`: Database host address (default: `127.0.0.1`).
   - `POSTGRES_PORT`: Database port (default: `5432`).
   - `POSTGRES_DB`: Database name (default: `getnet_support`).
   - `POSTGRES_USER`: Application database user (default: `getnet_app`).
   - `POSTGRES_PASSWORD`: Database password supplied through environment configuration. For the current local POC, `.env.example` may temporarily contain the owner-approved local configuration value; `.env` remains the runtime source of truth. Real production or non-POC credentials must not be committed or externally distributed.
   - `POSTGRES_SSLMODE`: SSL connection mode (default: `disable` for local POC).
   - `POSTGRES_CONNECT_TIMEOUT_SECONDS`: Physical connection timeout in seconds (default: `5`).
   - `POSTGRES_POOL_MIN_SIZE`: Minimum idle connection pool size (default: `1`).
   - `POSTGRES_POOL_MAX_SIZE`: Maximum total connection pool size (default: `5`).
   - `POSTGRES_POOL_TIMEOUT_SECONDS`: Pool connection acquisition timeout in seconds (default: `5`).

2. **Configuration & Security Rules:**
   - **Secret Protection:** `.env` is the Git-ignored runtime configuration source; `.env.example` is reference material only. Owner-approved local values may temporarily remain in `.env.example` for this POC, but this exception does not extend to production, non-POC, shared, or externally distributed repository state, which must use non-secret placeholders and never expose real credentials. Runtime code must never hardcode the password, and it must never be logged, printed, copied into documentation, or returned by application responses.
   - **Rejection of `DATABASE_URL`:** A single concatenated URI string is rejected to avoid credential exposure and parsing ambiguities. Connection parameters must be passed to Psycopg as structured keyword arguments.
   - **Validation Scope:** Configuration model validates host, port, database name, user, password presence, SSL mode, timeouts, and consistency between min and max pool sizes.
   - **Dependency Boundary:** No new `pydantic-settings` dependency is approved; configuration will be implemented using existing Pydantic models with explicit environment variable loading.
   - **Containerization Portability:** Local host execution uses `127.0.0.1:5432`; future containerized application execution requires changing only `POSTGRES_HOST` (e.g. to `postgres`), preserving the application architecture.

3. **Scope Boundary:** Architectural approval only. No runtime configuration code or database connections were created.

**Rationale:** Maintain consistency with `docker-compose.yml`, prevent credential exposure, and provide structured, type-safe configuration without adding unapproved dependencies.

**Status:** Approved; Phase 4.8.2 complete; Phase 4.8.3 current.

---

## DEC-135 — Database connection lifecycle and AsyncConnectionPool approved

**Decision:** Formally approve the connection pool technology, lifecycle orchestration,
sizing, and integration hooks for the Python database access layer (Phase 4.8.3):

1. **Pool Implementation & Approved Dependency:**
   - **Pool Technology:** `psycopg_pool.AsyncConnectionPool` is approved as the standard connection pool.
   - **Approved Dependency:** `psycopg-pool==3.3.2` is approved as an upcoming Phase 4.8 runtime infrastructure dependency. Installation and validation are owned by Phase 4.8.4; it is not installed in the active environment during this documentation step.
   - **Preserved Existing Dependencies:** `psycopg[binary]==3.3.6` and `pgvector==0.5.0` remain unchanged.

2. **Pool Sizing & Acquisition Parameters:**
   - `min_size = 1`: Keeps one warm connection available.
   - `max_size = 5`: Conservative pool cap for local POC development.
   - Acquisition timeout = 5 seconds (`POSTGRES_POOL_TIMEOUT_SECONDS`).
   - Constructed with `open=False` to prevent connection creation at import time.

3. **Application Lifecycle Orchestration:**
   - **Lifespan Startup:** Explicitly execute `await pool.open()` during FastAPI lifespan startup.
   - **Readiness Gate:** Verify pool readiness before declaring database-dependent endpoints ready; fails closed if PostgreSQL connections cannot be established.
   - **Lifespan Shutdown:** Explicitly execute `await pool.close()` during application shutdown to gracefully terminate physical connections.

4. **Connection Acquisition & Repository Pattern:**
   - **Singleton Infrastructure:** Exactly one pool instance per FastAPI process.
   - **Borrow Pattern:** Repositories borrow connections using `async with pool.connection() as conn`.
   - **Prohibited Patterns:** Manual `getconn()/putconn()` is prohibited as standard application access. Independent pool or connection creation by repositories is prohibited.
   - **Import Safety:** No connection or pool creation may occur as a module-import side effect.

5. **Multi-Worker & Transaction Budgeting:**
   - PostgreSQL connection budget must account for `workers × max_size` when multi-worker deployments are introduced. Speculative pool enlargement is prohibited.
   - Composable multi-repository operations within one atomic transaction are supported using a single borrowed connection (Phase 4.8.10).

6. **Connection Initialization Hook for pgvector:**
   - The pool `configure` async callback is designated as the integration point for Phase 4.8.5, ensuring `register_vector_async(conn)` is called once per newly opened physical connection.

7. **Scope Boundary:** Architectural and lifecycle approval only. Zero runtime code, database connections, package installations, or database modifications were performed.

**Rationale:** Leverage Psycopg 3's native asyncio pool to guarantee safe, non-blocking connection management, clean lifespan integration, and deterministic pgvector registration without ORM complexity.

**Status:** Approved; Phase 4.8.3 complete; Phase 4.8.4 current; Phase 4.8 in progress.

---

## DEC-136 — Central PostgreSQL connection component implemented

**Decision:** Implement `PostgresDatabase` as the centralized PostgreSQL
runtime infrastructure. Each instance owns one validated `DatabaseConfig` and
one `psycopg_pool.AsyncConnectionPool`, constructed from structured Psycopg
keyword arguments with `open=False`. Its explicit asynchronous lifecycle is
`open()` followed by pool readiness `wait()`, connection borrowing through
`async with database.connection()`, and `close()`.

Construction and module import perform no PostgreSQL network I/O and create no
global database or pool singleton. Repositories will borrow connections from
this component and must not create or manage independent pools. The component
does not build a credential-bearing URI, execute SQL, or add SQLAlchemy/Alembic
abstractions. Pgvector physical-connection registration is deferred to Phase
4.8.5, explicit transaction abstraction to Phase 4.8.10, and real PostgreSQL
connection validation to Phase 4.8.13.

Validation passed with `psycopg-pool==3.3.2`, 37 focused/full tests, application
compilation, import checks, and no real database connection. The approved
project virtual environment has no broken requirements; the known external
Google ADK/FastAPI conflict in the global Python environment is unrelated and
was not changed.

**Rationale:** Establish one explicit, testable pool lifecycle boundary before
adding per-connection pgvector configuration or repository behavior.

**Status:** Approved; Phase 4.8.4 complete; Phase 4.8.5 current; Phase 4.8 in
progress.

---

## DEC-137 — Pgvector physical-connection lifecycle integration implemented

**Decision:** Centralize Psycopg pgvector adapter setup in
`apps/agent_api/app/database/vector.py`. Its asynchronous
`configure_pgvector_connection()` callback invokes the official
`register_vector_async(connection)` adapter exactly once for each pool
configuration invocation. `PostgresDatabase` supplies this callback through
`AsyncConnectionPool.configure`, so every newly created physical connection is
configured before becoming available to repositories.

Because adapter registration performs PostgreSQL type-discovery queries, the
callback executes `rollback()` afterward to return the fresh connection
transaction-clean. Registration remains fail-closed: cleanup is attempted when
registration fails, the registration failure propagates, and it remains the
reported error even if cleanup also fails. There is no global or per-query
adapter registration, and logical pool checkouts do not repeat registration.

No extension creation, DDL, application SQL, repository, transaction
abstraction, pool/connection import side effect, or real PostgreSQL connection
validation was introduced. Validation used the approved virtual environment:
5 pgvector callback tests and 43 combined/full tests passed; dependency checks,
application/test compilation, and imports also passed. Real database validation
remains Phase 4.8.13.

**Rationale:** Configure pgvector once at the physical-connection boundary,
before repository use, while preserving clean transaction state and explicit
failure behavior.

**Status:** Approved; Phase 4.8.5 complete; Phase 4.8.6 current; Phase 4.8 in
progress.

---

## DEC-138 — Repository contracts and connection-bound persistence boundaries approved

**Decision:** Establish exactly three async-first repository domains:
`RAGRepository`, `OperationalRepository`, and `AuditRepository`.
`RAGRepository` exclusively owns the four approved `rag` tables;
`OperationalRepository` exclusively owns the six approved `ops` tables; and
`AuditRepository` exclusively owns `audit.security_events`, preserving the
approved total of 11 application tables.

Repositories are lightweight connection-bound persistence adapters. Each
concrete repository receives an existing `psycopg.AsyncConnection` through
dependency injection. A repository creates no pool or connection, owns no
`PostgresDatabase`, does not close the injected connection, does not call
`commit()` or `rollback()`, and establishes no independent transaction
boundary. This permits multiple repositories to share one physical connection
and one atomic transaction under the future Phase 4.8.10 transaction boundary.

Agents, endpoints, controlled tools, and application services never receive a
generic raw-SQL repository interface. Each repository accesses only its owned
schema and tables; cross-domain composition occurs above repositories in the
application-service layer. `OperationalRepository` returns deterministic facts
and failure evidence, while Customer Support application services and agents
retain responsibility for interpretation and probable root-cause reasoning.
`AuditRepository` accepts only already-sanitized security and governance event
data and must never become a general application log or secret-persistence
channel.

Concrete RAG SQL is deferred to Phase 4.8.7, OPS SQL to Phase 4.8.8, AUDIT SQL
to Phase 4.8.9, transaction orchestration to Phase 4.8.10, row mapping to Phase
4.8.11, database error translation to Phase 4.8.12, and real PostgreSQL
validation to Phase 4.8.13.

Validation used the approved Python 3.14.2 virtual environment: 13 repository
tests, 43 database tests, and all 56 project tests passed; repository imports
and `compileall apps tests` passed; `pip check` reported no broken requirements;
and the approved dependency versions remained unchanged. No real PostgreSQL
connection was opened and no SQL was executed.

**Rationale:** Preserve strict domain ownership and enable future atomic,
multi-repository operations without leaking pool, transaction, or raw-SQL
responsibilities into repositories or higher application layers.

**Status:** Approved; Phase 4.8.6 complete; Phase 4.8.7 current; Phase 4.8 in
progress.

---

## DEC-139 — RAGRepository concrete PostgreSQL persistence and retrieval implemented

**Decision:** Implement connection-bound `RAGRepository` over only
`rag.sources`, `rag.documents`, `rag.chunks`, and `rag.ingestion_runs`, using
parameterized, schema-qualified Psycopg SQL. It implements governed source and
current-document persistence, stable `(source_id, document_key)` identity,
checksum-aware change detection, complete non-empty chunk replacement, and the
approved ingestion-run lifecycle.

Lexical retrieval uses the approved combined standard PostgreSQL FTS query,
`ts_rank_cd`, and `rag.chunks.search_vector`. Semantic retrieval uses exact
cosine distance through `<=>`, with no HNSW or IVFFlat. Both paths require
ACTIVE source and document state and return bounded, provenance-bearing
records. Because the current `SearchCandidate` model cannot faithfully express
the physical row without prematurely implementing mapping, both retrieval
contracts return `Sequence[RepositoryRecord]` until Phase 4.8.11.

The repository owns no transaction and performs no commit, rollback, RRF, or
grounding. Mock-based validation passed with 19 focused RAG tests, 62 combined
repository tests, 43 database tests, and 105 full-suite tests; no real database
connection was opened.

**Status:** Approved; Phase 4.8.7 complete.

---

## DEC-140 — OperationalRepository concrete PostgreSQL persistence and operational evidence queries implemented

**Decision:** Implement connection-bound `OperationalRepository` over exactly
the six approved OPS tables using parameterized, schema-qualified SQL. It
provides strict operational create/update boundaries, protocol lookup,
deterministic establishment handling across both approved UNIQUE identities,
append-only execution logs, bounded execution timelines, protocol-status
facts, and execution-failure evidence.

The repository returns observed facts and sanitized evidence only. It performs
no diagnosis, probable root-cause inference, escalation, or handoff. It creates
no connection or pool and owns no transaction, commit, or rollback.
Mock-based validation passed with 19 focused OPS tests, 62 combined repository
tests, 43 database tests, and 105 full-suite tests.

**Status:** Approved; Phase 4.8.8 complete.

---

## DEC-141 — AuditRepository concrete sanitized security-event persistence implemented

**Decision:** Implement connection-bound `AuditRepository` over only
`audit.security_events`. Parameterized, schema-qualified SQL supports insertion
of already-sanitized events, PK lookup, request-reference correlation,
unreviewed-event lookup, and authorized review-state persistence. Structural
allowlists reject unknown and obviously secret-bearing raw-value keys before
SQL construction.

The repository remains a secret-safe security/governance persistence boundary,
not a general application log. It performs no semantic secret detection,
creates no connection or pool, and owns no transaction, commit, or rollback.
Mock-based validation passed with 10 focused AUDIT tests, 62 combined
repository tests, 43 database tests, and 105 full-suite tests. Compilation,
imports, dependency checks, and whitespace validation passed without real
PostgreSQL access.

**Status:** Approved; Phase 4.8.9 complete; Phase 4.8.10 current; Phase 4.8 in
progress.

---

## DEC-142 — Explicit composable transaction boundary implemented

**Decision:** `PostgresDatabase` owns the explicit application transaction
boundary. `PostgresDatabase.transaction()` obtains one pooled
`AsyncConnection`, enters Psycopg's native `connection.transaction()` context,
and yields that same connection to the caller. Multiple repositories may share
it for one atomic operation while continuing to own no pool, connection
lifecycle, transaction, commit, or rollback.

Psycopg owns completion behavior: normal transaction-context exit commits and
exceptional exit rolls back. Original application/repository exceptions are
not swallowed or translated in this phase. The architecture supports future
atomic RAG publication and multi-repository operations without adding a Unit of
Work, custom nested/savepoint abstraction, or ambient transaction framework.

The pgvector configuration rollback approved in DEC-137 remains a separate
physical-connection initialization concern. No real PostgreSQL connection was
opened. Mock-based validation passed with 7 focused transaction tests, 23
combined database infrastructure tests, 62 repository tests, and 112 full-suite
tests; compilation, imports, dependency checks, and whitespace validation also
passed.

**Status:** Approved; Phase 4.8.10 complete; Phase 4.8.11 current; Phase 4.8 in
progress.

---

## DEC-143 — Typed database result mapping layer implemented

**Decision:** Formally implement and approve the centralized database-row-to-Python/Pydantic
result mapping layer in `apps/agent_api/app/database/mapping.py` backed by typed
database read models in `apps/agent_api/app/database/models.py`:

1. **Centralized Result Mapping Layer:**
   - Centralized mapping functions in `apps/agent_api/app/database/mapping.py`:
     `map_rag_source`, `map_rag_document`, `map_search_candidate`,
     `map_automation_run`, `map_service_request`, `map_establishment`,
     `map_execution_log`, `map_protocol_status_facts`,
     `map_execution_failure_evidence`, and `map_security_event`.
   - Raw Psycopg `dict_row` outputs are strictly isolated behind repository
     read methods; callers and application services receive only strongly typed
     models.
2. **Immutability & Strict Field Policy:**
   - All database read models in `apps/agent_api/app/database/models.py` enforce
     `ConfigDict(frozen=True, extra="forbid")`.
   - Missing required columns, unexpected extra fields, or invalid types fail
     fast via Pydantic `ValidationError`.
3. **RAG Retrieval Boundary & Model Separation:**
   - `PersistedChunk` is the physical RAG chunk representation returned from
     database mapping (BIGINT `chunk_id: int`, UUID `document_id: UUID`,
     physical `content_type`, order, section, metadata, created_at).
   - `SearchCandidate` combines `PersistedChunk`, `RetrievalProvenance`, and
     per-channel lexical/semantic evidence (`retrieval_channel`, `channel_rank`,
     `channel_score`).
   - `RetrievedChunk` retains its architectural meaning as the final fused/ranked
     RAG result produced by the future RRF layer. It includes `PersistedChunk`,
     `RetrievalProvenance`, final `rank` (ge=1), final `score`, and
     `matched_channels`.
   - Database mapping does not create final `RetrievedChunk` objects.
   - `RRFRanker` remains a skeleton, but its contract is confirmed as:
     `Sequence[SearchCandidate] -> list[RetrievedChunk]`.
   - `ContextBuilder` continues to consume final `RetrievedChunk` objects
     (`Sequence[RetrievedChunk] -> GroundedContext`).
   - No RRF or grounding runtime was implemented by this correction.
   - Structural chunking model `Chunk` remains untouched as the pre-ingestion
     domain model.
   - `Sequence[SearchCandidate]` remains the read return type for lexical and
     semantic retrieval on `RAGRepository` and `RAGRepositoryContract`.
4. **OPS Factual Read Models:**
   - Implemented `AutomationRunRecord`, `ServiceRequestRecord`,
     `EstablishmentRecord`, `ExecutionLogRecord`, `ProtocolStatusFacts`
     (with typed tuples for nested JSONB `establishments` and
     `execution_timeline`), and `ExecutionFailureEvidence` (with optional
     previous successful run mapping).
   - Repositories return observed facts only without diagnosis or inference.
5. **AUDIT Read Model:**
   - Implemented `SecurityEventRecord` in `apps/agent_api/app/database/models.py`
     for single and sequence query results under the secret-safe boundary.
6. **Write Payloads Preserved:**
   - Repository write method inputs continue to accept `RepositoryRecord = Mapping[str, object]`.
   - Write-side command DTO redesign was intentionally not introduced.
7. **Architectural Invariants Maintained:**
   - DEC-142 composable transaction architecture remains intact; repositories
     receive injected connections, create no pools, and never commit or roll back.
   - Zero ORM, SQLAlchemy, or Alembic introduced.
   - Safe database error translation is not implemented here and remains
     deferred to Phase 4.8.12.
   - No real PostgreSQL connection was opened and no real database queries were
     executed.
8. **Validation Evidence:**
   - 10 database model tests, 9 RAG model tests, 21 mapping tests, 19 RAG repo
     tests, 19 OPS repo tests, 10 AUDIT repo tests, 13 repository contract tests,
     3 repository base tests, and 8 RAG retrieval contract regression tests passed.
   - Full test suite: 162 passed in Python 3.14.2 virtual environment.
   - Compilation (`compileall apps tests`), `pip check`, and `git diff --check`
     passed cleanly.

**Rationale:** Provide type safety, immutability, and immediate validation for
all data read from the PostgreSQL database, eliminating fragile dictionary key
access while keeping repositories transaction-clean, maintaining strict separation
between persisted chunk rows and final fused retrieval chunks, and preserving
future RRF and grounding contracts.

**Status:** Approved; Phase 4.8.11 complete; Phase 4.8.12 current; Phase 4.8 in
progress.

---

## DEC-144 — Safe database exception translation implemented

**Decision:** Implement centralized, secret-safe translation in
`apps/agent_api/app/database/errors.py`. Recognized Psycopg and
`psycopg_pool` failures are converted to stable application-facing errors
without copying driver messages, SQL, parameters, DSNs, credentials, constraint
names, or server diagnostics.

- `PoolTimeout` maps to `SafeConnectionError` with conservative
  `retryable=True` metadata. `PoolClosed` and generic `OperationalError` map to
  `SafeConnectionError` with `retryable=False`; integrity and query failures are
  also non-retryable.
- Integrity failures map to non-retryable `SafeIntegrityError`; programming,
  data, internal, and unsupported-operation failures map to non-retryable
  `SafeQueryError`; interface and other recognized driver errors map to the
  non-retryable `SafeDatabaseError` fallback.
- `PostgresDatabase` applies translation around pool open, connection checkout,
  and explicit transactions. `BaseRepository` applies it around cursor use, so
  all concrete repositories receive the same boundary behavior.
- The original driver exception is retained as `__cause__`; already-safe errors
  pass through without re-translation or self-chaining. No automatic logging,
  retry loop, database-error HTTP mapping, or secret disclosure is introduced.
  Pydantic validation, application errors, and control-flow exceptions
  propagate unchanged. The pgvector initialization callback retains DEC-137's
  `BaseException` cleanup semantics: cancellation triggers rollback, and cleanup
  failure cannot mask the original cancellation.
- Repositories remain connection-bound and transaction-free. No SQL, schema,
  migration, database object, real PostgreSQL connection, ORM, MCP runtime
  dependency, or additional transaction abstraction was introduced.

**Validation:** 17 error-taxonomy tests, 7 infrastructure/repository integration
tests, 42 combined database infrastructure/error tests, 64 repository tests,
and 186 full-suite tests passed in the approved Python 3.14.2 environment.
`compileall apps tests`, `pip check`, imports, static boundary checks, and
`git diff --check` passed.

**Status:** Approved; Phase 4.8.12 complete; Phase 4.8.13 current; Phase 4.8 in
progress.

---

## DEC-145 — Real PostgreSQL connectivity validated

**Decision:** Approve the real local application connection path using runtime
environment values loaded from `.env` through `load_database_config()`, then
`PostgresDatabase` and its Psycopg 3 `AsyncConnectionPool`. No credential,
connection string, or secret value is recorded.

The validation proved pool open and readiness wait, physical-connection
pgvector configuration, connection acquisition and return, read-only server
response, and clean pool close. The observed database was `getnet_support`, the
server major version was PostgreSQL 17, and the installed extension reported
pgvector 0.8.6. A parameterized vector value round-tripped through the registered
adapter. The Windows test harness used Psycopg's required selector event loop;
runtime database architecture was unchanged.

The focused real-connectivity test passed once, and 69 related configuration,
error, vector, connection, and transaction tests passed afterward. No schema,
migration, database object, or persistent application data was modified.

**Status:** Approved; Phase 4.8.13 complete; Phase 4.8.14 current; Phase 4.8 in
progress.

---

## DEC-146 — Real repository operations validated

**Decision:** Approve real PostgreSQL execution of all public concrete methods
of `RAGRepository`, `OperationalRepository`, and `AuditRepository` through one
injected Psycopg `AsyncConnection` per transaction. Repository ownership,
parameterized schema-qualified SQL, typed immutable result mapping, and external
transaction control remain unchanged.

RAG validation covered source/document identity and updates, checksum detection,
ingestion lifecycle, non-empty chunk replacement, ACTIVE source/document
filtering, PostgreSQL FTS, exact cosine pgvector retrieval, provenance-bearing
`SearchCandidate` mapping, and terminal ingestion status. OPS validation covered
the complete synthetic R1 run/email/attachment/protocol/establishment/log flow,
typed reads, timelines, protocol status facts, and failure evidence without
diagnosis. AUDIT validation covered sanitized insert, PK lookup, request
correlation, unreviewed lookup, review update, and typed result mapping.

A controlled duplicate repository write produced a real PostgreSQL integrity
failure translated to `SafeIntegrityError`; the safe message exposed no SQL or
test value and retained the original Psycopg exception as its internal cause.
Every write scenario ended through transaction rollback. The six-test real
integration suite passed, the 172-test database/repository unit gate passed, and
a final read-only cross-domain check found zero synthetic integration records.
No seed data, DDL, migration, index, schema, or persistent data change occurred.

**Status:** Approved; Phase 4.8.14 complete; Phase 4.8.15 complete; Phase 4.8.16
current; Phase 4.8 in progress.

---

## DEC-147 — Phase 4.8 database access layer completed

**Decision:** Approve the complete Phase 4.8 database access layer after the
final 4.8.16 audit. The implemented pipeline is:

`FastAPI / Agents -> Application Services -> Repositories -> PostgresDatabase -> Psycopg 3 + pgvector -> PostgreSQL 17`

The approved implementation includes validated immutable configuration, one
explicit async pool lifecycle, per-physical-connection pgvector registration,
strict RAG/OPS/AUDIT repository ownership, parameterized schema-qualified SQL,
composable transactions, immutable typed result mapping, and secret-safe
database-error translation. Real application connectivity, RAG FTS, exact
cosine pgvector retrieval, OPS evidence queries, AUDIT persistence/review, and
real integrity-error translation were all proven against local PostgreSQL 17
and pgvector 0.8.6.

All synthetic repository writes were enclosed in intentional rollback
transactions. The final read-only cleanliness test reported zero matching RAG,
OPS, or AUDIT integration records. No migration, schema, constraint, index,
extension configuration, seed data, production data, ORM, Alembic layer,
repository-owned transaction, MCP runtime dependency, or custom Unit of Work
was introduced. No secret was recorded or exposed.

Final evidence: six explicit real integration tests passed; the normal full
suite reported 189 passed and 6 opt-in integration tests skipped; compilation
of `apps` and `tests`, `pip check`, imports, static repository-boundary checks,
protected-file checks, and `git diff --check` passed. `knowledge/`,
`docs/challenge.md`, Harness Governance, migrations, and database structure were
unchanged. No commit or push occurred.

**Status:** Approved; Phase 4.8 complete; Phase 4.9 is the next roadmap phase
and has not been started.

---

## DEC-148 — Reusable OPS seed infrastructure and Case 001 approved

**Decision:** Approve the Phase 4.9 OPS-only seed structure in
`database/seed/ops/` and the first persistent synthetic scenario,
`caso_001_sucesso`.

The runner uses the approved path `DatabaseConfig -> PostgresDatabase ->
PostgresDatabase.transaction() -> OperationalRepository`. The runner owns one
pool lifecycle; scenario modules receive only the transaction-bound repository
and never create pools or connections, commit, roll back, or issue direct
persistence SQL. A registry maps stable IDs to scenarios, allowing future
cases without rewriting the execution engine.

Case 001 persists one synthetic R1 success on 2026-09-01 and one R2 success
continuing the same `POC-OPS-0001` protocol on 2026-09-02. It creates exactly
two OPS runs, one email, one attachment, one request, one establishment, and
sixteen execution-log entries (ten R1 and six R2). All human-facing synthetic
content is Portuguese; constrained technical statuses remain approved schema
values. R2 creates no email, attachment, protocol, or establishment.

The protocol is the idempotency key. Reruns report the existing scenario and
leave all rows unchanged; no destructive replacement or seed-tracking table is
introduced. RAG and AUDIT are not seeded. No migration, schema, constraint,
index, extension, or runtime database architecture changed.

**Validation:** focused runner/scenario tests passed (7); the opt-in real
persisted-scenario and idempotency checks passed (2); database tests passed
(52); repository tests passed (64); full suite passed (196) with eight opt-in
integration tests skipped. Compilation and whitespace checks passed. `pip
check` reported only the known external Google ADK/FastAPI environment conflict,
which was not modified. No secret was exposed, and no commit or push occurred.

**Status:** Approved; Phase 4.9.1 and 4.9.2 complete; Phase 4.9.3 is next;
Phase 4.9 remains in progress.

---

## DEC-149 — JSON-driven OPS seed scenarios and Case 002 approved

**Decision:** Replace scenario-specific Python seed implementations with a
validated JSON scenario engine. UTF-8 files under `database/seed/ops/scenarios/`
are auto-discovered in deterministic order. Pydantic contract validation rejects
malformed or duplicate definitions, naive timestamps, unsupported statuses,
blank required messages, and inconsistent success/failure lifecycles before
persistent execution.

The generic executor maps the approved R1/R2 cancellation lifecycle to
`OperationalRepository` operations under the existing
`PostgresDatabase.transaction()` boundary. JSON is operational data only: it
cannot carry SQL, arbitrary repository method names, executable Python, or
credentials. Protocol-number idempotency remains authoritative; existing
protocols are skipped without replacement or additional records.

Case 001 was migrated to `caso_001_sucesso.json` and its persisted
`POC-OPS-0001` records were verified unchanged. Case 002,
`caso_002_erro_download_r2` / `POC-OPS-0002`, records successful R1 processing
followed by R2 result-file download failure. Its final request is `FAILED`; its
establishment retains upload `SUCCESS` but has download and processing `ERROR`;
no successful return email is recorded. The Case 002 footprint is two runs, one
email, one attachment, one request, one establishment, and fifteen logs
(10 R1/5 R2), with download and terminal R2 failure evidence at `ERROR`.

**Validation:** 11 focused JSON-loader/executor tests and four opt-in real Case
001/002 persistence/idempotency tests passed. Full suite: 200 passed and 10
opt-in integration tests skipped. Compilation, imports, and whitespace checks
passed. `pip check` reported only the known external Google ADK/FastAPI conflict,
which was not modified. No migration, schema, index, RAG/AUDIT seed, secret,
commit, or push was introduced.

**Status:** Approved; Case 002 complete under 4.9.3; Phase 4.9 remains in
progress pending owner selection of additional scenarios.

---

## DEC-150 — Phase 4.9 JSON-driven OPS seed architecture completed

**Decision:** Approve the reusable JSON-driven OPS seed architecture as the
permanent Phase 4.9 development/POC seed mechanism. Scenario JSON definitions
under `database/seed/ops/scenarios/` are automatically discovered and
validated through Pydantic before execution. One generic executor materializes
the supported lifecycle through `OperationalRepository` under the existing
transaction boundary; scenario-specific Python implementations and arbitrary
JSON instructions are not part of the architecture.

Protocol number remains the idempotency business key. Existing protocols are
skipped without mutation, and each new scenario is persisted atomically in
its own transaction. The validated contract supports lifecycle variation,
including R1 failure without R2 and R2 failure states. `docs/ops-seed.md` is
the authoritative future JSON authoring guide.

**Status:** Approved; Phase 4.9 complete; Phase 4.10 current; Phase 4 in
progress.

---

## DEC-151 — Phase 4.10 database validation completed

**Decision:** Approve Phase 4.10 after a fast evidence-based validation pass
through the existing application infrastructure and repository paths. Real
connection identity, pool lifecycle, representative transactional
insert/select/update/rollback behavior, FK and constraint enforcement,
pgvector vector persistence/search, PostgreSQL FTS retrieval, OPS factual
reads, AUDIT sanitized persistence, regression tests, compilation,
dependency checks, and whitespace checks passed. Existing synthetic OPS
records were reused; temporary validation data was rolled back or confirmed
absent.

No schema, migration, index, or database-object change was required. The
validation retained the established repository and transaction boundaries and
did not introduce application logic or seed data.

**Validation:** Real integration suite with persistent OPS verification: 10
passed. Focused database/repository suite: 146 passed. Full suite: 211
passed. Compilation, `pip check`, and `git diff --check` passed.

**Status:** Approved; Phase 4.10 complete; Phase 5 INGESTION EXECUTÁVEL
current.

---

## DEC-152 — Deterministic pre-index ingestion preparation approved

**Decision:** Phase 5 normalizes curated UTF-8 content without semantic
rewriting and calculates a lowercase SHA-256 checksum from normalized content.
The checksum drives `INGEST`, `REINGEST`, and `SKIPPED_UNCHANGED` decisions
through the existing RAG repository lookup contract.

Structural chunking is deterministic and Markdown-aware: headings establish
sections; explicit rule and technical structures retain their approved
boundaries; oversized units split only as a paragraph-boundary safeguard.

**Status:** Approved; Phase 5 implementation in progress.

---

## DEC-153 — Prepared-ingestion boundary and controlled public registry approved

**Decision:** Phase 5 returns strict immutable prepared-document and
prepared-chunk contracts carrying content, ordering, structural type, and
JSON-compatible provenance. These contracts contain no embedding or PostgreSQL
FTS payload. Public source registration remains an explicit validated allowlist
with no crawling or automatic URL ingestion. Internal and public manual entry
points delegate to the shared ingestion preparation service.

Current persisted chunks remain untouched until Phase 6 can generate complete
embedding and FTS data and publish atomically through `RAGRepository`.

**Status:** Approved; Phase 5 implementation in progress.

---

## DEC-154 — Phase 5 executable ingestion preparation completed

**Decision:** Approve Phase 5 after real curated R1/R2 corpus preparation and
approved public registry validation completed without database mutation.
Focused ingestion tests, the complete regression suite, compilation,
dependency validation, and whitespace validation passed. No schema, migration,
index, constraint, fake embedding, incomplete chunk, historical-version model,
or retrieval publication was introduced.

**Validation:** 20 focused ingestion tests passed; public registry CLI
validated 22 sources with network disabled; full suite: 221 passed, 10 skipped.

**Status:** Approved; Phase 5 complete; Phase 6 FASTEMBED EXECUTÁVEL current.

---

## DEC-155 — Phase 5 contract and approval corrections

**Decision:** Correct the Phase 5 preparation boundary without changing the
physical database model. Structural `boundary_type` remains distinct from
database-compatible `content_type`: `section` maps to `TEXT`,
`business_rule` to `BUSINESS_RULE`, and `technical_symbol` to `TECHNICAL`.

The public registry representation `public_getnet` maps explicitly to the
database source type `PUBLIC_OFFICIAL` and origin `PUBLIC`; `source_class` is
retained in prepared provenance. The registry is reported as 23 registered
records and 22 ingestion-enabled records. Internal CLI paths accept only
files below the approved `knowledge/internal/` tree. No incomplete chunk,
embedding, or database publication was introduced.

**Status:** Approved; Phase 5 corrections complete; Phase 6 FASTEMBED
EXECUTÁVEL current.

---

## DEC-156 — Executable FastEmbed embedding adapter implementation

**Decision:** Implement the local FastEmbed adapter (`FastEmbedAdapter`) utilizing
the approved multilingual embedding model:
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` via FastEmbed 0.8.0.
Execution is performed strictly locally on CPU through the ONNX Runtime without
relying on external network access or third-party embedding APIs.

Every generated document and query vector is strictly validated to ensure:
1. Exact dimensionality of 384 (`VECTOR(384)`);
2. Finite numeric floating-point values (no `NaN` or `Inf`);
3. Rejection of blank, empty, or non-string inputs;
4. Preservation of FastEmbed's native mean pooling without manual vector normalization.

**Rationale:** Satisfies the architectural requirement for deterministic, local,
zero-external-dependency semantic representation aligned with the PostgreSQL
`rag.chunks.embedding VECTOR(384)` column.

**Status:** Approved; implemented and validated in Phase 6.

---

## DEC-157 — Native PostgreSQL FTS representation and weight hierarchy

**Decision:** Maintain native PostgreSQL Full Text Search vector generation inside
`RAGRepository.replace_document_chunks` using PostgreSQL's dual configuration:
- Document title: `portuguese` with weight `'A'`;
- Section title: `portuguese` with weight `'B'`;
- Portuguese text content: `portuguese` with weight `'C'`;
- Technical / exact symbol content: `simple` with weight `'D'`.

The tsvector payload is dynamically synthesized in the database during chunk
insertion via a SQL `CASE` construct when not explicitly supplied, ensuring
strict alignment between the document title, chunk section, and content.

**Rationale:** Prevents application-side text-search discrepancies, eliminates
redundant Python stemming dependencies, and satisfies database check constraints
requiring `search_vector IS NOT NULL` on retrievable chunks.

**Status:** Approved; implemented and validated in Phase 6.

---

## DEC-158 — Atomic PostgreSQL RAG publication and rollback guarantees

**Decision:** Implement atomic publication for `INGEST` and `REINGEST` through
`RAGPublicationService` and `PostgresDatabase.transaction()`.

Crucial architectural invariant: all chunk embeddings must be computed and validated
by `FastEmbedAdapter` *before* the database transaction is initiated. If embedding
generation fails, no database transaction is opened and existing database rows
remain completely untouched.

Within the atomic transaction:
1. Validate source existence in `rag.sources`;
2. Record ingestion run start in `rag.ingestion_runs`;
3. Persist/activate document in `rag.documents` (`status = 'ACTIVE'`);
4. Atomically delete and replace chunks in `rag.chunks`;
5. Complete ingestion run record (`status = 'SUCCESS'`).

If any operation within the database transaction fails, a full transaction
`ROLLBACK` is triggered, preserving the prior retrievable state intact.

For `SKIPPED_UNCHANGED` documents, embedding generation and chunk replacement
are skipped; an ingestion run record is logged with `status = 'SKIPPED'` and
`chunks_created = 0`.

**Rationale:** Guarantees that no partially published or inconsistent document
state can become retrievable by future query agents.

**Status:** Approved; implemented and validated in Phase 6.

---

## DEC-159 — Phase 6 executable FastEmbed and atomic RAG publication completed

**Decision:** Approve completion of Phase 6 after successful end-to-end publication
of representative curated internal documents (PDD, SDD, and Technical Overview)
into local PostgreSQL 17 + pgvector 0.8.6.

Persisted results:
- 1 active internal source (`rag.sources`);
- 3 active documents (`rag.documents`);
- 99 complete chunks (`rag.chunks`), each with a 384-dimensional FastEmbed vector
  and a populated native FTS `search_vector`;
- Both lexical smoke retrieval (`search_lexical_candidates`) and semantic smoke
  retrieval (`search_semantic_candidates`) verified against the real database.

Validation: 17 focused tests passed (100%); full test suite: 246 passed, 4 skipped;
`compileall apps tests` passed; `git diff --check` clean; database schema and
migrations unmodified.

**Status:** Approved; Phase 6 complete; Phase 7 HYBRID RETRIEVAL + RRF current.

---

## DEC-160 — Consistent Phase 7 retrieval snapshot approved

**Decision:** Execute lexical PostgreSQL FTS and semantic pgvector candidate
queries through one `PostgresDatabase.transaction()` checkout. The RAG
repository sets that transaction to `REPEATABLE READ READ ONLY` before either
query, so both channels observe one committed database snapshot. The
retrievers remain async, repository-bound, and contain no SQL.

**Status:** Approved; Phase 7 implementation in progress.

---

## DEC-161 — Rank-only Reciprocal Rank Fusion approved

**Decision:** Fuse at most 10 lexical and 10 semantic `SearchCandidate`
results using rank positions only with RRF:

```text
RRF(chunk) = sum(1 / (60 + rank_channel))
```

Raw FTS/cosine scores are not combined or normalized. No channel weighting,
ML reranker, ANN index, or vector index is introduced. Duplicate physical
`chunk_id` values are merged; ties use best channel rank and then stable
`chunk_id`. The final output is at most five `RetrievedChunk` values with
channel presence/ranks, matched channels, provenance, and fused score.

**Status:** Approved; Phase 7 implementation in progress.

---

## DEC-162 — Phase 7 hybrid retrieval and RRF completed

**Decision:** Approve Phase 7 after focused unit coverage and real PostgreSQL
corpus validation of lexical retrieval, semantic retrieval, consistent
snapshot orchestration, rank-only RRF, physical-chunk deduplication,
deterministic tie-breaking, provenance preservation, and Top-5 bounding.
Phase 8 grounding, citations, evidence sufficiency, and answer generation
remain unimplemented.

**Validation:** Focused Phase 7/repository tests: 41 passed; real hybrid
retrieval test: 1 passed; final fast regression: 254 passed and 4 skipped;
`compileall apps tests`, `pip check`, and `git diff --check` passed after the
final correction gate.

**Status:** Approved; Phase 7 complete; Phase 8 GROUNDING / ANTI-ALUCINAÇÃO
current.

---

## DEC-163 — Provider-neutral grounding and anti-hallucination boundary completed

**Decision:** Approve Phase 8 grounding as a provider-neutral boundary consuming
Phase 7 `RetrievedChunk` results and producing immutable `GroundedContext`
values. The boundary validates non-empty evidence and retains the complete
structured `RetrievalProvenance` fields inside `EvidenceProvenance`, including
source, document, chunk, and retrieval metadata. It deduplicates by physical
`chunk_id`, preserves lower-priority evidence, and assigns deterministic
citations. Source priority is Tier 1 internal PDD/SDD, Tier 2 internal
technical documentation, and Tier 3 approved public Getnet content. Internal
citations use abstract safe labels and never expose titles, references, local
paths, UUIDs, database names, tables, credentials, or secrets. Public citations
may expose an approved public title and URL; full provenance remains internal.

Sufficiency is structural only: usable evidence yields
`SUFFICIENT_CONTEXT`, while no usable evidence yields
`INSUFFICIENT_EVIDENCE` with a controlled reason. Retrieved text is passive DATA
and no score threshold, confidence percentage, LLM, answer generation, semantic
conflict classification, database write, or Phase 9 orchestration is introduced.

**Validation:** Grounding unit and contract tests: 13 passed; opt-in real
corpus grounding test: 1 passed; fast regression: 247 passed, 17 skipped;
compile/dependency/whitespace checks passed.

**Status:** Approved; Phase 8 complete; Phase 9 MULTI-AGENT + RAG + TOOLS +
TAVILY current and not started.

---

## DEC-164 — Phase 9 specification-first baseline approved

**Decision:** Establish a lightweight project-specific Spec-Driven Development
baseline under `docs/specs/phase-9/` before Phase 9 runtime implementation.
The six specifications define traceable requirements for the future LLM/provider,
agents, controlled tools, orchestration, external search, and `/chat` boundary.
Challenge requirements and approved project/domain documents remain higher
authority than the Phase 9 specifications. Future implementation and tests
must conform to reviewed requirements; conflicts must be reported and resolved
explicitly. No external SDD framework dependency is introduced.

**Status:** Approved; the Phase 9 SDD Foundation remains authoritative. Phases
9.2 through 9.10 are implemented under this baseline. Phase 9.8 uses typed,
non-persistent live-web grounding before generation; its approved Getnet source
priority is derived from the existing public registry. Phase 9.9 implements
Human Escalation, Phase 9.10 implements `/chat`, and Phase 9.11 is next.

---

## DEC-165 — Internal Django-to-FastAPI service authentication boundary

**Decision:** Authenticate the future Django-to-FastAPI internal request with a
runtime-only Bearer service credential loaded from `AGENT_API_SERVICE_TOKEN`.
Only after that check may FastAPI trust the service-supplied user identity,
CLIENT/SUPPORT_AGENT role, and optional OPS-authorization claim. The JSON
`user_id` remains a logical application assertion and MUST match the trusted
identity; it is not authentication proof. FastAPI issues no JWT, OAuth token,
or user session and stores no user or conversation record.

**Rationale:** Preserve DEC-001 ownership—Django owns user authentication and
sessions, while FastAPI owns internal agent execution—without allowing an
arbitrary request body to fabricate OPS access or human-operator authority.

**Status:** Approved and implemented in Phase 9.10. Phase 9.11 end-to-end
validation remains next.
