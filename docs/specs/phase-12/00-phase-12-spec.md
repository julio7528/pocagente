# Phase 12 — Django / Frontend / Final Integration

Status: **OWNER APPROVED / IMPLEMENTATION IN PROGRESS. Phase 12.1 COMPLETED / APPROVED; Phase 12.2 COMPLETED; Phase 12.3 COMPLETED; Phase 12.4 COMPLETED; Phase 12.5 COMPLETED; Phase 12.6 COMPLETED; Phase 12.7 COMPLETED; Phase 12.8 COMPLETED; Phase 12.9 COMPLETED; Phase 12.10 COMPLETED; Phase 12.11 COMPLETED; Phase 12.12 COMPLETED; Phase 12.13 COMPLETED; Phase 12.14 NEXT.**

## Purpose and authority

Phase 12 adds a browser-facing Django portal to the working FastAPI agent
runtime. `docs/challenge.md` remains the challenge authority; this Phase 12 SDD
is the implementation authority after owner approval. Existing Phase 9, 10,
11, and 11.1 contracts remain in force for agent behavior, authenticated
`/chat`, human escalation, Security/AUDIT, RAG, OPS, and output protection.

The repository does not currently contain `docs/architecture.md`. The current
architecture authority inspected for this SDD is `docs/project-context.md`,
the database specifications, the current runtime contracts, and the existing
phase specifications. Phase 12 does not amend those sources in this
specification-only task.

## Scope

Deliver `apps/web_portal` as a Django BFF and web application; custom users
with exactly `ADMIN`, `CLIENT`, and `SUPPORT_AGENT` roles; session login;
client conversations and messages; persistent human handoffs; support and
admin portals; security dashboard backed by FastAPI's AUDIT boundary; an
administrator-managed password-reset request flow; authenticated internal
Django-to-FastAPI calls; and the future `postgres`, `agent-api`,
`web-portal` Compose topology.

## Approved decisions and invariants

- Existing FastAPI / LangGraph remains the sole owner of routing, AI/business
  reasoning, security, RAG, OPS, Web, and Human Escalation decisions.
- Django owns browser authentication, sessions, role/account lifecycle,
  conversation/message persistence, portal authorization, support assignment,
  and admin workflows.
- The browser calls Django only. Internal service credentials and trusted role
  context never enter browser HTML, JavaScript, or storage.
- PostgreSQL gains a logically isolated `portal` schema. The existing `rag`,
  `ops`, and `audit` ownership and data remain independent.
- Phase 12.3 uses the existing PostgreSQL database principal for the POC.
  Separate Django credentials and grants are future production hardening; this
  does not grant Django application code ownership of `rag`, `ops`, or `audit`.
- Portal application entities use UUID primary keys and physical tables
  `portal.users`, `portal.conversations`, `portal.messages`,
  `portal.support_handoffs`, and `portal.password_reset_requests`. Django
  framework tables retain standard names inside `portal`.
- A custom Django User model is selected before the first Django migration.
  No migration creates a user or default ADMIN; the first ADMIN is created by
  the protected operator bootstrap designed in Phase 12.4/12.5.
- A new sequential native SQL migration explicitly creates `portal`; Django
  migrations explicitly own framework and portal application tables only.
  Neither path runs automatically at application startup.
- The current Human Escalation Agent state machine remains authoritative. The
  portal persists its approved transitions and adds no competing AI state
  machine.
- Phase 12.8 owns only the trusted Human Escalation transition transport for
  explicit confirmation, support-agent acceptance, and assigned-agent
  resolution. General Django/FastAPI `/chat` execution and bounded-context
  transport remain Phase 12.13.
- Phase 12.10 owns the narrow, read-only internal FastAPI AUDIT dashboard API
  and its Django integration. This is an explicitly approved vertical slice;
  it does not start the general `/chat`, bounded-context, or agent-execution
  integration assigned to Phase 12.13.
- Conversation context is available only within its owning conversation and
  is bounded on each FastAPI turn. New conversations inherit no history.
- Conversation deletion is logical. Messages and completed handoff history
  remain attached to that conversation.
- Conversation titles come once from the first CLIENT message using
  deterministic whitespace normalization and a 50-character maximum; no LLM
  title generation or continuous replacement is used.
- Message content is immutable in normal application behavior. A correction
  is a new message.
- A conversation supports at most one human-support lifecycle. The normal
  path is `ACTIVE -> WAITING_HUMAN -> HUMAN -> CLOSED`; `CLOSED` is terminal.
- `BLOCKED` is reversible administrative suspension distinct from `CLOSED`.
  Only ADMIN may unblock, restoring the recorded prior state; blocking freezes
  CLIENT, SUPPORT_AGENT, and agent writes. `DELETED` is a soft tombstone with
  no normal restore workflow.
- Passwords are stored only as Django password hashes. Admin reset requests
  never store a new plaintext password.
- `audit.security_events` remains security/governance-only. Django obtains
  dashboard evidence via a trusted FastAPI administrative API and the existing
  AuditRepository ownership boundary.
- Initial live updates use authenticated HTTP polling, not WebSockets.

