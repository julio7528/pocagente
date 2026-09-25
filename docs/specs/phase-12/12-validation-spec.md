# Phase 12.16–12.17 — Validation, Traceability, and Closure

## Validation gates

Phase 12 is implementation-ready only after owner approval of this SDD. Future
validation is staged and each gate must pass before the next dependent stage:

1. static/settings/auth configuration and explicit migration-plan review;
2. unit tests for user roles, status mapping, services, FastAPI DTO validation,
   and controlled error mapping;
3. portal-schema PostgreSQL integration tests using isolated test data and
   non-destructive cleanup; prove all Django tables resolve to `portal`, the
   custom UUID User is in the initial migration, application tables use the
   exact clean names, and existing `rag`, `ops`, and `audit` structures/counts
   remain intact; verify the 0007 native migration creates only `portal`;
4. route/object authorization, CSRF/session, blocked-user, safe-output,
   idempotency, concurrent handoff-claim, and audit-data sanitization tests;
5. FastAPI `/chat` and internal AUDIT API contract tests with trusted role
   propagation and denied browser-controlled claims;
6. E2E browser journey from CLIENT login and AI chat, through confirmed human
   handoff, SUPPORT_AGENT claim/messages/finalization, then CLIENT read-only
   closed history;
7. Docker service health/restart/`down`+`up` persistence tests, proving the
   existing PostgreSQL volume/data remain;
8. full project regression, Phase 9–11 validation, dependency/security scans,
   documentation/traceability checks, and owner closure review.

No destructive tests may target the developer's persisted database. Use an
isolated database/schema or explicitly resettable fixture approved for tests.
Do not run database cleanup against shared `rag`, `ops`, or `audit` data.

## Minimum future acceptance matrix

### Authentication and authorization

- Anonymous requests cannot access every protected client/support/admin page.
- CLIENT cannot access support/admin routes; SUPPORT_AGENT cannot access admin
  routes; inactive users cannot log in; forged role/OPS headers have no effect.
- Successful login sends CLIENT to `/chat/`, SUPPORT_AGENT to `/support/`, and
  ADMIN to `/admin-portal/`; wrong-role requests return controlled HTTP 403,
  while anonymous requests redirect to `/login/`.
- Login rotates the session, logout invalidates it, CSRF protects both POST
  forms, 30 minutes of inactivity expires the session, and repeated activity
  cannot extend it beyond the independent eight-hour absolute lifetime.
- Unknown username, wrong password, malformed login, and inactive account use
  the same public error. The page has no registration or Remember Me control;
  its Forgot Password link leads only to the complete Phase 12.12 request flow.
- CLIENT A changing a conversation UUID to CLIENT B's object receives safe
  403/404 and cannot read or mutate it.
- A SUPPORT_AGENT cannot read/accept another agent's assigned HUMAN item.
- CSRF, login session rotation, logout invalidation, blocked-user session
  invalidation/revalidation, and last-admin protection work.

### Client conversations

- Create a conversation; persist client and agent messages; reopen/continue
  ACTIVE; verify bounded context includes only recent same-conversation turns.
- BLOCKED and CLOSED histories remain readable but reject writes; only ADMIN
  can restore a BLOCKED conversation to its recorded prior state. DELETED is
  soft-deleted with ADMIN actor/time, hidden from ordinary client/support
  views, physically retained, and has no normal restore workflow.
- The title is initialized once from the first CLIENT message using normalized
  whitespace and the deterministic 50-character (47 plus `...`) rule; later
  messages do not change it.
- Historical message body is immutable to CLIENT, SUPPORT_AGENT, and ADMIN.
- Retry the same client turn key and prove no duplicate transcript messages.

### Support lifecycle

- Offer alone stays active/awaiting confirmation; confirmation creates the
  conversation's sole WAITING handoff; two simultaneous claims produce exactly
  one ASSIGNED owner.
- Accepted support messages share the same thread; AI is not called while
  HUMAN; wrong operator cannot finalize; assigned operator finalizes to
  terminal CLOSED. No HUMAN-to-ACTIVE transition or second handoff is allowed.
- After closure client reads history but cannot send and AI does not resume.
- Poll updates are ordered, deduplicated, bounded, and safe on service errors.

