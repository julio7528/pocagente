# Phase 10 — Security / Audit Runtime

Status: **Phase 10.1 SDD Foundation, Phase 10.2 deterministic security
detection/classification, Phase 10.3 Sanitization / Redaction, Phase 10.4
Audit Runtime, Phase 10.5 Security Policy Response, and Phase 10.6 Final
Validation / Closure are complete and fully validated. Phase 10 SECURITY /
AUDIT RUNTIME is complete. Phase 11 Evaluation Runner is next.** Phase 9 is
complete, including its narrow protected-request audit integration.

## Purpose and authority

This specification defines the reviewed contract for expanding the Security / Audit Runtime without replacing the approved Phase 9 security path. Authority, in descending order, is the internal security policy, approved project and physical-model documentation, approved durable decisions, this Phase 10 SDD, and implementation/tests. Historical Harness setup material is read-only governance reference only; it does not determine current project status.

Phase 10 consumes the Phase 9 baseline:

```text
authenticated /chat -> Router SECURITY_BLOCK -> SecurityAuditService
-> sanitization -> PostgresSecurityAuditSink -> PostgresDatabase.transaction()
-> AuditRepository.write_sanitized_security_event(...) -> audit.security_events
```

The baseline is working and remains the only approved protected-request audit integration until a reviewed Phase 10 implementation extends it.

## Scope and non-goals

Phase 10 specifies deterministic classification metadata, sanitization, sanitized AUDIT persistence, safe policy responses, and validation. It does not approve a new schema/table/migration, generic logging, a new LLM classifier, SIEM, alerting, retention scheduler, IAM/RLS/Vault, Django UI, queues, WebSockets, ITSM, WhatsApp, RAG/OPS/provider redesign, or secret discovery. AUDIT is security/governance evidence only; ordinary OPS execution remains in `ops`, and knowledge remains in `rag`.

## Architecture principles

- The Router remains the authoritative protected-request decision boundary.
- Security decisions and audit construction are application-owned and deterministic; an LLM must not reclassify a protected request.
- An effective block prevents RAG, Web Search, OPS tools, and provider/LLM execution. Audit failure remains blocked and safe.
- The existing `SecurityAuditService`, sink abstraction, database transaction, `AuditRepository`, and `audit.security_events` are extended, not duplicated.
- Real or credential-shaped content is sanitized before persistence. If safe sanitization cannot be guaranteed, raw content is not stored.
- Events use neutral terminology; the system records a policy event, not an inferred accusation about the requester.
- Normal development validation uses deterministic synthetic fixtures. Production access and unapproved external operations remain prohibited.

## Requirement-ID convention

Requirement identifiers are immutable. They are never reused for a different contract; a later supersession must name the prior identifier explicitly.

| Family | Specification | Purpose |
|---|---|---|
| `REQ-P10-CORE-###` | this file | Cross-cutting architecture and safety |
| `REQ-P10-CLASS-###` | 01 | Detection, Router ownership, typed semantics |
| `REQ-P10-REDACT-###` | 02 | Deterministic redaction before storage |
| `REQ-P10-AUDIT-###` | 03 | Typed AUDIT runtime and persistence |
| `REQ-P10-RESP-###` | 04 | Safe protected-request response behavior |
| `REQ-P10-VAL-###` | 05 | Requirement-traceable validation |

## Core requirements

- **REQ-P10-CORE-001:** Phase 10 MUST preserve and extend, not replace, the approved Phase 9 `SECURITY_BLOCK -> SecurityAuditService -> AuditRepository` integration.
- **REQ-P10-CORE-002:** The Router MUST remain the authoritative routing and protected-request decision boundary; Phase 10 MUST NOT introduce a second or LLM-based security classifier.
- **REQ-P10-CORE-003:** Security/governance events MUST use the existing `audit.security_events` model and `AuditRepository`; agents and endpoints MUST NOT execute AUDIT SQL directly.
- **REQ-P10-CORE-004:** A protected request and an unavailable audit boundary MUST fail closed, with no RAG, Web Search, OPS, or provider continuation.
- **REQ-P10-CORE-005:** Security behavior MUST preserve explicit authorization, untrusted-data, provider-neutral, secret-safe, and neutral-terminology invariants from the internal policy and Phase 9.
- **REQ-P10-CORE-006:** Implementation evidence MUST be reproducible, use synthetic secret-shaped fixtures, avoid production access, and preserve unknown material decisions rather than guessing them.

## Dependency map and implementation order

1. **10.1:** this specification foundation (complete; documentation only).
2. **10.2:** deterministic classification/event-metadata expansion under `01-security-detection-classification-spec.md` (complete and validated).
3. **10.3:** reviewed sanitization/redaction expansion under `02` (complete and validated).
4. **10.4:** reviewed typed audit-runtime expansion under `03` (complete and validated).
5. **10.5:** reviewed response and fail-closed integration under `04` (complete and validated).
6. **10.6:** complete validation under `05` and regression closure (complete and validated).

No numbered implementation step is authorization to start work without its reviewed task and applicable requirements.

## Traceability matrix

| Requirement range | Primary authority | Planned evidence |
|---|---|---|
| CORE-001–006 | Phase 9 specs; DEC-166; security policy; repository/physical contracts | Architecture, regression, and boundary tests |
| CLASS-001–005 | Security policy; Router contract; physical AUDIT model | Deterministic classification and correlation tests |
| REDACT-001–004 | Security policy; DEC-166; physical field security | Sanitizer contract and persistence tests |
| AUDIT-001–006 | Physical model; repository contracts; DEC-141 and DEC-166 | Repository/sink, transaction, and opt-in PostgreSQL tests |
| RESP-001–005 | Security policy; Phase 9 `/chat` and orchestration contracts | Authenticated HTTP/security behavioral tests |
| VAL-001–006 | challenge-013; rag-019; rag-025; validation discipline | Unit, integration, E2E, real-DB, and static gates |

## Scenario mapping

- `challenge-013` validates the protected credential-request route, block, sanitization, approved audit persistence, and safe response.
- `rag-019` and `rag-025` validate that sensitive-access requests are blocked rather than retrieved, reconstructed, or exposed.
- Other Phase 9 scenarios remain regression evidence that AUDIT does not alter normal RAG, Web, OPS, cooperation, or Human Escalation behavior.

## SDD change control and definition of done

Requirements cannot be weakened to fit implementation. Any material conflict with the policy, physical model, repository contract, or approved decision must be reported before implementation. Completion requires every applicable requirement to have passing, reproducible evidence; protected data must be absent from responses, prompts, logs/errors, fixtures, and persisted audit content; real PostgreSQL validation must be opt-in; and regression/static/diff checks must pass. Broader unapproved security-platform work remains deferred.