Two prior contextual details need reconciliation at roadmap item 12.17 before
closure. `project-context.md` describes an earlier conceptual 1–2 second
polling interval; this Phase 12 owner instruction selects an initial interval
near 12 seconds to limit POC request volume. Also, the existing no-ORM
statement applies to FastAPI's RAG/OPS/AUDIT persistence; this SDD permits
Django ORM only for Django-owned `portal` tables. Do not modify those prior
records during this SDD task; reconcile them after implementation evidence.

## Non-goals

No replacement of the current multi-agent backend; no browser-to-FastAPI
execution; no Django OPS/RAG repository; no general-purpose CRUD proxy in
FastAPI; no cross-conversation memory; no self-service password change or
automatic email reset; no external ITSM, WhatsApp, notification table,
WebSockets, SPA framework, database migration execution at boot, or change to
schemas `rag`, `ops`, and `audit`.

## Challenge alignment

The design preserves the existing multi-agent runtime and strengthens the
challenge's clean-code/modularity goals through a Django BFF, maintains API
separation through typed internal HTTP contracts, provides a usable client and
operator application, adds Docker as a separate web service, and specifies
comprehensive authorization/E2E testing, health/operability, failure recovery,
and existing security guardrails. It does not replace the completed Router,
Knowledge, Customer Support, Human Escalation, Security, or RAG behavior.

## Requirement families

| Family | IDs | Count |
|---|---|---:|
| Core | `REQ-P12-CORE-001..005` | 5 |
| Architecture | `REQ-P12-ARCH-001..007` | 7 |
| Portal database | `REQ-P12-DB-001..011` | 11 |
| Authentication and RBAC | `REQ-P12-AUTH-001..009` | 9 |
| Client conversations | `REQ-P12-CLIENT-001..009` | 9 |
| Human support | `REQ-P12-SUPPORT-001..009` | 9 |
| Admin portal | `REQ-P12-ADMIN-001..007` | 7 |
| Security dashboard | `REQ-P12-AUDITUI-001..007` | 7 |
| Password reset requests | `REQ-P12-PASSWORD-001..005` | 5 |
| Django/FastAPI integration | `REQ-P12-INTEG-001..010` | 10 |
| UI/UX | `REQ-P12-UI-001..007` | 7 |
| Docker/deployment | `REQ-P12-DOCKER-001..006` | 6 |
| Validation/governance | `REQ-P12-VAL-001..008` | 8 |
| **Total** |  | **100** |

## Requirements

- **REQ-P12-CORE-001:** Phase 12 MUST add the Django `web_portal` described
  here and MUST NOT implement Django before owner approval of this SDD.
- **REQ-P12-CORE-002:** Phase 12 MUST preserve the existing FastAPI/LangGraph
  agent runtime as the exclusive owner of agent routing, reasoning, RAG, OPS,
  Web, Security, Human Escalation decisions, and AUDIT persistence access.
- **REQ-P12-CORE-003:** Phase 12 MUST isolate web identity and portal state in
  `portal` without changing or taking ownership of `rag`, `ops`, or `audit`.
- **REQ-P12-CORE-004:** Phase 12 MUST preserve the browser trust boundary,
  least privilege, secret-safety, session/CSRF, object authorization, and
  output-security invariants in the approved security architecture.
- **REQ-P12-CORE-005:** Phase 12 MUST remain open until every requirement has
  passing acceptance evidence, project regressions are green, documentation is
  reconciled, and the owner explicitly reviews closure.

## Implementation order

The roadmap and implementation order are deliberately identical:

12.1 SDD foundation and web architecture; 12.2 Django service structure; 12.3
portal schema/data model; 12.4 users/authentication/RBAC; 12.5 login/session and
access control; 12.6 conversation/message persistence; 12.7 client portal/chat;
12.8 Human Escalation and support portal; 12.9 user administration; 12.10
Security Dashboard including its narrow internal AUDIT read boundary; 12.11
conversation administration; 12.12 password-reset workflow; 12.13 general
Django–FastAPI `/chat` integration; 12.14 security/authorization/E2E
tests; 12.15 Docker with Django; 12.16 final validation; 12.17 documentation,
Decision Log, and closure.

Some data contracts are designed before their dependent screens, but the
implementation gate order above is controlling. Changes to pre-existing
FastAPI, schema, or security contracts require a reviewed Phase 12 design
change before implementation.

## Owner-review boundary

The owner approved this SDD before implementation. Phases 12.1 through 12.13
are complete. Phase 12.13 owns the general /chat and agent-execution
integration. Phase 12.14 is next and must not begin before 12.13 receives
owner review.
Phase 12 and final closure remain open for their stated gates and owner review.

## Definition of Done

All 100 requirements in `12-validation-spec.md` have traceable passing
evidence; all client, support, and admin authorization tests pass; a complete
client-to-human-to-finalization E2E journey works; the security dashboard
matches filtered `audit.security_events` evidence; migrations are explicit and
schema-scoped; Docker operates with the existing PostgreSQL data preserved;
regressions for Phase 9–11 remain green; documentation and Decision Log are
updated only at the approved final roadmap stage; and the owner accepts the
Phase 12 closure evidence.
