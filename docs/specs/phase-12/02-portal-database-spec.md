# Phase 12.3 — Portal Database and Persistence Model

## Schema and migration ownership

The database becomes four domain schemas: `rag` (governed knowledge), `ops`
(observed automation facts), `audit` (security/governance evidence), and
`portal` (web identity and application state). Phase 12 adds no cross-domain
ownership. Portal records may contain opaque references/correlation values;
they do not copy OPS or AUDIT facts.

The recommended migration boundary is explicit and sequential:

1. a new immutable native SQL migration `0007_portal_schema.sql` creates only
   the `portal` schema;
2. Django migrations create and evolve Django framework and portal tables
   within `portal` only;
3. both migration steps are explicit operator/admin actions, never startup
   side effects;
4. Django's connection/search-path and migration recorder must be configured
   and tested so every framework table, including `django_migrations`, is in
   `portal`.

For this POC, Django uses the same PostgreSQL database and principal already
used by the project. Migration `0007` creates no role, user, password, grant,
table, or other-schema object. Django code and ORM models remain scoped to
`portal`; AUDIT reads continue through FastAPI/AuditRepository. A separate
least-privilege principal and grants are future production-hardening work, not
a Phase 12.3 blocker.

The application table names are explicitly `portal.users`,
`portal.conversations`, `portal.messages`, `portal.support_handoffs`, and
`portal.password_reset_requests`. Django framework tables keep Django's
standard names resolved only through the `portal` search path.

Applied native migrations remain immutable. No existing schema/table is
renamed, recreated, or altered to accommodate Django. The POC does not create
or alter PostgreSQL roles or grants; Django's ORM connection is restricted to
the `portal` search path and application code has no direct RAG/OPS/AUDIT
repository access. Separate least-privilege credentials/grants remain future
production hardening.

## Logical model and relationships

```text
portal.users (custom Django auth user)
  1 ─── N portal.conversations (owner)
              1 ─── N portal.messages
              1 ─── 0..1 portal.support_handoffs (one lifetime human-support cycle)
                          N ─── 0..1 portal.users (assigned support user)
  1 ─── N portal.password_reset_requests (requester, nullable after policy review)

Django framework tables, including sessions/content types/permissions/migration
recorder (and admin log if enabled), also reside in portal.
```

Use Django's custom auth model from the first migration. Every portal
application entity (User, Conversation, Message, SupportHandoff, and
PasswordResetRequest) uses a UUID primary key. Framework-owned keys may follow
Django defaults. The five application models set explicit clean `db_table`
names; Django's PostgreSQL connection fixes `search_path` to `portal` so both
application and framework tables resolve there, without falling through to
`public`, `rag`, `ops`, or `audit`.

All application timestamps representing instants use timezone-aware
`TIMESTAMPTZ` semantics and are stored in UTC; localized display is a portal
presentation concern. `User.username` is trimmed and lowercased before
persistence; exact uniqueness satisfies Django's auth contract and an
additional lower/trim unique constraint protects direct ORM writes from
case/whitespace duplicates. The
conversation owner FK is required and restrictive; message/handoff child
history is preserved if a user is deactivated. A message sender user is
required for CLIENT and SUPPORT_AGENT senders and null for AGENT/SYSTEM. A
handoff assignee is null while WAITING and required while ASSIGNED; resolver
is null until terminal resolution. `PasswordResetRequest.requester` is
required; unknown-account submissions do not create a row and receive the
same public confirmation as known accounts. No new password, reset token, or
plaintext credential field is permitted.

## Model inventory

| Model/table family | Required attributes and constraints |
|---|---|
| `User` | UUID technical key; unique normalized username/login; Django password hash; role `ADMIN/CLIENT/SUPPORT_AGENT`; active/blocked state; created/updated timestamps; Django last-login; account state changes invalidate or revalidate sessions. No plaintext password. |
| `Conversation` | UUID; explicit table `conversations`; required owner FK; status exactly `ACTIVE/WAITING_HUMAN/HUMAN/CLOSED/BLOCKED/DELETED`; nullable `status_before_block` only while BLOCKED; deterministic title `VARCHAR(50)` from first CLIENT message; created/updated timestamps; `deleted_at` and `deleted_by` for tombstoning. Owner/status/update access path. |
| `Message` | UUID; explicit table `messages`; conversation FK; sender class `CLIENT/AGENT/SUPPORT_AGENT/SYSTEM`; sender user required for CLIENT/SUPPORT_AGENT and null for AGENT/SYSTEM; immutable body; created timestamp; conversation-scoped client idempotency UUID unique for CLIENT turns; processing outcome/status for pending/controlled failure. Ordered by `(conversation, created_at, id)`. |
| `SupportHandoff` | UUID; explicit table `support_handoffs`; unique conversation FK (one lifecycle ever); status `WAITING/ASSIGNED/RESOLVED/CANCELLED`; requested/accepted/resolved timestamps; assigned support user nullable until acceptance; resolved-by nullable; approved escalation reason and sanitized handoff reference/package fields only. |
| `PasswordResetRequest` | UUID; required requester FK; status `OPEN/RESOLVED/REJECTED`; created/resolved timestamps; nullable resolver FK; nullable safe administrative note with no password. Create a row only for a known account; unknown-account submission receives identical public text without storing the submitted identifier. |
| Django framework records | Session, content type, permission, migration recorder, and optional admin-log tables use the `portal` schema. Disable any unused framework feature only through explicit approved settings, not by allowing its table into another schema. |

Conversation title is derived once from the first CLIENT message after trimming
surrounding whitespace and collapsing whitespace runs. If normalized length is
at most 50, retain it; otherwise store its first 47 characters plus `...`.
Do not use an LLM, pad short titles, or regenerate on later turns.

