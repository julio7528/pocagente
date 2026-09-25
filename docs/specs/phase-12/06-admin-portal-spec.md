# Phase 12.9 and 12.11 — Admin Portal

## Navigation and authorization

Provide a dedicated Django admin portal for application workflows; Django's
built-in admin may remain a restricted operational tool but is not the
required product dashboard. Only active `ADMIN` users can access admin routes.
Each mutation repeats authorization and validates state server-side. Admin
navigation covers overview, users, security, conversations, and password-reset
requests. Admin access to chat history is an explicit administrative
capability; it does not grant agent/OPS authority.

## User management

Admins can search/filter/list users; create CLIENT, SUPPORT_AGENT, and ADMIN
accounts; activate/deactivate/block; change role under policy; and set/reset a
password through Django's hash API. Deactivation is preferred where history
references a user and sets `is_active=False`, the only account block gate.
There is no public self-registration. Role changes require an active ADMIN,
revoke the target's sessions, and are rejected while a SUPPORT_AGENT owns an
active `ASSIGNED` handoff for a HUMAN conversation. Password changes use
Django's hasher and revoke existing sessions. Prevent concurrent deactivation
or demotion from removing the last active ADMIN; users are not physically
deleted by normal administration. Show safe, actionable errors; never
redisplay passwords after submission. The first ADMIN is established only by
the explicit interactive `bootstrap_admin` operator command, which refuses
once any ADMIN exists and hashes the confirmed password immediately.

Phase 12.9 exposes a product-facing overview at `/admin-portal/` and a
user-management area at `/admin-portal/users/`; only those sections are
actionable in that stage. Phase 12.10 adds the read-only Security Dashboard at
`/admin-portal/security/` through the approved internal AUDIT read boundary.
Phase 12.11 adds conversation administration at
`/admin-portal/conversations/`. Phase 12.12 enables Password Request navigation
only with the complete administrator-managed recovery workflow. The
user list is ordered by normalized username and
UUID, paginated at 25 records, searchable by username, and filterable by the
three application roles and `ACTIVE`/`INACTIVE` state. Invalid filter values
are ignored. List/detail output is limited to username, application role,
active state, UUID, timestamps, and last login. No password hash or session
identifier is exposed. If an ADMIN changes their own role, active state, or
password, the current request session is flushed and the browser is sent to
login so response messaging cannot revive the revoked session.

Sections do not appear as actionable controls before their owning phase is
implemented.

The native Django `/admin/` remains a technical/development tool rather than
the product portal. Access requires an authenticated active application user
with role `ADMIN`. Django's `is_staff` flag is derived from/synchronized with
that role; `is_superuser` does not grant an application capability and remains
false for portal identities.

## Conversation administration

Phase 12.11 provides an active-ADMIN-only, read-only conversation history and
metadata view plus the portal-owned block, unblock, and soft-delete actions.
The list includes all six approved conversation states, including retained
`DELETED` tombstones, and is ordered by `updated_at DESC, id DESC`, with 25
records per page. Bounded title/owner search, an owner filter, status filter,
and an optional created-date range combine in one query and are preserved
across pagination. A date range requires both endpoints, is inclusive in the
configured Django timezone, and spans no more than 365 days. Invalid filter
values are shown as controlled form errors and do not run an unfiltered query.

An ADMIN may block only a lifecycle-consistent `ACTIVE`, `WAITING_HUMAN`, or
`HUMAN` conversation. The saved `status_before_block` is server-derived. Block
freezes all normal CLIENT, SUPPORT_AGENT, and agent writes without changing a
handoff. A `HUMAN` block preserves the existing `ASSIGNED` handoff and operator.
Only ADMIN may unblock; the service restores the saved valid state and clears
the saved field. Restoring `HUMAN` requires the same still-assigned operator
and leaves automation suspended. Invalid or inconsistent prior state is
rejected without a fallback. `CLOSED` is terminal and cannot be unblocked or
reopened.

Soft-delete requires explicit confirmation and sets `DELETED`, `deleted_at`,
and `deleted_by`; it removes the conversation from ordinary client/support
views but physically retains the conversation, messages, and handoff history.
There is no normal restore workflow. Since this phase does not define how an
active human lifecycle is cancelled or resolved by deletion, soft-delete is
rejected while its handoff is `WAITING` or `ASSIGNED`, including when that
conversation is administratively blocked. The handoff is not cancelled,
resolved, or reassigned. Safe deletion is permitted when no active handoff
exists, including a finalized `CLOSED` conversation with a `RESOLVED` handoff.

All mutations lock and recheck the conversation before the handoff, matching
the existing support-service lock order, and commit state/timestamp changes
atomically. Admin history displays the complete same-thread transcript in
chronological order. The ADMIN is an observer: there is no message composer,
message editing, or agent invocation. Admin actions update portal-owned state
and timestamps; ordinary administrative events are not inserted into
`audit.security_events` unless a later approved security/governance policy
specifically requires it.

## Requirements

- **REQ-P12-ADMIN-001:** The application MUST provide a dedicated ADMIN-only
  portal; built-in Django Admin alone MUST NOT be treated as satisfying the
  required user, security, conversation, and reset-request experiences.
- **REQ-P12-ADMIN-002:** ADMIN users MUST be able to list, search, filter,
  create, activate/deactivate, change approved roles, and set/reset passwords
  for users through server-authorized workflows.
- **REQ-P12-ADMIN-003:** User administration MUST preserve historical
  references through deactivation rather than routine physical deletion and
  MUST protect the last active ADMIN from accidental lockout.
- **REQ-P12-ADMIN-004:** Active ADMIN users MUST be able to search, filter,
  paginate, and inspect conversation owner, status, permitted metadata, and
  the complete immutable same-thread message history, including retained
  `DELETED` tombstones.
- **REQ-P12-ADMIN-005:** Active ADMIN users MUST be able to block and unblock
  only lifecycle-consistent nonterminal conversations by preserving and
  restoring the server-recorded prior state, and logically delete only when
  no `WAITING` or `ASSIGNED` handoff would be orphaned. Blocking freezes normal
  writes without changing the handoff; deletion records its actor/time and
  hides the conversation from normal client/support access without physical
  erasure or a normal restore workflow.
- **REQ-P12-ADMIN-006:** Every admin page and mutation MUST verify an active
  ADMIN session on the server; guessed URLs and forged form roles MUST NOT
  grant admin access.
- **REQ-P12-ADMIN-007:** Portal administration MUST NOT create ordinary
  application events in `audit.security_events` or use that table as a general
  admin log; any future portal audit mechanism requires separate approval.

`BLOCKED` is an administrative suspension distinct from terminal business
`CLOSED`. `DELETED` is a physically retained tombstone, not a restore-capable
state.
