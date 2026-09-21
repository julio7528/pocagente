# Phase 9.7–9.9 — Orchestration and external search

Status: Phase 9.7 LangGraph orchestration, Phase 9.8 controlled Tavily
web-search integration, and Phase 9.9 Human Escalation coordination are
implemented and validated. Phase 9.10 `/chat` remains next.

## Provisional state contract

The future graph MAY carry this typed conceptual state, subject to implementation
review:

```text
message
user_id
route
grounded_context
tool_result
answer
citations
requires_human
error
```

It MUST not carry raw credentials, chain-of-thought, arbitrary SQL, or internal
database state to user-facing output.

Phase 9.7/9.8 implement the approved acyclic routing topology with typed request,
Router decision, Knowledge result, Customer Support result, controlled status,
and deferred-route flags. The injected live-public Knowledge boundary executes
only for Router-approved web policy: required current information, or conditional
fallback after insufficient persistent RAG. It never runs for private OPS,
security-block, or Human Escalation paths. Human escalation is an injected,
typed, non-persistent state-transition capability.
Live evidence is first transformed by the typed `LiveWebContextBuilder`, an
equivalent non-persistent grounding contract that reuses Phase 8 evidence
sufficiency, citations, priority ordering, and passive-DATA instructions while
deliberately omitting persistent `RetrievedChunk`/database provenance. The
Phase 9.7 `web_fallback_terminal` is removed: missing injected web capability
still returns `WEB_FALLBACK_PENDING` directly from `web_knowledge`.
For cooperative requests it runs Knowledge followed by Customer Support and
retains both results without semantic merging.

## Requirements

- **REQ-P9-ORCH-001:** Routing MUST transition only to approved capabilities.
- **REQ-P9-ORCH-002:** Knowledge transitions MUST consume an approved typed
  grounded-evidence contract before generation. Persistent RAG Knowledge MUST
  consume `GroundedContext` produced by the Phase 8 grounding boundary. Live
  public Web Knowledge MUST consume `LiveWebGroundedContext`, or an approved
  equivalent non-persistent live-evidence grounding contract, before generation.
  Raw retrieval or raw web-search evidence MUST NOT be passed directly to
  generation, and live evidence MUST NOT be converted into synthetic persistent
  RAG provenance.
- **REQ-P9-ORCH-003:** Customer Support transitions MUST use controlled typed
  tools for operational facts.
- **REQ-P9-ORCH-004:** Multiple capabilities MAY cooperate when one request
  requires both process knowledge and observed OPS facts.
- **REQ-P9-ORCH-005:** Normal completion MUST produce a safe response contract;
  failures MUST remain explicit and must not become fabricated success.
- **REQ-P9-ORCH-006:** Human handoff MUST transition only after explicit user
  confirmation.
- **REQ-P9-ORCH-007:** The graph MUST remain independent of provider SDKs,
  repository internals, and raw database access.

Example cooperation: a protocol-delay question may combine Knowledge evidence
about the expected process with Customer Support OPS evidence about observed
state. The final interpretation MUST preserve fact/inference boundaries.

## Tavily boundary

- **REQ-P9-WEB-001:** Tavily MAY be used for public/general/current information
  where freshness requires external search.
- **REQ-P9-WEB-002:** Tavily MUST NOT be used for private protocol, account, or
  runtime facts.
- **REQ-P9-WEB-003:** Web results MUST remain untrusted evidence and MUST pass
  the approved security/grounding policy before use.
- **REQ-P9-WEB-004:** Web results MUST NOT be persisted into RAG automatically.
- **REQ-P9-WEB-005:** Search failure or unsafe content MUST fail closed without
  fabricated information or bypassed authorization.

Approved Getnet priority for live evidence is derived from the existing public
source registry (`knowledge/internal/cancellation-process/public/sources.yaml`)
through its existing parser; it is not duplicated in the Tavily adapter or
Router. Third-party live sources remain untrusted public evidence and are not
automatically approved or ingested.

## Failure behavior

The future graph must represent, without inventing success: LLM unavailable,
RAG unavailable, OPS tool unavailable, insufficient evidence, web-search failure,
invalid routing, and unavailable escalation. Each path requires a controlled
safe error or handoff state and a future behavioral test.

## Human handoff transitions

For challenge-014, turn 1 remains in Customer Support: it obtains protocol and
failure evidence, labels FACT versus INFERENCE, and offers escalation without
transferring. Only an explicit user confirmation permits the Human Escalation
transition. The conversation then enters `WAITING_HUMAN`, which means confirmed
handoff awaiting authorized operator acceptance, not active human ownership.
After an authorized operator accepts, a distinct approved human-owned state
becomes active and only then are automated responses suspended. The graph
passes only the minimum sanitized diagnostic package and does not create an
external ITSM ticket through AI. Return to automation requires an explicit
approved transition by the assigned authorized operator; resolution has the
same ownership requirement. Acceptance verifies that the confirmed handoff
package references the same conversation as the transition request. This
contract is compatible with the future Django
`CLIENT` / `SUPPORT_AGENT` operator experience and does not introduce a queue,
polling, persistence model, or external channel.

### Orchestration acceptance scenarios

- **Given** a process question, **when** the graph routes it, **then** Knowledge
  receives the request and grounding precedes generation.
- **Given** challenge-012, **when** both expected process and observed protocol
  state are needed, **then** Knowledge and Customer Support share only typed
  evidence through one approved orchestration path.
- **Given** challenge-014 turn 1, **then** support uses both approved tools,
  explains observed facts versus inference, and offers but does not execute
  handoff.
- **Given** challenge-014 turn 2 with explicit confirmation, **then** the graph
  enters `WAITING_HUMAN`, transfers minimum sanitized context, and waits for
  authorized operator acceptance; it does not yet suspend automated responses.
- **Given** a `WAITING_HUMAN` conversation, **when** an authorized operator
  accepts, **then** human ownership becomes active and automated responses are
  suspended.
- **Given** no confirmation, tool/provider failure, insufficient evidence, or
  unavailable escalation, **then** the graph returns a controlled safe state and
  never fabricates success.
