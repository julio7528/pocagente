# Phase 11.1 — Runtime Integration Contract

## Reuse, not replacement

The implementation shall preserve the authenticated path:

```text
FastAPI /chat -> ChatApplicationService -> RouterAgent -> LangGraphOrchestrator
-> Knowledge / WebKnowledge / CustomerSupport / HumanEscalation / SecurityAuditService
-> response translation
```

`ChatApplicationService` remains the owner of principal identity, role, trusted OPS context, human actions, and request translation. `OperationalTools` and repositories remain the owner of private fact access. The semantic classifier is an injected provider-neutral, asynchronous structured-output boundary only; it cannot call tools.

OPS authorization and operational selection are separate. Authorization is derived only from trusted authenticated application claims/context and is checked before any OPS planning or tool call. An optional protocol/run selector may come from trusted preselection or from a validated strict typed plan over the current message; a selector never establishes authorization. Authorized discovery plans may omit a selector when the approved operation, such as recent-protocol listing, does not need one.

Authorized Customer Support may use an LLM-generated strict typed operational investigation plan over an application-owned allowlist of read-only evidence categories. The closed plan contains an objective, bounded protocol/run/limit selectors, optional bounded discovery criteria, and an ordered/deduplicated set of evidence needs. It cannot contain SQL, table/column names, JOINs, arbitrary filters, credentials, routes, authorization, or repository/tool names. Application code validates and dispatches the plan to typed repository-bound operations. Investigation is bounded to at most three rounds. The LLM may synthesize answers from supplied typed facts, explicitly separating FACT from INFERENCE; SQL construction and data access remain in application/repository code.

For questions about required procedure, expected behavior, correctness, remediation, or reprocessing, the deterministic capability mapper may select the existing cooperative INTERNAL Knowledge + Customer Support path. The Knowledge query is formulated from the original question and only selected safe observed facts; it must not use a protocol identifier as the sole process-document query. Internal PDD/SDD evidence and observed OPS facts are combined only in a validated grounded synthesis. Public Web is never procedure authority.

For latest-request discovery, “recent” means greatest `ops.service_requests.created_at` (record/request creation time), with `request_id DESC` as a deterministic tie-breaker. For latest-execution discovery, ordering uses actual `ops.automation_runs.started_at` and/or correlated `ops.execution_log.logged_at`, according to a documented definition of the last execution for a request; database persistence `created_at` and protocol-string ordering are not substitutes. If domain timestamps conflict, the response preserves the discrepancy.

The Router semantic operation and LangGraph router node are natively async when a provider classification is required. Security preflight runs first; then the graph awaits classification through its normal async execution path. No sync facade may call the provider through `asyncio.run()`, nested event loops, blocking waits, or ad-hoc thread wrappers.

LangGraph is not replaced. It carries `RouterDecision.knowledge_scope` as immutable typed orchestration state into a typed knowledge request and then unchanged through `KnowledgeAgent`, `HybridRetriever`, both retrievers, and both repository predicates. It retains its existing security terminal, cooperative knowledge/support sequence, Web fallback edge, and Human Escalation state machine. A public RAG insufficiency activates the existing fallback edge; an internal insufficiency does not become unrelated public knowledge. The assembler must use typed result statuses rather than generated answer wording.

## API, observability, and CLI

Any route/intent/scope/status additions are additive, validated, and safe to expose only through an allowlisted transport representation. Internal raw classifier output, security semantics, provenance internals, protected messages, or source filters do not become public `/chat` fields. Tests/instrumentation may observe typed internal decisions through existing composition seams.

The authenticated `/chat` allowlist may expose the validated semantic intent and closed operational plan for observability. The plan contains only its approved intent and bounded selectors/limit; it never exposes raw model output or authority fields. Authorization remains solely in the trusted application context and is not serialized into the plan.

`scripts/chat_cli.py` remains a manual harness over the real application boundary. It may later render approved typed public route/intent/scope/status fields, but must not route, secure, retrieve, decide fallback, or emulate business behavior itself.

The local developer CLI may default to an explicitly labeled synthetic
`SUPPORT_AGENT` principal with OPS read authorization so that the normal local
invocation exercises the approved POC support path. Explicit `CLIENT` and
unauthorized options remain available. This is CLI-only test identity; it does
not change production authentication, `AuthenticatedPrincipal`, or `/chat`
authorization.

## Requirements

* `REQ-P11R-CORE-001`: production/runtime contracts remain owners; evaluation/CLI do not become policy.
* `REQ-P11R-CORE-002`: Phase 11 historical contracts/evidence remain immutable regression inputs.
* `REQ-P11R-CORE-003`: authority, tools, source scope, and Web policy remain deterministic application decisions.
* `REQ-P11R-CORE-004`: normal hardening tests are network-free and provider-neutral doubles are bounded.
* `REQ-P11R-CORE-005`: no production/customer/credential access is introduced.
* `REQ-P11R-CORE-006`: production packages do not depend on evaluation packages.
* `REQ-P11R-INTEG-001`: authenticated `/chat` and `ChatApplicationService` remain the official execution boundary.
* `REQ-P11R-INTEG-002`: LangGraph reuses existing agents/nodes and does not create a parallel graph.
* `REQ-P11R-INTEG-003`: OPS authorization/context remains enforced at current trusted boundaries.
* `REQ-P11R-INTEG-004`: API/observability additions are typed, additive, and secret-safe.
* `REQ-P11R-INTEG-005`: CLI has no duplicate routing/security/RAG/Web/business logic.
* `REQ-P11R-INTEG-006`: `KnowledgeScope` propagates as trusted typed state from `RouterDecision` through orchestration, KnowledgeAgent, HybridRetriever, both retrieval channels, and both repository queries; it is never reconstructed from user/model/Web output.
* `REQ-P11R-INTEG-007`: OPS authorization and operational selectors are separate; authorization comes only from trusted authenticated application context, while validated natural-language or controlled application selectors never grant authorization.
* `REQ-P11R-INTEG-008`: authorized Customer Support may use a strict typed LLM operational plan only to select an application-owned allowlist of read-only capabilities; the model cannot produce SQL, schema identifiers, arbitrary filters, credentials, or authorization decisions.
* `REQ-P11R-INTEG-009`: Customer Support may correlate approved typed facts from multiple OPS repository operations and use the LLM to formulate an answer while preserving FACT versus INFERENCE separation.