### Admin and password requests

- Admin create/block/role-change/reset operations enforce last-admin
  protection; migrations create no ADMIN account and the first ADMIN is
  established only through `manage.py bootstrap_admin`, which refuses repeat
  use, prompts for confirmed credentials, and persists only a Django hash.
- There is no anonymous registration route. Only active ADMIN services can
  create users/change roles; `is_active=False` rejects both login and prior
  sessions, and role/password changes revoke target sessions.
- A SUPPORT_AGENT with an active ASSIGNED handoff for a HUMAN conversation
  cannot change roles. CLIENT ownership and SUPPORT_AGENT assignment policies
  are enforced in reusable server-side authorization primitives.
- Django `/admin/` admits only authenticated active ADMIN-role users even if
  framework flags are forged; `is_superuser` is never an application-role
  bypass. Concurrent admin deactivation/demotion attempts preserve at least
  one active ADMIN.
- Admin block stores the prior state and freezes all normal writers while
  preserving readable history; only ADMIN restores it. Soft delete records
  ADMIN actor/time, hides the history from normal views, and preserves rows.
- Password request response is non-enumerating; OPEN can be resolved/rejected;
  plaintext is absent from DB, logs, HTML, and AUDIT.

### Security Dashboard and integration

- Against a known sanitized fixture, daily totals, involved users, events per
  user, event type/source breakdown, each filter, pagination, and detail agree
  with `audit.security_events` via AuditRepository API results.
- Django cannot query AUDIT directly; anonymous/browser calls to internal
  endpoints fail; trusted ADMIN with OPS false is allowed while CLIENT,
  SUPPORT_AGENT, missing role, and OPS true are denied. Sanitized content only
  is returned. The narrow AUDIT dashboard API belongs to Phase 12.10; general
  `/chat` and context integration remains Phase 12.13.
- `/chat` receives identity and roles derived by Django; CLIENT has OPS false;
  SUPPORT_AGENT authorization is server-derived; browser cannot alter either.
- Controlled 401/403/422/503/timeout results do not expose provider internals;
  retry does not duplicate persisted messages.

### Docker and full journey

- Build/start all three services; verify health/readiness and private service
  connectivity; no migration is executed automatically.
- Restart and `down` then `up` without `-v`; verify exact PostgreSQL volume
  identity and preserved RAG/OPS/AUDIT/portal data.
- Run complete CLIENT login → conversation → AI → confirmed handoff → support
  claim/message → finalization → client read-only history flow.
- Run complete project tests plus compile/static/dependency/security checks;
  compare behavior against Phase 9–11 baselines and challenge expectations.

## Requirement traceability matrix

Each unique Phase 12 requirement appears exactly once below. Acceptance
evidence names the future proof; test type is a required validation category,
not a claim that implementation or tests already exist.

