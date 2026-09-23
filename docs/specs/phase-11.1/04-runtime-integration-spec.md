# Phase 11.1 — Runtime Integration Contract

## Reuse, not replacement

The implementation shall preserve the authenticated path:

```text
FastAPI /chat -> ChatApplicationService -> RouterAgent -> LangGraphOrchestrator
-> Knowledge / WebKnowledge / CustomerSupport / HumanEscalation / SecurityAuditService
-> response translation
```

`ChatApplicationService` remains the owner of principal identity, role, trusted OPS context, human actions, and request translation. `OperationalTools` and repositories remain the owner of private fact access. The semantic classifier is an injected provider-neutral, asynchronous structured-output boundary only; it cannot call tools.

The Router semantic operation and LangGraph router node are natively async when a provider classification is required. Security preflight runs first; then the graph awaits classification through its normal async execution path. No sync facade may call the provider through `asyncio.run()`, nested event loops, blocking waits, or ad-hoc thread wrappers.

LangGraph is not replaced. It carries `RouterDecision.knowledge_scope` as immutable typed orchestration state into a typed knowledge request and then unchanged through `KnowledgeAgent`, `HybridRetriever`, both retrievers, and both repository predicates. It retains its existing security terminal, cooperative knowledge/support sequence, Web fallback edge, and Human Escalation state machine. A public RAG insufficiency activates the existing fallback edge; an internal insufficiency does not become unrelated public knowledge. The assembler must use typed result statuses rather than generated answer wording.

## API, observability, and CLI

Any route/intent/scope/status additions are additive, validated, and safe to expose only through an allowlisted transport representation. Internal raw classifier output, security semantics, provenance internals, protected messages, or source filters do not become public `/chat` fields. Tests/instrumentation may observe typed internal decisions through existing composition seams.

`scripts/chat_cli.py` remains a manual harness over the real application boundary. It may later render approved typed public route/intent/scope/status fields, but must not route, secure, retrieve, decide fallback, or emulate business behavior itself.

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
