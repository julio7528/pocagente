# Phase 10 — Sanitization and Redaction

Status: Phase 10.3 implementation complete and fully validated. The Phase 9
sanitizer was evolved in place; it was not rewritten from scratch.

## Contract

```text
raw protected input -> deterministic sanitizer -> allowlisted safe description
-> typed audit event -> AUDIT boundary
```

Raw request bodies, headers, provider diagnostics, graph state, and exception objects must never cross into persistent AUDIT storage.

## Requirements

- **REQ-P10-REDACT-001:** Sanitization MUST deterministically remove or replace credential/secret shapes, including connection strings, password/passphrase assignments, API-key shapes, bearer/access/refresh tokens, JWT-like values, private keys, cookies, secret fields, protected secret or environment paths, raw SQL-shaped sensitive content, and raw tracebacks/diagnostics where they would expose protected material.
- **REQ-P10-REDACT-002:** Sanitization MUST occur before `AuditRepository` receives an event. The repository receives an already-safe representation, never raw protected input or a recoverable prefix/suffix of a supplied secret.
- **REQ-P10-REDACT-003:** Multiple protected values in one input MUST each be handled. Output MUST be bounded and nonblank when present. If no concrete safe fragment can be guaranteed, the system MUST store only neutral generic safe text or a null sanitized-content value allowed by the physical model.
- **REQ-P10-REDACT-004:** Sanitization failures MUST not log or persist raw input. They MUST take the fail-closed path. Tests use synthetic credential-shaped placeholders only; real credentials, customer records, and secret locations are prohibited in fixtures and evidence.

## Phase 10.3 implementation evidence

The sanitizer performs deterministic global redaction for DSNs, credentials,
tokens, API keys, JWT-like values, private-key blocks, cookies/secrets,
protected paths, SQL-shaped content, and traceback/diagnostic blocks. It strips
blank input, bounds the safe result after redaction to 4000 characters, and
returns a neutral protected-request fallback when no safe fragment is
guaranteed. `SecurityAuditService` sanitizes before constructing the event
passed to the sink and converts sanitizer or sink failures to the controlled
unavailable result without logging or persisting raw input.

## Preserved information

Sanitization is not blanket deletion. It may retain a minimum neutral event description, approved event/resource category, correlation reference, action, and result when those values are safe. It must not reconstruct a requested secret or turn untrusted content into policy instructions.

## Traceability

Authority: internal security-policy audit/redaction rules; Phase 9 `REQ-P9-SEC-002`; DEC-166; `audit.security_events` field-security constraints; and the secret-safe persistence contract in `AuditRepository`.
