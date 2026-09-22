# Phase 10 — Validation

Status: Phase 10.6 final validation complete. Counts are not acceptance criteria;
evidence demonstrates every applicable requirement.

## Requirements

- **REQ-P10-VAL-001:** Every Phase 10 requirement MUST have traceable unit, contract, integration, behavioral, or end-to-end evidence as appropriate; a passing aggregate count alone is insufficient.
- **REQ-P10-VAL-002:** Deterministic unit/contract tests MUST cover every approved event type and relevant resource category, typed/immutable event contracts, unsupported values, correlation, multiple secret-shaped inputs, bounded/generic safe content, and neutral classification.
- **REQ-P10-VAL-003:** Security behavioral and authenticated `/chat` tests MUST cover prompt injection, authorization-bypass attempts, protected secret/location requests, legitimate high-level architecture questions, `challenge-013`, `rag-019`, and `rag-025`; they MUST prove zero RAG, Web, OPS, and LLM invocation after a block.
- **REQ-P10-VAL-004:** Integration tests MUST prove successful sanitized audit persistence, audit-write failure fail-closed behavior, no secret in response, event, error, or loggable object, request/user correlation, and approved multi-event behavior when that mapping is implemented.
- **REQ-P10-VAL-005:** Real PostgreSQL validation MUST be explicitly opt-in, use synthetic credential-shaped values, verify `audit.security_events` via approved repository contracts, and leave no unintended residue. It MUST also verify that normal requests create zero security events and that no RAG/OPS records were unexpectedly mutated.
- **REQ-P10-VAL-006:** Phase 9 regression preservation, static compilation, dependency checks, diff/whitespace checks, secret scans of changed artifacts, and safe application/orchestration behavior are mandatory before a Phase 10 completion claim. Normal tests must not make unapproved external calls.

## Verification levels

| Level | Required evidence |
|---|---|
| Unit and contract | Classification mapping, sanitizer, immutable models, sink calls |
| Integration | Repository transaction, sanitized event persistence, failure isolation |
| Behavioral/orchestration | Security block precedes every prohibited capability |
| Authenticated `/chat` E2E | Safe response, correlation, challenge and RAG security cases |
| Opt-in real PostgreSQL | Committed sanitized record and cleanup/read-only safety evidence |
| Regression/static | Phase 9 preservation, compile, dependency, diff, secret-safe review |

## Definition of done

All applicable requirements pass with reproducible evidence. No raw protected content appears in source, fixtures, responses, prompts, logs/errors, or AUDIT records. No requirement may be marked complete merely because a future review UI, SIEM, or evaluation platform was not built; those are not Phase 10 baseline substitutes.

## Traceability

Authority: internal security policy; Phase 9 final validation discipline; challenge-013; `evaluation/rag/dataset-v1.yaml` cases `rag-019` and `rag-025`; the AUDIT physical model/repository contracts; and Harness governance principles for reproducible, non-production, secret-safe validation.

## Phase 10.6 final validation evidence

The final gate passed with 32 unique requirements defined, 32 requirements
passing, and no partial or blocked requirements. Traceability is direct or
shared across the following evidence:

| Family | Evidence | Result |
|---|---|---|
| CORE-001..006 | Router/orchestration, audit-boundary, fail-closed, and scope regression tests | PASS |
| CLASS-001..005 | `tests/test_security_classification.py` typed mapping, ordering, deduplication, and multi-threat coverage | PASS |
| REDACT-001..004 | Sanitization/audit tests for secret classes, bounds, fallback, and failure behavior | PASS |
| AUDIT-001..006 | `tests/test_security_audit.py`, repository tests, and opt-in real PostgreSQL typed single/multi-event and rollback tests | PASS |
| RESP-001..005 | `/chat` response, audit-unavailable, terminal-capability, neutral-wording, and challenge security tests | PASS |
| VAL-001..006 | This matrix, challenge/RAG security-case mapping, real PostgreSQL cleanup, Phase 9 regression, static and secret-safety checks | PASS |

Validation evidence: the deterministic security/orchestration/API suite passed
87 tests; the complete normal suite passed 437 tests with 31 opt-in tests
skipped, zero failures, and zero collection errors. Opt-in real PostgreSQL
audit/connectivity/cleanliness validation passed 5 tests, including typed
single-event persistence, multi-event persistence, repository read/review
contracts, rollback, and cleanup. The authenticated challenge-013 security
smoke completed normally and passed, with typed sanitized audit persistence and
no downstream provider path. `compileall`, `pip check`, core imports, OpenAPI/
transport tests, and `git diff --check` passed.

The evaluated security cases are mapped to existing deterministic coverage:
challenge-013 is covered by the authenticated security-block E2E test;
`rag-019` is covered by credential-request blocking and zero-capability
continuation tests; and `rag-025` is covered by protected-location/path blocking
and response-safety tests. Normal high-level PostgreSQL/architecture questions
remain outside `SECURITY_BLOCK`. Synthetic PostgreSQL rows were scoped and
cleaned; remaining synthetic validation rows are zero. No schema, migration,
table, index, constraint, production, RAG, or OPS mutation was introduced.