| Requirement | Source spec / implementation owner | Future acceptance evidence | Test type |
|---|---|---|---|
| REQ-P12-CORE-001 | 00 Master / Phase owner | Portal scope map | Review |
| REQ-P12-CORE-002 | 00 Master / Django + FastAPI owners | Responsibility boundary review | Architecture |
| REQ-P12-CORE-003 | 00 Master / Database owner | Schema ownership check | Integration |
| REQ-P12-CORE-004 | 00 Master / Security owner | Security and data-flow gate | Security |
| REQ-P12-CORE-005 | 00 Master / Phase owner | 100-ID traceability and closure evidence | Documentation |
| REQ-P12-ARCH-001 | 01 Architecture / Django | Package tree and service ownership | Static |
| REQ-P12-ARCH-002 | 01 Architecture / Django | Browser network inspection and API path | E2E/security |
| REQ-P12-ARCH-003 | 01 Architecture / Django + FastAPI | Ownership review by domain | Architecture |
| REQ-P12-ARCH-004 | 01 Architecture / Django | Dependency/import and API boundary scan | Static |
| REQ-P12-ARCH-005 | 01 Architecture / Integrations | Typed client/DTO contract tests | Unit/contract |
| REQ-P12-ARCH-006 | 01 Architecture / Django | Module dependency review | Architecture |
| REQ-P12-ARCH-007 | 01 Architecture / Platform | Local and Compose smoke tests | Integration |
| REQ-P12-DB-001 | 02 Portal DB / Database + Django | All portal/framework tables resolve in portal only | PostgreSQL integration |
| REQ-P12-DB-002 | 02 Portal DB / Accounts | Custom User present in initial migration | Migration review |
| REQ-P12-DB-003 | 02 Portal DB / Django | Approved table inventory only | Schema test |
| REQ-P12-DB-004 | 02 Portal DB / Conversations | Owner/status/tombstone constraints | PostgreSQL integration |
| REQ-P12-DB-005 | 02 Portal DB / Conversations | Sender FK, ordered history, and immutable body behavior for all roles | Integration |
| REQ-P12-DB-006 | 02 Portal DB / Conversations | Replayed turn key has one transcript row | Idempotency integration |
| REQ-P12-DB-007 | 02 Portal DB / Support | Handoff timestamps, assignment, unique lifetime handoff per conversation, terminal resolution | PostgreSQL/concurrency integration |
| REQ-P12-DB-008 | 02 Portal DB / Accounts | Reset table contains no password material | Security/schema test |
| REQ-P12-DB-009 | 02 Portal DB / Platform | Framework tables in portal, shared POC principal, and no Django ORM access to other schemas | PostgreSQL/static integration |
| REQ-P12-DB-010 | 02 Portal DB / Admin | Soft-delete retains message/handoff history | Integration |
| REQ-P12-DB-011 | 02 Portal DB / Database | Explain/query evidence for listed access paths | Query review |
| REQ-P12-AUTH-001 | 03 Auth / Accounts | Custom role-bearing User and hash fields | Model/auth tests |
| REQ-P12-AUTH-002 | 03 Auth / Authorization | Exactly three role choices; no registration; ADMIN-only role mutation and revocation | Security tests |
| REQ-P12-AUTH-003 | 03 Auth / Accounts | Hash verification; environment-driven secure cookie policy; no credentials in browser output | Auth/security |
| REQ-P12-AUTH-004 | 03 Auth / Accounts | is_active rejection; deactivation clears prior session and returns generic login UX | Integration |
| REQ-P12-AUTH-005 | 03 Auth / Django views | Anonymous redirect, strict role landing matrix, controlled wrong-role HTTP 403 | Route authorization |
| REQ-P12-AUTH-006 | 03 Auth / Authorization | Cross-client and unassigned-support object matrix, including assigned HUMAN predicate | Object authorization |
| REQ-P12-AUTH-007 | 03 Auth / Policy | Role matrix plus ADMIN-no-OPS proof | Security integration |
| REQ-P12-AUTH-008 | 03 Auth / Accounts | CSRF, rotation, logout, generic errors, 30m inactivity and independent 8h absolute expiry | Browser/security |
| REQ-P12-AUTH-009 | 03 Auth / Admin | Bootstrap command and concurrent last-active-ADMIN protection | Unit/PostgreSQL concurrency |
| REQ-P12-CLIENT-001 | 04 Client / Conversations | Create/list/reopen and cross-conversation isolation | E2E |
| REQ-P12-CLIENT-002 | 04 Client / Integrations | Every runtime-to-portal handoff mapping | State contract |
| REQ-P12-CLIENT-003 | 04 Client / Conversations | BLOCKED/CLOSED read-only; DELETED hidden | E2E/authorization |
| REQ-P12-CLIENT-004 | 04 Client / Conversations | Mixed AI/system/human ordered thread | Integration |
| REQ-P12-CLIENT-005 | 04 Client / Integrations | Same-key retry creates no duplicate transcript | Retry integration |
| REQ-P12-CLIENT-006 | 04 Client / Integrations | Same-conversation context capped at 12 prior messages and 6,000 characters; oversized current input remains fully persisted while its context copy is explicitly marked truncated | Contract/security |
| REQ-P12-CLIENT-007 | 04 Client / Templates | Header/sidebar/main/footer, owned history, new conversation, state-aware composer and full escaped transcript usable | Browser E2E |
| REQ-P12-CLIENT-008 | 04 Client / Authorization | URL/body ID substitution is denied | Security E2E |
| REQ-P12-CLIENT-009 | 04 Client / UX | Empty, pending, failed, validation and service-error states contain no internals; Phase 12.7 has no inactive retry action | UX/security |
| REQ-P12-SUPPORT-001 | 05 Support / FastAPI + Django | Internal typed endpoint delegates approved transition requests to existing HumanEscalationAgent | API contract/security |
| REQ-P12-SUPPORT-002 | 05 Support / Support portal | Request alone does not queue; separate CSRF-protected confirmation invokes CONFIRM | Browser/state integration |
| REQ-P12-SUPPORT-003 | 05 Support / Integrations | Runtime/portal status mapping matrix | Contract |
| REQ-P12-SUPPORT-004 | 05 Support / Support views | Role/assignment queue visibility matrix | Authorization E2E |
| REQ-P12-SUPPORT-005 | 05 Support / Support service | Two concurrent claimants, one winner | Concurrency |
| REQ-P12-SUPPORT-006 | 05 Support / Support service + FastAPI | Assigned operator only; actor headers and portal active assignment must agree for RESOLVE | Security integration |
| REQ-P12-SUPPORT-007 | 05 Support / Integrations | HUMAN messages same thread; zero agent calls | E2E/observer |
| REQ-P12-SUPPORT-008 | 05 Support / Support service + FastAPI | Assigned operator invokes RESOLVE, portal commits CLOSED/RESOLVED, repeat is safe | E2E/API contract |
| REQ-P12-SUPPORT-009 | 05 Support / UX | 12s polling, cursor order, dedupe/backoff | Browser integration |
| REQ-P12-ADMIN-001 | 06 Admin / Admin portal | Product admin screens beyond Django Admin | Browser review |
| REQ-P12-ADMIN-002 | 06 Admin / User services | ADMIN-only paginated search/filter/list/create/activate/role/password flows; sensitive changes revoke target sessions, including the acting browser session on self-change | Admin integration |
| REQ-P12-ADMIN-003 | 06 Admin / User services | Deactivate referenced user; last-admin protection | Integration |
| REQ-P12-ADMIN-004 | 06 Admin / Conversation services | Active ADMIN bounded search/filter/pagination; full immutable same-thread history, including retained DELETED records | PostgreSQL/browser E2E |
| REQ-P12-ADMIN-005 | 06 Admin / Conversation services | Atomic block/unblock restores valid saved state and assignment; retained soft-delete rejects an active handoff; CLOSED terminal | PostgreSQL concurrency/browser E2E |
| REQ-P12-ADMIN-006 | 06 Admin / Authorization | Guessed admin URLs denied for other roles | Route security |
| REQ-P12-ADMIN-007 | 06 Admin / Audit policy | No routine admin row in security_events | Repository boundary |
| REQ-P12-AUDITUI-001 | 07 Audit UI / FastAPI Audit service | Aggregates reconcile to AuditRepository records | PostgreSQL integration |
| REQ-P12-AUDITUI-002 | 07 Audit UI / FastAPI + Django | Django has no AUDIT SQL/repository; browser denied | Static/security |
| REQ-P12-AUDITUI-003 | 07 Audit UI / FastAPI Audit service | Typed summary/series/breakdown/list/detail contract | API contract |
| REQ-P12-AUDITUI-004 | 07 Audit UI / FastAPI + Django | Each filter affects all dashboard outputs | API/UI integration |
| REQ-P12-AUDITUI-005 | 07 Audit UI / Audit service | Daily/user/type/source aggregates match fixture | Aggregate integration |
| REQ-P12-AUDITUI-006 | 07 Audit UI / Security | Invalid ranges, enum, size and payload leakage denied | Security/contract |
| REQ-P12-AUDITUI-007 | 07 Audit UI / Admin UI | Filtered cards/charts/list/detail and reset | Browser E2E |
| REQ-P12-PASSWORD-001 | 08 Password / Accounts | Explicit confirmation; active known account creates/reuses one OPEN item; inactive/unknown create none | Integration/concurrency |
| REQ-P12-PASSWORD-002 | 08 Password / Accounts | Known active, known inactive, and unknown identifiers receive the same public outcome and page shape | Security/browser |
| REQ-P12-PASSWORD-003 | 08 Password / Admin portal | ADMIN queue filters all lifecycle states, oldest-first bounded pagination, detail and OPEN-only actions | Workflow integration |
| REQ-P12-PASSWORD-004 | 08 Password / Admin + Accounts | Hash-only persisted; no plaintext in logs/UI/DB | Security scan |
| REQ-P12-PASSWORD-005 | 08 Password / Admin service | Atomic resolve/reject race has one terminal winner; password service, resolver/time and session revocation are consistent | PostgreSQL concurrency |
| REQ-P12-INTEG-001 | 09 Integration / Django | Session/object authorization precedes outbound HTTP | Contract/security |
| REQ-P12-INTEG-002 | 09 Integration / FastAPI auth | Bearer and identity contract plus minimal ADMIN extension | API security |
| REQ-P12-INTEG-003 | 09 Integration / Django auth | Forged browser role/OPS values ignored | Security E2E |
| REQ-P12-INTEG-004 | 09 Integration / FastAPI chat | Existing `/chat` plus typed conversation metadata; nonblank current text stays intact through validation and reaches Security before business routing | API/security contract |
| REQ-P12-INTEG-005 | 09 Integration / FastAPI Human | Trusted transition endpoint delegates CONFIRM/ACCEPT/RESOLVE to existing agent; general `/chat` execution is owned and validated separately in Phase 12.13 | Unit/API contract |
| REQ-P12-INTEG-006 | 09 Integration / Django support | Locked portal commit owns assignment; stateless result alone never establishes owner | Failure/concurrency |
| REQ-P12-INTEG-007 | 09 Integration / FastAPI Audit | Admin-only AUDIT read; no browser endpoint | API security |
| REQ-P12-INTEG-008 | 09 Integration / Django + FastAPI | Context same-conversation, bounded, non-authoritative | Contract/security |
| REQ-P12-INTEG-009 | 09 Integration / Django client | 401/403/422/503/timeout and bounded retry behavior | Fault injection |
| REQ-P12-INTEG-010 | 09 Integration / Security | HTML/network capture has no secrets or raw internals | Secret/output scan |
| REQ-P12-UI-001 | 10 UI / Frontend | Template stack, no required SPA/CDN | Build/static review |
| REQ-P12-UI-002 | 10 UI / Frontend | Twelve screen inventory acceptance | Browser E2E |
| REQ-P12-UI-003 | 10 UI / Frontend | Header/sidebar/main/footer by role | Browser review |
| REQ-P12-UI-004 | 10 UI / Frontend | Poll/filter request loading/error/cursor behavior | Browser integration |
| REQ-P12-UI-005 | 10 UI / Frontend | Pinned self-hosted chart asset works offline | Static/browser |
| REQ-P12-UI-006 | 10 UI / Frontend | Keyboard, labels, focus, status and contrast baseline | Accessibility |
| REQ-P12-UI-007 | 10 UI / Authorization | Hidden control bypass attempts still denied server-side | Security E2E |
| REQ-P12-DOCKER-001 | 11 Docker / Platform | Three services and exact existing volume identity | Compose integration |
| REQ-P12-DOCKER-002 | 11 Docker / Platform | Loopback portal access; FastAPI not browser-facing | Network scan |
| REQ-P12-DOCKER-003 | 11 Docker / Platform | Service DNS/env config and ORM search_path restricted to portal | Integration/security |
| REQ-P12-DOCKER-004 | 11 Docker / Platform | Image/config/source/browser secret scan | Security scan |
| REQ-P12-DOCKER-005 | 11 Docker / Platform | Liveness/readiness/degraded API behavior | Container integration |
| REQ-P12-DOCKER-006 | 11 Docker / Platform | Startup has no migration; explicit command proof | Container/migration |
| REQ-P12-VAL-001 | 12 Validation / Phase owner | IDs unique and appear once in this matrix | Spec lint |
| REQ-P12-VAL-002 | 12 Validation / Phase owner | No 12.2 implementation before SDD approval | Process review |
| REQ-P12-VAL-003 | 12 Validation / Test owner | Isolated portal integration preserves current schemas/data | PostgreSQL integration |
| REQ-P12-VAL-004 | 12 Validation / Security owner | Complete route/object/CSRF/session/role matrix | Security suite |
| REQ-P12-VAL-005 | 12 Validation / Test owner | Full client-AI-human-support-close journey | E2E |
| REQ-P12-VAL-006 | 12 Validation / Database owner | Native + Django migrations explicit/schema-bounded | Migration audit |
| REQ-P12-VAL-007 | 12 Validation / Platform owner | Restart/down-up preserves volume and all domain counts | Docker/PostgreSQL integration |
| REQ-P12-VAL-008 | 12 Validation / Phase owner | Regression, scans, traceability and owner closure evidence complete | Full regression/review |

