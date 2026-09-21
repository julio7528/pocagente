# Phase 9.10 — `/chat` API boundary

Status: Phase 9.10 implementation complete and validated. FastAPI `POST /chat`
is the authenticated, typed transport boundary over the existing application
orchestration runtime. Phase 9.11 end-to-end validation remains next.

## Request

The authenticated boundary remains compatible with the challenge payload:

```json
{
  "message": "Your query or statement here",
  "user_id": "some_user_identifier"
}
```

- **REQ-P9-CHAT-001:** The endpoint MUST accept a validated non-blank message
  and user identifier.
- **REQ-P9-CHAT-002:** The endpoint MUST enforce the approved service/user
  authentication boundary before agent execution.
- **REQ-P9-CHAT-003:** The endpoint MUST invoke application orchestration rather
  than exposing LangGraph or provider internals.
- **REQ-P9-CHAT-004:** A successful response MUST support a safe answer, route or
  capability, safe citations, and `requires_human` state where applicable.
- **REQ-P9-CHAT-005:** Errors MUST be structured and safe; raw prompts,
  chain-of-thought, SQL, schema names, credentials, and provider secrets MUST
  not be returned.
- **REQ-P9-CHAT-006:** The response contract MUST remain stable enough for the
  future Django portal and must not require Django knowledge of DeepSeek,
  LangGraph, pgvector, RRF, or repositories.

## Django compatibility

Django is a future portal/frontend/session/admin consumer of this HTTP contract.
It MUST NOT need direct knowledge of DeepSeek SDK details, LangGraph graph state,
pgvector, RRF, RAG repositories, or OPS repositories. The API remains the
agent/RAG/tools/provider backend boundary.

## Implemented authentication and translation boundary

FastAPI authenticates its trusted internal caller with the runtime-only
`AGENT_API_SERVICE_TOKEN` Bearer credential before accepting identity or role
claims. The authenticated service supplies `X-Authenticated-User-Id`,
`X-Authenticated-Role`, and an optional `X-Ops-Authorized` claim. The JSON
`user_id` MUST match the authenticated identity and is never authentication
proof by itself. This is compatible with future Django-owned CLIENT and
SUPPORT_AGENT sessions without implementing Django, JWT issuance, OAuth, or a
user database.

`ChatApplicationService` explicitly translates the strict transport contract
to `OrchestrationRequest`, then allowlists `OrchestrationResult` into the stable
HTTP response. Optional operational and human-transition context contains only
business selectors and same-conversation state; OPS authority and operator role
come exclusively from authenticated claims. The route handler contains no
routing, retrieval, SQL, provider, OPS-tool, or handoff-state logic.

The response may contain a safe answer, route, citations, separate Knowledge
and Customer Support sections, FACT/INFERENCE separation, `requires_human`, and
the approved Human state. It excludes internal provenance, raw graph state,
repository/provider objects, prompts, SQL, credentials, diagnostics, and
provider-specific payloads. Controlled domain outcomes use HTTP 2xx; malformed
input uses 422, failed authentication 401, authenticated forbidden operations
403, and unavailable application orchestration 503.

## Acceptance scenarios

Tests cover authenticated valid requests, invalid input, grounded
knowledge response, controlled OPS response, insufficient evidence, explicit
handoff states, provider/tool failure, safe error serialization, health/readiness,
and OpenAPI generation. Normal tests use injected fakes and perform no network
or database access.

### `/chat` acceptance scenarios

- **Knowledge:** Given an authenticated documented question, when `/chat`
  invokes orchestration, then the response contains only a grounded safe answer
  and safe citations.
- **Customer Support:** Given an authorized protocol question, then the response
  reflects typed OPS facts or a controlled unavailable state.
- **Cooperation:** Given challenge-012, then the response can represent the
  comparison of grounded process evidence and observed OPS evidence without
  exposing internal provenance.
- **Insufficient evidence:** Given no usable evidence, then the response uses a
  safe insufficient-evidence state and does not invent facts.
- **Security block:** Given challenge-013, then no secret is searched or returned
  and the approved block/redaction/audit path is represented safely.
- **Escalation:** Given challenge-014, then offer, confirmation, handoff state,
  and human ownership are represented without silent transfer.
- **Failure:** Given provider, tool, RAG, or orchestration failure, then the API
  serializes a safe error without raw prompts, SQL, chain-of-thought, credentials,
  or provider secrets.