Message bodies and conversation history are sensitive customer content. Apply
least-privilege reads, safe rendering, retention/access policy review, and
never copy full conversations into `audit.security_events`. Completed
messages are immutable for CLIENT, SUPPORT_AGENT, and ADMIN in normal flows;
correction is a new message, never mutation of historical body content.

## Status and integrity rules

Conversation statuses: `ACTIVE`, `WAITING_HUMAN`, `HUMAN`, `CLOSED`,
`BLOCKED`, `DELETED`. `WAITING_CONFIRMATION` is represented as `ACTIVE` with a
pending confirmation indicator, not as a second portal lifecycle state. Admin
block stores the prior state in `status_before_block` and freezes CLIENT,
SUPPORT_AGENT, and agent writes. Only ADMIN may unblock; it restores the prior
valid state, retaining the same HUMAN assignment and keeping AI suspended when
the prior state was HUMAN. `DELETED` is an irreversible tombstone through
normal portal workflows. `BOT` maps to `ACTIVE`; confirmed `WAITING_HUMAN`
maps to `WAITING_HUMAN`; accepted operator ownership maps to `HUMAN`; only
assigned human finalization maps `HUMAN -> CLOSED`. The portal does not expose
a return-to-automation transition. A conversation supports one human-support
lifecycle only and cannot be escalated again after completion.

Handoff statuses: `WAITING`, `ASSIGNED`, `RESOLVED`, `CANCELLED`. `WAITING`
means user-confirmed and available for claim, not yet human-owned. Atomic
conditional update/row locking claims the conversation's sole handoff and
assigns the authenticated support user. The successful claim and conversation
`WAITING_HUMAN -> HUMAN` update share one transaction. Stale competing claims
receive a safe conflict. Finalization changes the handoff to `RESOLVED` and
the conversation to terminal `CLOSED`; no second handoff can be created.

Reset statuses: `OPEN -> RESOLVED | REJECTED`; terminal requests are not
reopened by mutating history. FKs use restrictive semantics where deletion
would erase business history. Conversation deletion is a tombstone; related
messages/handoffs remain. Physical deletion, cascade erasure, and automatic
retention purges are not the normal POC behavior.

## Access paths and indexes

Use unique username/login; conversations by `(owner_id, status, updated_at
DESC)` excluding logically deleted rows from normal client lists; messages by
`(conversation_id, created_at, id)`; waiting handoffs by status/request time;
assigned handoffs by `(assigned_user_id, status, updated_at)`; reset requests
by `(status, created_at)`; administrative conversation search fields only
where defined and justified. Reuse primary/unique indexes. Final index DDL is
approved during schema review against actual query plans; do not add speculative
indexes. AUDIT dashboard uses existing AUDIT indexes through FastAPI, not
portal indexes.

## Requirements

- **REQ-P12-DB-001:** Portal-owned records and all Django framework tables
  MUST reside in PostgreSQL schema `portal`; application tables MUST use the
  explicit names `users`, `conversations`, `messages`, `support_handoffs`, and
  `password_reset_requests`; `rag`, `ops`, and `audit` remain separately owned.
- **REQ-P12-DB-002:** The custom Django User model MUST be selected before the
  first Django migration and MUST use a stable technical identifier, unique
  login, password hash, one approved role, account state, timestamps, and
  last-login data as appropriate.
- **REQ-P12-DB-003:** The portal model MUST include the required user,
  conversation, message, support-handoff, password-reset-request, and needed
  Django framework records using UUID primary keys for all five application
  entities; no notifications table is added without a proven requirement or
  default ADMIN is seeded.
- **REQ-P12-DB-004:** A conversation MUST be owned by a client, use only the
  approved lifecycle states, have a 50-character deterministic first-message
  title, creation/update timestamps, block restoration state, and logical
  deletion actor/time; technical IDs MUST be opaque and stable.
- **REQ-P12-DB-005:** Messages MUST reference the same conversation through
  AI and human handling, identify sender class and applicable sender user,
  have deterministic chronological ordering, and preserve historical content
  as append-only records.
- **REQ-P12-DB-006:** Each persisted client turn MUST have a conversation-
  scoped idempotency key so retries cannot create duplicate transcript
  messages; ambiguous backend execution may be retried only under the
  integration policy.
- **REQ-P12-DB-007:** Handoff records MUST persist state, requested/accepted/
  resolved timestamps, assigned support user, resolver where applicable, and
  safe correlation/context; a conversation MUST have at most one handoff for
  its lifetime and human resolution MUST close that conversation.
- **REQ-P12-DB-008:** Password reset request records MUST store lifecycle and
  requester/admin resolution metadata only and MUST never store plaintext
  passwords, password hashes outside the User record, or reset secrets.
- **REQ-P12-DB-009:** Django framework tables, including migration recorder
  and sessions, MUST be placed within `portal`. The POC uses the existing
  shared PostgreSQL principal; separate least-privilege credentials are future
  production hardening. Django ORM/code MUST NOT access `rag`, `ops`, or
  `audit`; AUDIT remains behind FastAPI/AuditRepository.
- **REQ-P12-DB-010:** Conversation deletion MUST be a logical tombstone with
  deletion time and ADMIN actor; normal workflows MUST provide no restore and
  MUST preserve messages/handoff rows through restrictive history-preserving
  references.
- **REQ-P12-DB-011:** Schema constraints and indexes MUST support the approved
  owner/status/update, conversation/message-order, handoff-queue/assignment,
  and reset-request access paths without speculative schema-wide indexing.
