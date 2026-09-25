# Phase 12.7–12.12 — UI/UX and Frontend

## Technology decision

Use Django Templates for server-rendered pages, semantic HTML, scoped CSS, and
ordinary same-origin JavaScript for chat polling and interactive filters. Do
not add React, Vue, Angular, a SPA build pipeline, or Django Channels for the
initial POC. HTMX is optional only if a concrete view becomes simpler; it is
not a required dependency. Use a lightweight chart library (Chart.js is the
initial candidate) self-hosted as a pinned static asset rather than a public
CDN. No visual pixel dimensions are contractual; consistent hierarchy,
responsive behavior, keyboard accessibility, and clear state feedback are.

## Shared shell and screen inventory

Authenticated screens use a Header, role-specific Sidebar, main content, and
Footer. Login/forgot-password use a simpler public Header/Footer shell.
Support and client views share the same conversation/message presentation but
not authorization rules. Mobile/narrow layouts collapse the sidebar without
changing accessible navigation semantics.

| Screen | Role / route | Purpose, major components, actions | Empty / error / authorization |
|---|---|---|---|
| Login | Public `/login/` | Username, password, Enter/Login; role-owned success destination | Generic invalid credentials; CSRF; inactive users denied; no registration, Remember Me, or unfinished password-recovery control |
| Forgot Password Request | Public `/password-reset/request/` | Account identifier, confirmation, submit | Same generic confirmation for known/unknown accounts; bounded service error |
| Client Chat / Conversation | CLIENT `/chat/`, `/chat/<uuid>/` | Header/sidebar/main/footer, ordered messages, state badge, input/send, new conversation | New/empty prompt; controlled error; input allowed in ACTIVE, WAITING_HUMAN, and HUMAN under portal persistence policy; owner-scoped |
| Client History / Sidebar | CLIENT `/chat/` sidebar | New conversation, owned active/recent history, account/logout | Empty history; excludes DELETED; only owner records |
| Waiting Support Queue | SUPPORT_AGENT `/support/queue/` | Waiting count, sortable queue, status/request summary, accept action | Explicit no waiting cases; polling/network state; active agent only |
| Active Human Conversation | Assigned SUPPORT_AGENT `/support/conversations/<uuid>/` | Same thread, sanitized handoff summary, message form, return/finalize | No unassigned access; HUMAN owner required; stale claim conflict |
| Finalized Conversations | SUPPORT_AGENT `/support/finalized/` | Permitted resolved history and search | Empty history; access per support policy |
| Admin Dashboard / Navigation | ADMIN `/admin-portal/` | Navigation and high-level portal links | Empty metrics/API failure; active ADMIN only |
| User Management | ADMIN `/admin-portal/users/` | Search/filter/list/create/activate/block/change role/reset password | No matching users; validation and conflict states; active ADMIN only |
| Security Dashboard | ADMIN `/admin-portal/security/` | Cards, charts, date/type/source/user filters, event list/detail | No events, bounded-query errors; sanitized FastAPI data only |
| Conversation Management | ADMIN `/admin-portal/conversations/` | Search, inspect history/status/owner, block/unblock, soft-delete | Empty results; safe object state; active ADMIN only |
| Password Reset Requests | ADMIN `/admin-portal/password-requests/` | Open queue, inspect minimized request, set password, resolve/reject | Empty queue; no plaintext redisplay; active ADMIN only |

Each page provides a useful empty state, loading feedback, validation feedback,
and a safe recoverable error state. Errors do not expose server internals.
Controls remain operable by keyboard; forms have labels and focus order; state
is not conveyed by color alone; charts have text/table alternatives.

Phase 12.7 uses server-rendered forms and a small same-origin script for
submission feedback and accidental double-submit prevention. The Django
persistence service provides the authoritative idempotency guard. Full
authorized transcript history is shown even when a message exceeds the future
6,000-character FastAPI context budget. Pending and failed message states are
displayed without an inactive retry control; transport retries are Phase 12.13.

Phase 12.5 implements only the public login shell, controlled HTTP 403, and
minimal protected role landing placeholders needed to validate authentication.
The Forgot Password entry point is introduced with its complete workflow in
Phase 12.12, never as a dead Phase 12.5 link. CLIENT, SUPPORT_AGENT, and ADMIN
land at `/chat/`, `/support/`, and `/admin-portal/` respectively. These
placeholders did not implement the later chat, support queue, or product admin
screens. Phase 12.9 replaces the ADMIN placeholder with the product-facing
user-management overview/list/create/detail routes. Its list uses a bounded
25-record page size with username search and role/state filters. Security,
Conversation, and Password Request navigation is omitted until those features
are implemented; Django's built-in `/admin/` remains separate technical
tooling.

## Requirements

- **REQ-P12-UI-001:** The initial portal MUST use Django Templates, ordinary
  JavaScript and CSS, and same-origin server requests; a SPA framework and
  WebSockets are out of scope absent new approval.
- **REQ-P12-UI-002:** The UI MUST provide all twelve screens, routes, role
  ownership, actions, empty/error states, and access conditions in the screen
  inventory.
- **REQ-P12-UI-003:** Logged-in layouts MUST provide Header, role-specific
  Sidebar, main content, and Footer, with client history/new-conversation and
  account/logout controls where applicable.
- **REQ-P12-UI-004:** Chat, support queue, message refresh, and dashboard
  filters MUST use accessible same-origin requests with stable IDs/cursors and
  clear loading, completion, no-result, and safe error feedback.
- **REQ-P12-UI-005:** Dashboard charts MUST use a lightweight pinned,
  self-hosted chart library (Chart.js candidate); third-party runtime CDN code
  MUST NOT be required for core portal operation.
- **REQ-P12-UI-006:** The portal MUST be responsive and meet baseline
  accessibility expectations for semantic landmarks, labels, keyboard use,
  focus, contrast, and non-color-only status presentation.
- **REQ-P12-UI-007:** Role/state-dependent controls MUST reflect the current
  server state, but hiding or disabling a control MUST NOT replace backend
  route/object authorization.
