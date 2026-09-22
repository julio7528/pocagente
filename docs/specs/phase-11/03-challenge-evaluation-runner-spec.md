# Phase 11 — Challenge Evaluation Runner

Status: Phase 11.4 implementation complete and validated with deterministic
authenticated execution of all 14 dataset-v1 scenarios. Phase 11.5 metrics and
reporting are implemented; Phase 11.6 revalidation records Phase 11 closure
CLOSED. Challenge evidence remains 14/14 PASS and was not changed by the RAG
closure remediation.

## Execution

The challenge runner executes all 14 versioned `challenge-*` scenarios through
the authenticated application boundary used by existing deterministic E2E
tests. It reuses Router, LangGraph, agents, tools, Web fallback, Human
Escalation, security, and `/chat`; it does not copy their logic.

The runner compares behavior through an explicit dataset adapter. Conceptual
route values in YAML are not required to equal runtime enum names. Typed
observations determine selected route/state, invoked capabilities, forbidden
capabilities, authorization, evidence/FACT versus INFERENCE boundaries, safe
response class, and AUDIT behavior.

The adapter is policy-driven by the declared route, capabilities, tool classes,
freshness, RAG, and security fields. Scenario IDs are retained only for
traceability; they must not select runtime policy. Message text is never parsed
and no second Router is introduced.

## Capability and policy assertions

Expected capabilities must be observed as typed calls; forbidden capabilities
must be asserted absent. Web fallback is evaluated only where the route and
orchestration permit it. OPS requires the existing authorization/context
boundary. `challenge-013` requires Phase 10 blocking, typed sanitized AUDIT,
safe response, and zero RAG/Web/OPS/Human/provider continuation.

Exact response wording is not a baseline assertion because the dataset does not
require it. Public response safety and absence of internal metadata remain
mandatory.

## Challenge-014 multi-turn contract

Challenge-014 is one scenario with two ordered turns, not two independent
requests. The runner creates one conversation state, executes diagnosis and
Customer Support evidence first, checks the offer without transfer, then sends
the explicit confirmation. Only then may Human Escalation run and transition
to human ownership. Automation remains suspended under human ownership.

The exact state sequence is:

`BOT` --support offer--> `WAITING_CONFIRMATION` --explicit client confirmation--> `WAITING_HUMAN`

At `WAITING_HUMAN`, no operator owns the conversation, `assigned_operator_id`
is absent, and `automation_suspended` is false. The evaluation runner may then
perform a controlled verification continuation with an authorized
`SUPPORT_AGENT` acceptance:

`WAITING_HUMAN` --authorized operator ACCEPT--> `HUMAN`

Only at `HUMAN` is `assigned_operator_id` present and `automation_suspended`
true. The historical dataset remains two client turns; operator acceptance is
an evaluation verification action, not a silently added client turn.

The runner must verify no automatic escalation, no AI ticket creation, no
external ITSM integration, and minimum necessary handoff context. It must
preserve the existing conversation/handoff state rather than reconstructing it
from isolated turn results.

## Result

Each scenario records ordered turn outcomes, mapped route/state, expected and
forbidden capability observations, authorization/evidence observations,
security/AUDIT observations where applicable, status, and controlled evidence.

## Implemented evidence

`apps/agent_api/app/evaluation/challenge_runner.py` consumes the loaded suite
and `adapt_challenge_scenario(...)` in YAML order. It composes the actual
authenticated `/chat` application boundary with production Router, LangGraph,
Customer Support, OperationalTools, Human Escalation, and SecurityAuditService.
Only deterministic knowledge, Web, OPS repository, interpretation-provider,
and audit-sink boundaries are substituted.

Results are frozen typed observations with per-scenario and per-turn invocation
deltas. They record capability/tool execution, route/state, authorization,
FACT/INFERENCE structure, direct sanitized AUDIT events, and public-response
safety without retaining raw messages or implementation objects. The runner
does not use scenario IDs to select policy and does not implement aggregate
metrics, report files, or exact-answer grading.

The conditional persistent-RAG/Web scenario includes a supporting
insufficient-evidence branch within its one scenario result. Challenge-014
preserves one conversation across its two client turns and controlled operator
continuations: `WAITING_CONFIRMATION`, `WAITING_HUMAN`, authorized `HUMAN`,
automation suspension, unauthorized-operator rejection, and assigned-operator
resolution. No external provider, database, ticket, or ITSM action is used.

## Final observation-integrity correction

Conditional fallback observations are now measured from the actual primary
and insufficient-evidence request deltas plus a capability-name-only sequence.
The fallback branch passes only when observed `knowledge` precedes observed
`web`; the primary sufficient-evidence branch must observe Knowledge and no
Web. The deterministic composition has no persistent-publication boundary, so
the result records that architectural absence rather than a fabricated write
counter.

Authorization, expected tools, FACT/INFERENCE structure, security/audit, and
the complete v1 forbidden-capability vocabulary are typed PASS/FAIL dimensions.
OPS scenarios include one supporting denied request with measured zero
repository calls and controlled response. Security requires recorded typed
sanitized AUDIT events with actual `SecurityAction.BLOCK` and measured zero
downstream continuation. Challenge-014 additionally verifies preserved HUMAN
ownership, assigned operator, and automation suspension after a different
operator is rejected.

The final reconciliation additionally requires the central conditional gate to
reject a primary request that skipped Knowledge or invoked Web prematurely,
even if the supporting fallback branch succeeds. The security gate independently
checks the actual observed action tuple is non-empty and contains only
`SecurityAction.BLOCK`; a derived boolean alone is not sufficient evidence.
