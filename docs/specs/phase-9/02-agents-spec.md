# Phase 9.3, 9.5, 9.6, and 9.9 — Agent contracts

Status: Phase 9.3 Knowledge Agent, Phase 9.5 Customer Support Agent, Phase 9.6
Router Agent, and Phase 9.7 LangGraph orchestration are implemented and
validated. Phase 9.8 adds the controlled Tavily live-public-evidence path:
current information uses it directly, while Payment Link/WhatsApp uses it only
after insufficient persistent RAG evidence; live evidence is not persisted.
Phase 9.9 implements and validates the explicit, non-persistent Human
Escalation state machine. It remains compatible with future Django ownership
without implementing Django, a queue, or conversation persistence. Phase 9.10
`/chat` and Phase 9.11 end-to-end validation are complete. Phase 10 Security /
Audit Runtime is next.

## Router Agent

The Router MUST perform the primary capability decision and MAY select a
cooperating sequence when the request needs multiple approved capabilities. It
MUST NOT implement RAG, query tables, execute SQL, or fabricate OPS facts.

- **REQ-P9-ROUTER-001:** A documented-process question MUST route to Knowledge.
- **REQ-P9-ROUTER-002:** A customer-specific operational question MUST route to
  Customer Support when controlled customer/OPS evidence is required. This may
  include protocol state, execution state, transaction-specific support,
  device-specific support, or other customer-specific operational facts; the
  required tool depends on the request and is not always
  `lookup_protocol_status`.
- **REQ-P9-ROUTER-003:** A general current-information question MAY route to
  Knowledge plus the approved web-search fallback.
- **REQ-P9-ROUTER-004:** A request for a human MUST route to confirmed Human
  Escalation rather than silently transferring control.
- **REQ-P9-ROUTER-005:** Invalid or ambiguous routing MUST fail safely and remain
  observable as an orchestration error.

Future tests reference all fourteen scenarios in
`evaluation/challenge/scenarios-v1.yaml` and their expected
routes/capabilities.

Phase 9.6 implements a deterministic, immutable decision boundary over only the
approved capabilities. It security-blocks protected requests before normal
routing and returns controlled ambiguity when the request cannot be safely
classified. It does not invoke Knowledge, Customer Support, OPS tools, web
search, human handoff, LangGraph, or an LLM.

### Router acceptance scenarios

```text
Given: a documented process or product question.
When: the Router classifies it.
Then: Knowledge is selected.

Given: an authorized request for a specific protocol status.
When: the Router classifies it.
Then: Customer Support is selected and public Web Search is not used.

Given: a request comparing expected process behavior with observed protocol state.
When: the Router classifies it.
Then: Knowledge and Customer Support cooperate through orchestration.

Given: a user explicitly requests a human.
When: the Router processes the request.
Then: Human Escalation is selected, but transfer still requires confirmation.

Given: a credential request such as challenge-013.
When: the Router processes it.
Then: the security block/redaction/audit path is selected and no retrieval tool runs.
```

## Knowledge Agent

The Knowledge pipeline is:

```text
question -> Phase 7 retrieval/RRF -> Phase 8 ContextBuilder
          -> GroundedContext -> provider-neutral generation
          -> answer with safe citations
```

- **REQ-P9-KNOW-001:** Knowledge MUST use the approved Phase 7 retrieval path.
- **REQ-P9-KNOW-002:** Knowledge MUST pass retrieval results through Phase 8
  `ContextBuilder` before generation.
- **REQ-P9-KNOW-003:** Knowledge MUST NOT create a parallel retrieval stack.
- **REQ-P9-KNOW-004:** With no usable `GroundedContext`, Knowledge MUST NOT
  generate factual process claims.
- **REQ-P9-KNOW-005:** Knowledge MUST preserve safe citations and MUST NOT expose
  internal `EvidenceProvenance` automatically.