## Requirements

- **REQ-P12-VAL-001:** Every Phase 12 requirement MUST have one unique ID,
  source spec, implementation owner, acceptance evidence, and test type and
  MUST appear exactly once in the traceability matrix above.
- **REQ-P12-VAL-002:** Phase 12 implementation MUST NOT begin before explicit
  owner approval of the Phase 12 SDD; failed stage gates MUST block dependent
  implementation/closure claims.
- **REQ-P12-VAL-003:** PostgreSQL integration tests MUST use isolated,
  non-destructive fixtures and prove `rag`, `ops`, and `audit` ownership/data
  remain intact.
- **REQ-P12-VAL-004:** Future validation MUST cover anonymous/role/object
  authorization, CSRF/session protections, blocked users, and trusted-claim
  forgery attempts.
- **REQ-P12-VAL-005:** Future end-to-end validation MUST prove the complete
  client-to-agent-to-human-support-to-closed-history lifecycle.
- **REQ-P12-VAL-006:** Migration validation MUST prove explicit execution,
  portal-only Django ownership, immutable existing native migrations, and no
  startup migration side effects.
- **REQ-P12-VAL-007:** Docker validation MUST prove health, private integration,
  existing PostgreSQL volume identity, and persistence across restart and
  `down`/`up` without `-v`.
