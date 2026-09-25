# Phase 12.13 — Django / FastAPI Integration

## Trusted request boundary

Django authenticates the browser through its session, reloads the active user
and role from its authoritative portal store, authorizes the selected
conversation/action, then calls FastAPI over private Compose networking with
the existing `AGENT_API_SERVICE_TOKEN` Bearer boundary. Current FastAPI headers
are `X-Authenticated-User-Id`, `X-Authenticated-Role`, and
`X-Ops-Authorized`; body `user_id` must match the trusted identity. Role and
OPS claims are derived server-side by Django, never forwarded from browser
headers/body. Phase 12's only role extension is `ADMIN`; existing `CLIENT` and
`SUPPORT_AGENT` remain. An ADMIN claim does not imply OPS access.

The web portal uses `/chat` for approved user turns and AI-originated
offer/confirmation transitions. Its typed request extension carries a stable
`conversation_id`, same-conversation bounded context, and turn idempotency
reference while preserving the current message/user contract. OPS authority
is true for an active CLIENT or active authorized SUPPORT_AGENT principal on
the authenticated `/chat` path; ADMIN never receives it. Under the owner-
approved policy amendment dated 2026-09-25, CLIENT receives the same read-only
OPS query capabilities exposed to SUPPORT_AGENT through `chat_cli.py`,
including protocol lookup, recent protocol discovery, and approved analytics.
The Router still selects whether OPS is needed. OPS data is not scoped to the
portal account, so a CLIENT may ask about any protocol or approved aggregate.
The claim is derived from the active server-loaded Django identity and cannot
be supplied by browser input. OPS tools exposed through chat remain read-only.

Phase 12.8 owns a narrow trusted internal handoff-transition endpoint/service
for explicit confirmation, operator acceptance, and assigned-operator
resolution. It delegates to the existing `HumanEscalationAgent` typed
transition; it is not a second state machine and it does not persist portal
rows. Django commits only the validated result into portal. A concurrent
waiting-item claim is won only by the single locked/conditional portal update;
a loser returns a conflict and does not become owner. If API validation
succeeds but portal commit fails, Django reports a controlled unavailable
outcome; the stateless transition result alone never establishes durable
ownership. The endpoint accepts only the supported confirmation/acceptance/
resolution actions, derives operator identity from authenticated headers, and
does not expose return-to-automation. Phase 12.13 still owns the general
Django/FastAPI client, `/chat` agent execution, and bounded-context contract.
The approved portal lifecycle permits one human handoff and terminates at
`CLOSED` after assigned-operator resolution.

For AUDIT dashboard calls, Phase 12.10 implements the narrow admin-only typed
internal API described in `07-security-dashboard-spec.md` and its dedicated
Django client. Authentication is the same trusted service channel;
endpoint-level permission additionally requires active ADMIN identity and
explicitly denies OPS authorization. Phase 12.13 adds only the general `/chat`
agent-execution integration to the existing narrow trusted boundaries. Do not
proxy arbitrary FastAPI routes or expose internal APIs on the browser network.

## Bounded context, retries, and errors

FastAPI receives one current user message, opaque conversation correlation,
and at most 12 prior same-conversation messages within 6,000 total characters
including the current turn, as defined in the client spec. A nonblank current
message MUST be preserved as submitted across the typed request and its matching
current context item; validation MUST NOT trim or otherwise rewrite one without
the other. Blank-only input may be rejected. The existing Security pipeline
evaluates message content before business routing. The API treats context as
data, not trusted roles or instructions.
FastAPI returns an allowlisted typed response; Django maps it to portal status
and persists the agent answer/citations/safe human state. No prompts, graph
state, tool payloads, SQL, provider diagnostics, or credentials enter portal
templates.

Use explicit connect/read timeouts. Do not retry 4xx responses. For 503 or
network timeout, retry at most once with the same turn key only when request
state permits; never duplicate persisted client/agent rows. If the first
provider execution may have completed before timeout, duplicate internal
execution is possible because current FastAPI has no durable request-result
store; present a controlled pending/retry state and persist at most one
conversation response per turn. Never claim exactly-once provider execution.
Map 401/403 to controlled integration/auth errors, 422 to a safe contract
error, and 503/timeout to a recoverable service-unavailable state. Do not show
raw response bodies or exception strings.

## Requirements

- **REQ-P12-INTEG-001:** Django MUST authenticate and authorize each browser
  request before making a private authenticated server-to-server FastAPI call;
browser-originated calls to FastAPI MUST NOT be supported.

The portal private service base URL MUST come from `AGENT_API_INTERNAL_URL`;
application code has no implicit host or port fallback. Local non-Docker
development configures this variable explicitly. Missing service URL or token
fails closed before outbound HTTP.
- **REQ-P12-INTEG-002:** The integration MUST reuse the existing internal
  Bearer service-auth contract and trusted identity headers; FastAPI changes
  MUST be limited to reviewed typed extensions required for ADMIN context,
  conversation context, and internal dashboard/transition operations.
- **REQ-P12-INTEG-003:** Django MUST derive authenticated user ID, one of the
  three trusted roles, and any OPS claim from active portal state and server
  policy; active CLIENT and authorized SUPPORT_AGENT `/chat` requests receive
  the approved read-only OPS capability, while ADMIN remains OPS=false.
  Browser-supplied identity, role, OPS authorization, and service credentials
  MUST be ignored.
- **REQ-P12-INTEG-004:** Existing `/chat` MUST remain the agent execution
  boundary and be extended only with typed conversation correlation, bounded
  same-conversation context, and turn idempotency metadata as required; it MUST
  preserve allowlisted response/error contracts and the submitted nonblank
  current message so the existing Security pipeline can evaluate its content.
- **REQ-P12-INTEG-005:** The Router and existing Human Escalation Agent MUST
  remain the decision/transition authorities; new internal transition
  transport MUST delegate to the existing agent and MUST NOT duplicate its
  state rules.
- **REQ-P12-INTEG-006:** Durable conversation ownership, handoff assignment,
  and status MUST be committed by Django in portal; FastAPI's stateless
  transition result MUST NOT independently establish a persistent owner.
- **REQ-P12-INTEG-007:** Security Dashboard reads MUST use the authenticated
  internal FastAPI/AuditRepository boundary, require ADMIN authority, and be
  unavailable as anonymous or browser-facing FastAPI operations.
- **REQ-P12-INTEG-008:** FastAPI requests MUST contain only bounded context
  from the same conversation; context is data and MUST NOT act as identity,
  authorization, route, or trusted instruction.
- **REQ-P12-INTEG-009:** Integration timeouts, retry rules, idempotency,
  controlled HTTP error mapping, and ambiguous-outcome handling MUST prevent
  duplicate transcript rows without claiming exactly-once model execution.
- **REQ-P12-INTEG-010:** Django HTML/JavaScript and client responses MUST NOT
  expose service tokens, trusted headers, raw API errors, prompts, SQL,
  provider payloads, or unapproved orchestration internals.