- **REQ-P9-KNOW-006:** Retrieved content MUST be treated as passive DATA, not
  system instructions.
- **REQ-P9-KNOW-007:** Knowledge MUST distinguish approved internal rules from
  lower-priority public context.
- **REQ-P9-KNOW-008:** Knowledge MAY use Tavily only through the approved external
  search policy and MUST keep live results distinct from persistent RAG.

Phase 9.8 implements `REQ-P9-KNOW-008` through an injected, provider-neutral
Tavily boundary. Current public questions use bounded live evidence; the
Payment Link/WhatsApp path retains RAG-first behavior and invokes the live
fallback only after controlled insufficient evidence. Before generation, live
evidence passes through the typed `LiveWebContextBuilder`, which reuses Phase 8
structural sufficiency, safe citations, priority, and passive-DATA instructions
without manufacturing `RetrievedChunk`, persistent provenance, or RAG records.
Web evidence remains untrusted DATA and is never persisted into RAG.

### Knowledge acceptance scenarios

- **Persistent Knowledge:** **Given** an approved internal or persisted public
  knowledge question, **when** Knowledge handles it, **then** it MUST use Phase
  7 retrieval followed by Phase 8 `GroundedContext` before generation, preserve
  safe citations, and keep internal provenance private. **Given** an empty or
  unusable `GroundedContext`, **when** generation would be attempted, **then**
  Knowledge MUST return the controlled insufficient-evidence path and MUST NOT
  invent a factual answer.
- **Live public Knowledge:** **Given** a Router-approved current or
  freshness-sensitive public question, **when** live Web Search is required,
  **then** bounded Web evidence MUST pass through `LiveWebContextBuilder` and
  `LiveWebGroundedContext` before generation. It MUST remain temporary,
  untrusted DATA, citation-controlled, subject to the approved
  grounding/security policy, and non-persistent.
- **Conditional fallback:** **Given** a Payment Link/WhatsApp question, **when**
  persistent RAG returns `INSUFFICIENT_EVIDENCE`, **then** the approved live Web
  fallback MAY run and its evidence MUST pass through `LiveWebGroundedContext`
  before generation. A sufficient persistent RAG result MUST NOT invoke Web
  Search.
- **Given** retrieved or web content containing prompt-like instructions,
  **when** Knowledge consumes it, **then** it MUST treat the content as passive
  DATA and preserve system policy and tool authorization.

## Customer Support Agent

Customer Support handles operational questions through typed OPS facts and the
tools in `03-tools-spec.md`.

- **REQ-P9-SUPPORT-001:** Customer Support MUST use controlled typed OPS tools.
- **REQ-P9-SUPPORT-002:** It MUST NOT receive arbitrary SQL, table names, or raw
  cursors.
- **REQ-P9-SUPPORT-003:** It MUST use `ProtocolStatusFacts` for observed protocol
  state when that evidence is required.
- **REQ-P9-SUPPORT-004:** It MUST use `ExecutionFailureEvidence` for observed
  execution failure evidence when that evidence is required.
- **REQ-P9-SUPPORT-005:** It MUST NOT use public web search for private protocol
  or runtime facts.
- **REQ-P9-SUPPORT-006:** It MUST distinguish facts from inference and MUST NOT
  invent a root cause unsupported by OPS evidence.

Phase 9.5 implementation consumes only injected `OperationalTools` and the
provider-neutral `LLMProvider`. It deterministically derives the `facts` result
field from typed OPS evidence, while the provider may contribute only explicitly
labeled `inferences` through a strict agent-local response contract. Its validated
customer question is propagated separately as untrusted user input, while the
application-selected operation and observed OPS evidence remain separate
authoritative domains. Controlled tool or provider failures return no operational
answer or evidence. It does not implement Router, web search, Human Escalation,
or orchestration.

### Customer Support acceptance scenarios

