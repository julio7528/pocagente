# Phase 10 — Audit Runtime

Status: Phase 10.4 implementation complete and fully validated. This document
extends the approved Phase 9 audit slice; it does not approve a competing
service, repository, or table.

## Approved runtime boundary

`SecurityAuditService` constructs immutable typed sanitized events and delegates through the provider-neutral `SecurityAuditSink`. The PostgreSQL adapter uses `PostgresDatabase.transaction()` and delegates exclusively to `AuditRepository.write_sanitized_security_event(...)`. Agents, Router, LangGraph state, and HTTP handlers do not receive an AUDIT connection or issue SQL.

## Requirements

- **REQ-P10-AUDIT-001:** Events MUST be typed and immutable, and contain only physically approved fields: event time, approved event type, source component, optional authenticated user/request correlation, optional approved resource category, sanitized content, approved protective action/result, and review state. Database-generated identity and persistence timestamp remain database owned.
- **REQ-P10-AUDIT-002:** The runtime MUST use `SecurityAuditService`, the sink abstraction, `PostgresSecurityAuditSink`, the existing transaction boundary, `AuditRepository`, and `audit.security_events`; it MUST NOT create a second repository/table, generic SQL adapter, or direct agent database access.
- **REQ-P10-AUDIT-003:** `source_component`, authenticated user correlation, request correlation, action, result, and review state MUST respect the exact physical constraints. Correlation is opaque and nullable when unavailable; it is not a request payload, foreign key, or authority grant.
- **REQ-P10-AUDIT-004:** Normal requests MUST create no security event. A protected request persists the policy-required sanitized event(s) only after deterministic classification and before the normal blocked outcome is represented as handled. Multi-event behavior follows `REQ-P10-CLASS-004`.
- **REQ-P10-AUDIT-005:** Audit persistence failure MUST remain blocked and be observable only as a controlled safe unavailable outcome. It MUST NOT claim an event was recorded or resume retrieval, tools, Web Search, or provider execution; database diagnostics and SQL remain internal.
- **REQ-P10-AUDIT-006:** Existing repository lookup, request-correlation, unreviewed listing, and review-metadata update capabilities remain the approved persistence surface. A review UI, reviewer authorization model, queue, retention scheduler, and public API are deferred unless separately authorized.

## Approved values and transaction behavior

The physical model is authoritative for event type/resource category values, actions (`BLOCK`, `DENY_ACCESS`, `REDACT`, `SAFE_RESPONSE`, `ESCALATE`), results (`SUCCESS`, `PARTIAL`, `ERROR`), review states (`UNREVIEWED`, `REVIEWED`), and review timestamp consistency. Repository methods do not independently commit; the application-owned transaction controls atomicity.

## Phase 10.4 implementation evidence

Router-owned typed semantics are forwarded unchanged through the orchestration
security terminal. The existing `SecurityAuditService` sanitizes once and
constructs one immutable event per supplied semantic. The existing PostgreSQL
sink persists the batch through one `PostgresDatabase.transaction()` using the
existing `AuditRepository.write_sanitized_security_event(...)` method, so a
multi-event request commits all events or none. Empty semantics, sanitization
failure, and sink failure take the controlled unavailable path without raw
content or partial event IDs. Existing repository lookup, correlation,
unreviewed-listing, and review-update methods remain unchanged; no new schema,
table, repository, review API, or authorization model was introduced.

Real PostgreSQL validation proved single typed-event persistence, multi-event
correlation and sanitization, controlled transaction rollback with zero
residue, repository review operations, and scoped cleanup with zero synthetic
rows remaining.

The authenticated real `/chat` challenge-013 security test completes normally,
persists the typed sanitized events, verifies the safe response and protected
downstream boundary, and removes all uniquely scoped synthetic rows.

## Traceability

Authority: `docs/database-physical-model.md`, `docs/repository-contracts.md`, `docs/database-mapping.md`, DEC-141 (repository contract) and DEC-166 (Phase 9 audit integration), plus the internal security policy.
