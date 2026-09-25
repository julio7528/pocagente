# Phase 12.4–12.5 — Authentication, Sessions, and RBAC

## Identity and role model

Use a custom Django User model from the initial migration. The application role
field is a closed choice with exactly `ADMIN`, `CLIENT`, and `SUPPORT_AGENT`;
it is server-owned and cannot be changed by form/API input from a browser.
There is no public self-registration. Only an active ADMIN may create CLIENT,
SUPPORT_AGENT, or additional ADMIN identities through a server-side
administration service. Account availability is represented only by Django's
`is_active`: true means enabled; false means blocked/deactivated. No duplicate
generic blocked flag is permitted.

| Role | Allowed areas | Denied areas |
|---|---|---|
| `CLIENT` | own client portal, own conversations, own reset request; same read-only OPS query capabilities as SUPPORT_AGENT through authenticated `/chat` | all support-agent and admin routes; other users' conversations |
| `SUPPORT_AGENT` | waiting queue, assigned HUMAN conversations, permitted finalized support history | admin routes; unassigned HUMAN content; client account/ownership bypass |
| `ADMIN` | admin dashboard, user/conversation/reset administration, sanitized security dashboard | no automatic OPS authority from ADMIN role; no direct RAG/OPS/AUDIT SQL |

Support-agent portal access is limited to queue items and conversations
assigned to that operator, with explicitly approved read-only finalized access
if required. For authenticated `/chat` execution, the owner-approved policy
grants active CLIENT and authorized SUPPORT_AGENT principals the same read-only
OPS query capability. This can return protocol records across the OPS dataset;
current OPS records are not linked to a portal account. The trusted claim is
derived by Django server code and is never a browser claim. ADMIN does not
receive OPS authorization. An ADMIN may inspect conversations and metadata as
required for administration; all views remain server-authorized.

## Login and session policy

Login uses Django's supported authentication backend and password hashing
mechanisms. Use Django session authentication with Secure/HttpOnly cookies in
production-like deployment, SameSite protection, CSRF on state-changing forms,
session rotation at login, logout invalidation, a 30-minute inactivity timeout,
an independent eight-hour absolute lifetime, and generic login failure
responses. Authenticated activity refreshes only the inactivity timestamp and
cannot extend the absolute lifetime. There is no Remember Me option. An inactive user cannot
establish or continue a protected session. Deactivation, role changes, and
password changes invalidate all existing sessions for that user. Role changes
are ADMIN-only and are refused while the target SUPPORT_AGENT owns an active
`ASSIGNED` handoff for a HUMAN conversation.

The browser login endpoint is `/login/` and logout is CSRF-protected `POST
/logout/`. Successful role landings are `/chat/` for CLIENT, `/support/` for
SUPPORT_AGENT, and `/admin-portal/` for ADMIN. Anonymous protected requests
redirect to `/login/`; an authenticated user requesting another role's area
receives a controlled HTTP 403 without being silently redirected. Invalid
username, invalid password, malformed login, and inactive account outcomes use
the same public message, `Usuário ou senha inválidos.`, and do not automatically
block the account. An unavailable or revoked session is cleared and returns a
generic login message without disclosing the administrative cause.

Phase 12.5 exposes no registration, Forgot Password, or Remember Me control.
The complete Forgot Password UI and workflow remain deferred to Phase 12.12.

Protect the invariant that at least one active ADMIN remains, including under
concurrent deactivation/demotion attempts. Administrative operations that can
reduce the active ADMIN count use a common PostgreSQL transaction-level lock
before checking and changing identity state. Physical user deletion is not a
normal operation; preserve historical references through deactivation.

The first ADMIN account is provisioned only through the explicit operator-run
command `python apps/web_portal/manage.py bootstrap_admin` after portal
migrations. The command prompts securely for username, password, and
confirmation; refuses when an ADMIN already exists; and never uses default
credentials, logs/retains plaintext, or runs during application startup or
migrations. Password validation and Django's password hasher are applied.
Additional ADMIN identities are created only by the authenticated ADMIN
administration service.

Django framework permission/group flags do not create additional application
roles or supersede the role matrix. Built-in `/admin/` is technical/development
tooling only and is accessible only to authenticated, active users whose
application role is ADMIN. `is_staff` is synchronized from the application
role and cannot independently authorize access. `is_superuser` remains false
for application identities and never bypasses application authorization.

## Route and object policy

Every protected route requires an authenticated active session and explicit
role policy. Every object query is scoped before retrieval/mutation: a CLIENT
conversation is fetched through `(conversation_id, owner_id, not_deleted)`;
SUPPORT_AGENT human content requires assignment match; ADMIN access is explicit
and separately guarded. Direct URL guessing returns safe 404 or 403 without
revealing whether another user's object exists. Templates may hide controls,
but server checks are authoritative.

Phase 12.4 supplies reusable role and object-policy primitives for later views;
Phase 12.5 still owns browser login/session UX and protected-route redirects.
The identity-policy layer does not derive FastAPI OPS authority from ADMIN.

## Requirements

- **REQ-P12-AUTH-001:** Django MUST use a custom User model from its initial
  migration, with stable technical ID, unique login, Django password hash,
  exactly one of the three approved roles, active/blocked state, timestamps,
  and last-login where applicable.
- **REQ-P12-AUTH-002:** Application authorization MUST recognize exactly
  `ADMIN`, `CLIENT`, and `SUPPORT_AGENT`; role changes MUST be performed only
  by an authorized server-side admin workflow.
- **REQ-P12-AUTH-003:** Login MUST use Django's supported password hashing and
  session authentication; plaintext passwords, FastAPI bearer credentials,
  and trusted role context MUST never be stored in browser-accessible storage.
- **REQ-P12-AUTH-004:** Blocked/inactive users MUST be denied login and
  protected requests; existing sessions MUST be revalidated against account
  status and invalidated promptly when an account is blocked where practical.
- **REQ-P12-AUTH-005:** Every protected route MUST enforce authentication and
  role authorization on the server, independent of navigation visibility.
- **REQ-P12-AUTH-006:** Object-level authorization MUST prevent cross-client
  conversation access and prevent support agents from accessing unassigned
  HUMAN conversations.
- **REQ-P12-AUTH-007:** CLIENT, SUPPORT_AGENT, and ADMIN permissions MUST
  follow the role matrix in this specification; ADMIN role alone MUST NOT grant
  OPS execution authority.
- **REQ-P12-AUTH-008:** Login/logout and state-changing browser requests MUST
  use Django session rotation/invalidation, CSRF protection, secure cookie
  attributes, safe errors, generic account-identification responses, a
  30-minute inactivity timeout, and an independent eight-hour absolute limit.
- **REQ-P12-AUTH-009:** The first ADMIN MUST be provisioned by an explicit
  protected bootstrap operation with no default credentials or startup side
  effect; administration MUST prevent removal of the last active ADMIN under
  concurrency and prefer deactivation over physical deletion when history
  references a user.
