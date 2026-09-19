# Getnet Support — Project Context

## Purpose

This document records the current approved working context of the getnet-support
POC. It allows future agents and developers to resume work from repository
evidence without relying on chat history.

## Current Phase

**Current major phase:** PostgreSQL + pgvector

**Current task:** Detailed schema architecture

**Current subtask:** 4.4 — AUDIT Schema Architecture

**Conceptual schema architecture status:**

1. `rag` responsibility — completed
2. `ops` responsibility — completed
3. `audit` responsibility — completed
4. limits and flow between schemas — completed
5. complete conceptual schema architecture — approved
6. 4.2 RAG detailed schema architecture — completed
7. 4.3 OPS detailed schema architecture — completed

**Current status:**

- PostgreSQL Docker infrastructure is working.
- PostgreSQL 17 is running; the observed container version is 17.11.
- pgvector 0.8.6 is enabled.
- The project roadmap records that the DBeaver connection works.
- Phase 4.1 is complete.
- Phase 4.2 is complete; detailed conceptual architecture of the RAG schema (`rag.sources`, `rag.documents`, `rag.chunks`, `rag.ingestion_runs`) is approved.
- Phase 4.3 is complete; detailed conceptual architecture of the OPS schema (`ops.automation_runs`, `ops.incoming_emails`, `ops.email_attachments`, `ops.service_requests`, `ops.establishments`, `ops.execution_log`) is approved.
- RAG, OPS, and AUDIT conceptual responsibilities and boundaries are approved.
- No physical RAG, OPS, or AUDIT schema or table has been created yet.
- The project now advances to 4.4 — AUDIT Schema Architecture.

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

- Planned orchestration layer for routing, specialized agents, state, handoff,
  and escalation.

### Planned multi-agent responsibilities

The runtime agents are approved architecture but are not implemented yet.

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
sanitized AUDIT architecture. The design addresses the optional fourth-agent
and human-handoff capabilities in `docs/challenge.md`, but remains approved
architecture and planned implementation only.

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

`knowledge/public/sources.yaml` is the exact public-source registry. It now
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

The FastAPI/RAG package currently provides executable imports and typed
interfaces, but not a completed RAG runtime.

Implemented as API structure or contracts:

- FastAPI `main.py`;
- `GET /health`;
- `GET /ready` placeholder;
- typed `POST /chat` placeholder;
- fail-closed internal-service authentication placeholder;
- `RAGService` facade;
- RAG configuration and domain/provenance models;
- ingestion loader, validator, and structural chunker skeletons;
- FastEmbed adapter skeleton;
- lexical, semantic, and hybrid retrieval skeletons;
- RRF ranking skeleton;
- grounding/context-builder skeleton.

The ingestion, embeddings, database persistence, PostgreSQL FTS queries,
pgvector queries, hybrid orchestration, RRF calculation, grounding runtime,
LangGraph execution, and LLM calls are not implemented. Placeholder methods
raise `NotImplementedError`, readiness remains unavailable, and `/chat` does not
execute an agent.

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

These structures are conceptual. No physical `rag` schema, table, DDL,
migration, or index exists yet.

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

These remain conceptual fields only. Do not assign SQL types, constraints,
PK/FK implementation, enums, or indexes.

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

These remain conceptual fields only.

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

These remain conceptual fields only.

Conceptual responsibilities:

- `content`: actual retrievable text.
- `chunk_order`: logical position within the parent document.
- `section`: document section/title/logical location when available.
- `content_type`: conceptual category such as business rule, document section,
  technical description, code symbol, policy, etc.
- `metadata`: auxiliary provenance/context metadata.
- `embedding`: semantic-vector representation used by pgvector (do NOT define
  `VECTOR(N)` yet).
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

These remain conceptual fields only.

Conceptual operation examples include:

- `INGEST`
- `REINGEST`
- `SKIPPED_UNCHANGED`

Do not define physical database enums or constraints yet.

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

Do not define physical joins, FK constraints, SQL queries, or indexes yet.

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

These remain conceptual structures only; no physical `ops` schema, table, DDL,
migration, constraints, or index has been created.

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

- while items are pending or waiting, `status` remains in progress (e.g. `IN_PROGRESS`);
- when all required items are concluded, `status` transitions to completed (`COMPLETED`).

Do not define physical enums, SQL types, constraints, or SQL consolidation rules
at this stage.

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
- final state: `upload_status = SUCCESS`, `download_status = SUCCESS`, `processing_status = COMPLETED`.

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

