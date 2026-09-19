# Getnet Support — Project Context

## Purpose

This document records the current approved working context of the getnet-support
POC. It allows future agents and developers to resume work from repository
evidence without relying on chat history.

## Current Phase

**Current major phase:** PostgreSQL + pgvector

**Current task:** Schema architecture definition

**Current conceptual subtask:** 4.1.2 — Define responsibility of the OPS schema

**Current schema discussion order:**

1. `rag` responsibility — completed
2. `ops` responsibility — current
3. `audit` responsibility — next

**Current status:**

- PostgreSQL Docker infrastructure is working.
- PostgreSQL 17 is running; the observed container version is 17.11.
- pgvector 0.8.6 is enabled.
- The project roadmap records that the DBeaver connection works.
- Physical RAG, OPS, and Audit schemas/tables have not been created.
- Schema architecture remains under review.

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
- Public Getnet sources are secondary and cannot override internal
  cancellation-process rules.
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

#### Conceptual information categories

The RAG schema conceptually represents:

1. source;
2. document;
3. retrievable content and chunks;
4. lexical retrieval representation;
5. semantic/vector retrieval representation;
6. ingestion tracking;
7. provenance and governance metadata.

#### POC simplification

Historical document-version management is not required for this POC. The POC
must not use `rag.document_versions` or maintain historical document versions
such as v1, v2, and v3.

A checksum may remain on the current document to detect content changes. If a
document changes during the POC:

1. detect the change through its checksum;
2. reprocess the document;
3. replace its current retrievable chunks in a controlled way.

Historical document versions must not be introduced unless a future
requirement explicitly demands them. This simplification is intentional:
`docs/challenge.md` requires a functional RAG pipeline but does not require
historical knowledge-document versioning.

#### Provenance

Retrieved evidence must internally preserve enough provenance to identify:

- source;
- document;
- chunk;
- section or logical location when available;
- document checksum when applicable.

This internal provenance supports grounding, evaluation, debugging, and
auditability.

#### User-facing attribution abstraction

Detailed internal provenance must not automatically be exposed to users.
Normal user responses must not disclose internal implementation details such
as:

- PDD, SDD, or Technical Overview filenames;
- database table, schema, or column names;
- SQL;
- chunk IDs;
- hashes or checksums;
- internal file paths;
- the database technology used for retrieval;
- connection information.

Use abstract source classes instead:

- PDD, SDD, or Technical Overview: “Segundo a documentação do processo...”
- Security policy: “Segundo a política interna de segurança...”
- Operational records: “Segundo os registros de execução...” or “Segundo os
  registros operacionais do processo...”
- Approved official public sources: “Segundo informações públicas oficiais...”

#### Functional process data

Authorized business-facing process information may be returned when relevant,
including:

- protocol number;
- status;
- processing date and time;
- related sender or email when appropriate;
- related filename;
- upload or download result;
- business rejection or error reason;
- operational result.

These functional facts may be exposed without revealing how or where they are
physically stored. For example:

> Segundo os registros de execução, o protocolo X está associado ao arquivo Y
> e permanece em andamento.

A response must not identify an internal table or persistence query used to
obtain that fact.

#### RAG and OPS responsibility boundary

- RAG answers: “What should happen?” and “What does the approved documentation
  say?”
- OPS answers: “What actually happened?”

For example, RAG may establish the documented rule for when a protocol should
transition, while OPS may establish the currently observed status of a specific
protocol. The agent may compare expected behavior with observed operational
state without exposing implementation details of either persistence layer.

Current approved conceptual structures:

- `rag.sources`
- `rag.documents`
- `rag.chunks`
- `rag.ingestion_runs`

These structures are conceptual. No physical `rag` schema or table has been
created.

### `ops`

Purpose: operational RPA execution state.

Reference Oracle-derived structures include concepts for:

- RPA registration;
- execution;
- logs;
- alerts;
- processing;
- email;
- attachments;
- EC;
- consolidated cancellation-process state.

The Oracle model is reconstructed and reference-only. It is not an
authoritative production schema. No physical `ops` schema or table has been
created.

### `audit`

Purpose: security and governance audit events.

Planned first table:

- `audit.security_events`

Expected event categories include:

- credential requests;
- secret requests;
- database access requests;
- sensitive infrastructure requests;
- prompt injection;
- authorization bypass attempts;
- security policy probes.

No physical `audit` schema or table has been created.

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

The RAG evaluation dataset is `evaluation/rag/dataset-v1.yaml` and currently
contains 25 cases.

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
- `reference/automation-anywhere/cancelamento-vendas/`
- `apps/agent_api/app/`
- `docs/project-roadmap.md`
- `docs/decision-log.md`

## Current Pending Decisions

- Final physical architecture of the `rag` schema.
- Exact `rag` table columns and relationships.
- Final FastEmbed model and embedding vector dimension.
- `ops` schema design.
- `audit` schema design.
- PK, FK, index, uniqueness, nullability, and constraint strategy.
- Python database libraries and repository implementation.
- Executable ingestion.
- Executable embeddings.
- Executable hybrid retrieval and RRF.
- Grounding runtime.
- Knowledge Agent.
- Evaluation runner.
- Django integration.

## Immediate Next Step

Complete 4.1.2 by defining and approving the conceptual responsibility of the
OPS schema. The approved RAG responsibility and current conceptual structures
remain inputs to the later physical design:

- `rag.sources`
- `rag.documents`
- `rag.chunks`
- `rag.ingestion_runs`

No DDL should be generated until the conceptual schema architecture is
approved.

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
