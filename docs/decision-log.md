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