- **REQ-P12-VAL-008:** Phase 12 closure MUST require full regression/security
  evidence, requirement traceability, documentation reconciliation, and
  explicit owner review; no phase closure is inferred from implementation
  completion alone.

## Phase 12.14 execution evidence (2026-09-25)

- Baseline and final `python -m pytest`: **922 passed, 37 skipped, 1 known
  FastEmbed warning**.
- Django application suite against disposable PostgreSQL database
  `p12_14_validation_20260925`: **189 tests passed**. The database was removed
  after validation.
- `tests/phase12_portal_security_e2e.py` adds a machine-readable inventory of
  **36 protected routes** and **21 state-changing browser routes**. Anonymous
  and wrong-role requests are denied; each mutation rejects missing and
  invalid CSRF tokens. Its deterministic in-process journey crosses the
  browser-facing Django flow, the actual FastAPI `/chat` boundary, explicit
  Human Escalation confirmation, support claim/messages, finalization, and
  read-only CLOSED history. External model providers are not required by this
  deterministic gate.
- The route matrix exposed a wrong-role response regression in technical
  `/admin/`: authenticated CLIENT and SUPPORT_AGENT requests were redirected
  instead of receiving the SDD-required HTTP 403. The technical Admin wrapper
  was corrected; anonymous login and active ADMIN access remain covered by the
  existing account tests.
- `manage.py check` passed; all listed Django migrations are applied;
  `makemigrations --check --dry-run` reported no changes. `compileall`,
  `git diff --check`, `docker compose config`, and the `agent-api` container's
  `pip check` passed. Compose services remained healthy and `/ready` returned
  HTTP 200.
- Persistent `getnet_support` counts remained unchanged across the isolated
  suite: users 3, conversations 8, messages 24, support handoffs 0, password
  requests 0, and `audit.security_events` 146.
- Host-global `python -m pip check` still reports the pre-existing
  `google-adk 1.23.0` requirement for FastAPI `<0.124.0` against installed
  FastAPI `0.141.1`. The authoritative `agent-api` container dependency check
  is clean; project dependencies were not changed for the host-global
  environment.
