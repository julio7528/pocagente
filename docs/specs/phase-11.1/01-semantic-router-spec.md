# Phase 11.1 — Semantic Router Contract

## Boundary

`RouterAgent` remains the only producer of controlled routing decisions. Its sequence becomes:

```text
RouterRequest
  -> deterministic Phase 10 security preflight
  -> await closed-schema semantic intent classifier
  -> deterministic intent/policy mapper
  -> RouterDecision(route, capabilities, WebSearchPolicy, KnowledgeScope, reason)
```

`SECURITY_BLOCK` is deliberately not a semantic intent. Security may terminate before the classifier and retain the current typed `SecurityClassification` tuple.

## Closed semantic contract

The provider-neutral LLM boundary shall expose a schema-bound structured-output operation (an additive interface/adapter, not tool calling). Its exact class names are implementation details, but the validated frozen, `extra="forbid"` result must contain exactly one supported intent and a schema version. Free text rationale, confidence, tool selection, route names, permissions, source filters, and policy values are not accepted as authority.

The v1 intent vocabulary is closed:

| Intent | Deterministic runtime mapping |
|---|---|
| `CONVERSATIONAL` | new bounded conversational route/capability; no RAG, Web, OPS, Human, or provider tool execution |
| `INTERNAL_KNOWLEDGE` | `KNOWLEDGE`, `KnowledgeScope.INTERNAL`, Web `NONE` |
| `PUBLIC_GETNET_KNOWLEDGE` | `KNOWLEDGE`, `KnowledgeScope.PUBLIC_GETNET`, `FALLBACK_IF_RAG_INSUFFICIENT` |
| `CUSTOMER_SUPPORT` | `CUSTOMER_SUPPORT`; OPS remains subject to trusted auth/context |
| `EXPECTED_VS_OBSERVED` | `KNOWLEDGE_AND_CUSTOMER_SUPPORT`, internal rules plus authorized controlled observation |
| `GENERAL_PUBLIC_INFORMATION` | bounded existing Web path, no internal/public Getnet RAG substitution |
| `CURRENT_PUBLIC_INFORMATION` | existing Web route with `REQUIRED` freshness policy |
| `HUMAN_REQUEST` | existing Human Escalation route/state machine |
| `AMBIGUOUS` | current bounded clarification behavior |

The mapper, not the model, rejects impossible combinations. `EXPECTED_VS_OBSERVED` without trusted operational context degrades safely; it cannot unlock OPS. The mapper may use authenticated context supplied by the application, never model output.

`RouterDecision.knowledge_scope` is an application-owned, typed field. It is populated only by this mapper and is propagated unchanged through orchestration and the retrieval request path specified in `02`; semantic/query wording, the user, the LLM, and Web evidence cannot choose or mutate it.

## Native async classification

The provider-backed semantic operation is natively asynchronous. The approved conceptual boundary is `await RouterAgent.route(...)`, or an awaited `SemanticIntentClassifier.classify(...)` followed immediately by the deterministic mapper. The exact decomposition is secondary; the externally consumed semantic-routing path must be compatible with the current async `LLMProvider.generate(...)`, FastAPI request handling, and LangGraph async execution.

Security preflight executes before any provider await and may remain synchronous internally. The LangGraph router node must be async when semantic classification is needed and use the framework's normal async graph execution. Implementation must not use `asyncio.run()` in an active event loop, nested-loop execution, blocking waits, ad-hoc thread wrappers intended to retain the old synchronous signature, or any other sync-over-async provider bridge. A security block must return without invoking the semantic provider.

## Dominant intent

Classification evaluates the whole normalized message. A greeting/thanks prefix is subordinate to a substantive request: `Oi` is conversational; `Oi, quero saber quais produtos a Getnet oferece` is public Getnet knowledge; `Bom dia, minha maquininha não conecta` follows the substantive support/knowledge policy. Security always dominates every greeting or semantic intent.

## Classifier failure

Security preflight always runs first. On timeout, provider error, malformed JSON, unknown enum, or schema validation failure, the application records a controlled reason and grants no additional authority. A reviewed compatibility fallback to the existing deterministic Router is allowed only for a fixed, non-escalating subset proven by tests; otherwise return `AMBIGUOUS`/controlled failure. It must not manufacture OPS access, public-Web policy, scope, or a security allow decision.

## Requirements

* `REQ-P11R-ROUTER-001`: security preflight precedes semantic classification and is terminal.
* `REQ-P11R-ROUTER-002`: semantic output is a closed, validated, frozen structured contract.
* `REQ-P11R-ROUTER-003`: semantic classifier has no tool/action/authorization authority.
* `REQ-P11R-ROUTER-004`: deterministic mapper owns intent-to-route/capability/policy/scope mapping.
* `REQ-P11R-ROUTER-005`: dominant substantive intent cannot be swallowed by conversational tokens.
* `REQ-P11R-ROUTER-006`: trusted auth/context, not classifier output, gates OPS/cooperative flows.
* `REQ-P11R-ROUTER-007`: invalid/unavailable classifier output degrades without privilege escalation.
* `REQ-P11R-ROUTER-008`: mappings are auditable and reject unsupported intent/policy combinations.
* `REQ-P11R-ROUTER-009`: route state changes occur only after structured output validation and mapping.
* `REQ-P11R-ROUTER-010`: semantic intent classification uses a native async FastAPI/LangGraph-compatible path; sync-over-async event-loop workarounds are prohibited.