The physical SQL type (`TIMESTAMP`, `TIMESTAMPTZ`, etc.) will be chosen in phase
4.5. The current decision is semantic: full timestamps for all time instants.

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

Do not define physical PK/FK constraints or SQL joins yet.

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

The initial POC uses one approved conceptual structure:

- `audit.security_events`

This intentionally simplified model remains conceptual. No physical `audit`
schema or table has been created, and multiple audit tables must not be
introduced unless a future approved requirement requires them.

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
- `sanitized_content`
- `action_taken`
- `result`
- `review_status`
- `reviewed_at`
- `review_note`
- `created_at`

`event_id` identifies the event and `occurred_at` records when it occurred.
`event_type` identifies its conceptual security/governance category.
`source_component` identifies the detecting or generating component, such as a
Router Agent, Knowledge Agent, Customer Support Agent, tool gateway, security
guardrail, or application boundary; no fixed physical enum is approved yet.

`user_identifier` identifies the related user only when available and
authorized. `request_reference` provides correlation to the originating
request, session, or conversation without storing the entire request payload.
`sanitized_content` contains only a sanitized description of the relevant
request or detected content. `action_taken` describes the protective action,
conceptually including `BLOCKED`, `DENIED`, `IGNORED`, `REDACTED`, or
`ALLOWED_WITH_RESTRICTION`, while `result` captures the security decision
outcome. No physical constraint or enum has been approved.

The optional `review_status`, `reviewed_at`, and `review_note` fields support
later governance review within the same POC structure. No separate review
table, review workflow implementation, or Django Admin behavior is approved at
this stage. `created_at` records creation of the audit record.

#### Approved conceptual event categories

`audit.security_events` must support at least:

- `CREDENTIAL_REQUEST`
- `SECRET_REQUEST`
- `DATABASE_ACCESS_REQUEST`
- `SENSITIVE_INFRASTRUCTURE_REQUEST`
- `PROMPT_INJECTION`
- `AUTHORIZATION_BYPASS_ATTEMPT`
- `SECURITY_POLICY_PROBE`

These are conceptual categories only. Database enums and `CHECK` constraints
have not been defined.

#### Sanitization and secret handling

AUDIT must never persist passwords, API keys, access or refresh tokens,
cookies, private keys, connection strings, database credentials, raw secret
values, secret locations, or other credential-shaped sensitive values. When
sensitive content is detected, the conceptual flow is:

`sensitive input -> detection -> sanitization/redaction -> security action -> audit.security_events`

Only a sanitized description may be stored. For example, the audit description
may state that credential-like sensitive content was detected and removed; it
must never reproduce the value itself.

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

The project maintains two separate evaluation suites:

- `evaluation/rag/dataset-v1.yaml` contains 25 cases for RAG retrieval,
  grounding, provenance, insufficient-evidence, and security quality.
- `evaluation/challenge/scenarios-v1.yaml` contains 13 end-to-end architectural
  scenarios for routing, agent and capability selection, RAG versus Web Search,
  controlled Customer Support tools, multi-agent cooperation, and security
  behavior.

The challenge suite does not replace or merge into the RAG dataset. Neither
suite has an executable evaluation runner yet.

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
- `knowledge/public/sources.yaml`
- `evaluation/rag/dataset-v1.yaml`
- `evaluation/challenge/scenarios-v1.yaml`
- `reference/automation-anywhere/cancelamento-vendas/`
- `apps/agent_api/app/`
- `docs/project-roadmap.md`
- `docs/decision-log.md`

## Current Pending Decisions

- Detailed OPS table architecture, responsibilities, and relationships in phase 4.3.
- Detailed AUDIT table architecture in phase 4.4.
- Final FastEmbed model and embedding vector dimension.
- Physical-model decisions.
- PK, FK, index, uniqueness, nullability, and constraint strategy.
- Python database libraries and repository implementation.
- Executable ingestion.
- Executable embeddings.
- Executable hybrid retrieval and RRF.
- Grounding runtime.
- Router, Knowledge, and Customer Support Agent runtime.
- Controlled Customer Support and OPS tools.
- Evaluation runner.
- Django integration.

## Immediate Next Step

Begin 4.3 — OPS Schema Architecture.

Review and approve the detailed responsibilities, relationships, and
conceptual behavior of:

- `ops.automation_runs`
- `ops.incoming_emails`
- `ops.email_attachments`
- `ops.service_requests`
- `ops.establishments`
- `ops.execution_log`

Do not create physical tables, DDL, migrations, PK/FK constraints, indexes, or
`VECTOR(N)` yet. These remain assigned to later roadmap phases.

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