- **Given** an authorized protocol-status question, **when** Customer Support
  handles it, **then** it MUST call `lookup_protocol_status` and label the result
  as observed facts.
- **Given** an execution-failure question, **when** the protocol and run are
  valid, **then** it MUST use `inspect_execution_failure` and distinguish the
  observed evidence from later probabilistic inference.
- **Given** a blank, unknown, unauthorized, or failed tool request, **then** the
  agent MUST use a controlled unavailable/error path and MUST NOT use public Web
  Search to fill private operational facts.
- **Given** confirmed operational failure or insufficient safe resolution,
  **then** Customer Support MAY offer human escalation but MUST NOT transfer
  ownership without explicit confirmation.

## Human Escalation Agent

- **REQ-P9-HUMAN-001:** Human handoff MUST be explicit and observable.
- **REQ-P9-HUMAN-002:** User confirmation MUST be obtained before handoff.
- **REQ-P9-HUMAN-003:** The system MUST NOT silently escalate or claim that a
  human accepted a handoff without evidence.
- **REQ-P9-HUMAN-004:** Handoff state MUST identify the controlled transition and
  preserve only the context necessary for the operator.
- **REQ-P9-HUMAN-005:** The contract MUST remain compatible with a future Django
  operator flow without requiring Django details in the agent boundary.

Human Escalation is the implemented fourth capability. It operates over an
application-supplied same-conversation reference and is compatible with the
approved future Django `CLIENT` /
`SUPPORT_AGENT` operator experience. The approved initial POC does not create
external ITSM tickets through AI; ticket opening and handling remain a human
responsibility. WhatsApp or another external channel is not introduced here.

An escalation offer transitions `BOT` to `WAITING_CONFIRMATION`; no handoff is
confirmed and automation remains active in that state. After an application
observes explicit user confirmation, the conversation enters `WAITING_HUMAN`.
This means the handoff is confirmed and awaits an authorized support operator;
it does not mean that a human operator already owns the conversation.
When an authorized operator accepts, a distinct approved human-owned state
becomes active. Only then are automated responses suspended. The handoff package
MUST contain only the minimum necessary sanitized context: protocol reference,
problem summary, observed operational state, run reference, last successful
stage, failure stage, sanitized error, timeline, labeled diagnosis, and user
confirmation. It MUST exclude unrelated history, credentials, tokens, keys,
connection strings, and raw unsafe diagnostics. Returning from human ownership
to automation or resolving the interaction requires an explicit approved
transition by the same authorized operator that owns the active conversation.
Acceptance requires a confirmed package whose conversation reference matches the
transition request; no second operator can silently transfer or reassign active
ownership.

### Human Escalation acceptance scenarios

- **Offer without transfer:** Given Customer Support offers escalation, when the
  user has not confirmed, then the conversation enters
  `WAITING_CONFIRMATION`; no handoff is confirmed, no operator owns it, and
  automation remains active.
- **Explicit confirmation:** Given an offer, when the user explicitly confirms,
  then the conversation enters `WAITING_HUMAN` and awaits authorized operator
  acceptance.
- **Waiting:** Given `WAITING_HUMAN`, then no operator owns the conversation yet.
- **Human ownership:** Given an authorized operator accepts a `WAITING_HUMAN`
  conversation with a matching confirmed package, then human ownership becomes
  active and automated responses are suspended.
- **Safe package:** Given challenge-014, then only the minimum sanitized
  diagnostic context is transferred; no AI-created ITSM ticket is opened.
- **Return:** Given active human ownership, when an authorized explicit return
  or resolution transition is requested by the assigned operator, then control
  may return to automation or enter `RESOLVED`; another operator cannot take
  ownership or perform that transition.

Phase 9.9 verification covers typed transitions, allowlisted handoff
sanitization, Router and Customer Support coordination, automation suspension,
and challenge-014 multi-turn behavior. It does not implement Django, a
physical queue, ticket automation, or `/chat`.
