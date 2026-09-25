# Phase 12.12 — Administrator-Managed Password Reset Requests

## User journey

The login page offers “Esqueci minha senha”. The requester supplies the
approved account identifier, reviews and confirms the request, and receives a
generic confirmation that the request was forwarded to an administrator. The
public response must not reveal whether the username exists, is active, or is
blocked. Create a minimal `PasswordResetRequest` only where policy permits;
unknown-account submissions may be handled with a non-identifying safe outcome
without creating an enumerable record.

For this POC, only a known active account may create a request row. A known
inactive account and an unknown identifier both receive the same public
confirmation and create no row; an inactive account remains blocked by the
existing `is_active` access policy. Repeated confirmed requests for a user
with an existing `OPEN` item reuse the oldest such item, serialized on the
requester account row. This coalesces duplicate work without adding a schema
constraint. A later request may create a new row after the earlier item reaches
`RESOLVED` or `REJECTED`.

An ADMIN-only queue lists `OPEN` requests and permits `RESOLVED` or `REJECTED`.
Resolution consists of an authenticated admin setting a new password through
Django's approved hash setter, then marking the request resolved in a
transactional workflow. The new password exists only in request memory and the
User hash; it is never written into the request row, session, audit field,
application log, template context, or success response. User is prompted to
log in with the administrator-provided reset outcome through the approved
internal channel; no email delivery is assumed.

Only ADMIN may change passwords in this POC. There is no self-service password
change, tokenized email flow, or direct password reveal/recovery.

The ADMIN queue defaults to `OPEN`, supports status and bounded requester
username filters, and uses 25-row pages ordered oldest-first by
`created_at ASC, id ASC`. Detail is read-only for request metadata except for
the resolve/reject actions while the item is `OPEN`. Resolve and reject lock
the request row, recheck `OPEN`, and produce one terminal result; stale or
concurrent actions receive a controlled conflict. Password resolution reuses
the Phase 12.4 account password service so hashing, validation, and session
revocation have one implementation.

## Requirements

- **REQ-P12-PASSWORD-001:** Login MUST expose a forgot-password request path
  that collects the approved account identifier, requires confirmation, and
  creates a minimal administrator work item where applicable.
- **REQ-P12-PASSWORD-002:** Public reset-request responses MUST be generic and
  must not disclose whether an account exists, is active, or is blocked.
- **REQ-P12-PASSWORD-003:** Reset requests MUST use `OPEN`, `RESOLVED`, and
  `REJECTED` lifecycle states and be visible/actionable only to authorized
  ADMIN users.
- **REQ-P12-PASSWORD-004:** Only ADMIN may set/reset a user password in the
  POC; Django's password hash mechanism MUST be used and plaintext MUST never
  be persisted, logged, audited, rendered after submission, or placed in a
  reset-request record.
- **REQ-P12-PASSWORD-005:** Resolving a request MUST record resolver and
  resolution time, update the target user's password hash safely, preserve a
  non-enumerating user outcome, and handle repeated submissions/idempotent
  admin actions without duplicating a completed reset.
