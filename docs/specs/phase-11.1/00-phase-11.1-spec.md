# PHASE 11.1 — Semantic Routing and Runtime Hardening

Status: **SDD DRAFT — implementation requires explicit owner approval**

Type: post-Phase-11 bridge/hardening phase; documentation only
Requirement namespace: `REQ-P11R-*`

## Identity, authority, and historical boundary

This is a new bridge phase between the **closed** Phase 11 Evaluation Runner and future Phase 12. It is deliberately named Phase 11.1 by the project owner, but it is not any of the historical internal Phase 11 steps formerly numbered 11.1–11.6. Historical `REQ-P11-*`, evaluation datasets, reports, decisions, and evidence remain immutable.

The authoritative implementation source is the current `getnet-support` working tree. The new SDD follows the repository convention at `docs/specs/phase-11.1/`; no `project-context.md`, roadmap, or decision-log state is changed by this draft.

`docs/architecture.md` and `docs/development.md` are not present in the authoritative active `getnet-support/docs/` tree. Related context documents with those names may exist elsewhere in the broader Drive/context tree, but are not active project documentation for this SDD unless an authoritative contract explicitly references them.

Phase 10 security/AUDIT contracts, Phase 9 application composition, and the closed Phase 11 evaluation contracts are authoritative dependencies. Evaluation may regress the hardened runtime later, but must never become runtime policy.

## Discovered current-state mismatch

The current `RouterAgent` is a deterministic, lexical/regex router. It invokes its existing security classification first, but ordinary routing has no semantic-intent contract, no conversational route, and no knowledge scope. Consequently, greetings and broad public Getnet questions can become `AMBIGUOUS`; public product questions can enter generic `KNOWLEDGE`; and that retrieval path can admit internal cancellation/process material.

`KnowledgeAgent` correctly returns `INSUFFICIENT_EVIDENCE` when `ContextBuilder` has no structural evidence, and LangGraph already has a `FALLBACK_IF_RAG_INSUFFICIENT` edge. However, once structural context exists it renders arbitrary provider prose as `KnowledgeResultStatus.ANSWERED`; a prose answer that says it lacks knowledge is therefore not a typed insufficient-evidence outcome. The fallback edge cannot safely use that prose as a trigger.

The approved public Getnet registry and public-origin metadata exist, while the demonstrated curated publication path is R1/R2 internal material. An **approved source registry** is not **local source content**, and neither is a **published RAG document/chunk**. Therefore a public scope cannot be assumed available merely because a registry record exists. Scoped retrieval availability must be checked against the real local RAG/PostgreSQL boundary before implementation treats persistent public RAG as available.

The current Phase 10 Router security owner normalizes accents and has typed classifications, but its ordinary phrase patterns do not compositionally cover all Portuguese override-plus-protected-target requests. It must be hardened in that same deterministic owner, not delegated to an LLM.

## Objectives

1. Preserve deterministic security, authorization, tool, source, Web, and handoff policy.
2. Add closed-schema semantic intent understanding through the existing provider-neutral **async** LLM boundary, without tool calling.
3. Deterministically map a typed intent to approved route, capability set, `WebSearchPolicy`, and knowledge scope.
4. Separate `INTERNAL` and `PUBLIC_GETNET` retrieval before lexical, semantic, and RRF candidate selection.
5. Make knowledge generation produce a validated typed `ANSWERED` or `INSUFFICIENT_EVIDENCE` outcome; never infer it from rendered prose.
6. Reuse the existing FastAPI, `ChatApplicationService`, LangGraph, agents, HybridRetriever, ContextBuilder, WebKnowledge, OPS, Human Escalation, and SecurityAuditService boundaries.

## Non-goals and prohibitions

This phase does not replace LangGraph, PostgreSQL/pgvector, FastEmbed, WebKnowledge, Human Escalation, or the Phase 11 evaluation system. It does not add Django, frontend, persistent memory, schema/migrations, IAM changes, Docker, production deployment, external services, external-provider validation, datasets, or Challenge changes.

Implementation must not add one regex per failed sentence, hardcode Challenge answers/questions, make the LLM select tools or authorize OPS, let Web replace internal rules or customer facts, treat non-empty Top-5 as sufficient, parse generated prose for state, duplicate policy in `scripts/chat_cli.py`, or mutate Phase 11 evidence to obtain a green regression.

## Invariants

* Security preflight is deterministic and terminal before semantic classification.
* The semantic model receives no tools and cannot emit routes, capabilities, scope, Web policy, authorization, or handoff decisions.
* Only the deterministic mapper can create a `RouterDecision`; trusted auth/context remains owned by `ChatApplicationService` and OPS boundaries.
* `KnowledgeScope` is trusted typed state: semantic intent → deterministic mapper → `RouterDecision` → graph state → knowledge request/agent → HybridRetriever → both retrieval channels/repository predicates. It is never reconstructed from query text, LLM output, Web output, or a user filter.
* Scope filtering is applied consistently to lexical and semantic retrieval before RRF; provenance, Top-5, grounding, and current source identity remain intact.
* Security preflight may remain synchronous internally, but provider-backed semantic routing is natively async through FastAPI/LangGraph; sync-over-async workarounds are prohibited.
* `SECURITY_BLOCK` causes sanitized Phase 10 AUDIT and zero downstream Knowledge, Web, OPS, Human, or provider continuation.
* Existing Phase 11 RAG and Challenge artifacts are regression baselines, not rewritten acceptance inputs.

## Requirement families

| Family | Count | Purpose |
|---|---:|---|
| `CORE` | 6 | ownership, safety, versioning, dependency direction |
| `ROUTER` | 10 | semantic intent and deterministic mapping |
| `KNOW` | 8 | scope, public-corpus prerequisite, and typed knowledge outcomes |
| `WEB` | 6 | deterministic Web policy and fallback |
| `SEC` | 7 | deterministic security hardening |
| `CONV` | 4 | bounded conversational experience |
| `INTEG` | 6 | application/graph/API/CLI integration |
| `VAL` | 6 | evidence and regression gates |
| **Total** | **53** | individually traced in `05-validation-spec.md` |

## Implementation order after approval

1. Freeze the async typed contracts, intent mapper, scope propagation policy, and safe failure behavior with unit tests.
2. Harden the existing deterministic Phase 10 security classifier and prove precedence/non-overblocking.
3. Add semantic classifier adapter and deterministic Router mapping; add conversational route only through the current Router/graph contracts.
4. Inspect the real local public corpus; if absent, stop persistent-public-RAG publication work pending the owner decision defined in `02`.
5. Add scoped retrieval predicates and prove identical scope propagation through both channels before RRF, without a second retriever.
6. Add typed generation sufficiency and wire existing LangGraph fallback transitions.
7. Integrate safely through application/API/CLI presentation, then run unit, integration, E2E, manual CLI, and Phase 11 regression evidence.

## Definition of done

Implementation may be proposed complete only after every `REQ-P11R-*` has reproducible evidence, all normal tests are network-free, production modules do not depend on evaluation, public/internal scope is proved, all listed security terminal guarantees hold, and historical Phase 11 artifacts remain unchanged. A durable decision and project-context/roadmap update occur only after reviewed implementation and validation.
