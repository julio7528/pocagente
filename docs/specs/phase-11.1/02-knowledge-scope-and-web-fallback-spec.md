# Phase 11.1 — Knowledge Scope, Sufficiency, and Web Fallback

## Scoped retrieval

Introduce an application-owned `KnowledgeScope` equivalent with at least `INTERNAL` and `PUBLIC_GETNET`; a non-RAG scope may be represented explicitly for conversational/general-Web journeys. Scope is selected solely by the deterministic Router mapper.

The scope is not an annotation or a late retrieval heuristic. The required typed propagation path is:

```text
SemanticIntent
 -> deterministic Router mapper
 -> RouterDecision.knowledge_scope
 -> LangGraph/OrchestrationState
 -> typed Knowledge capability request
 -> KnowledgeAgent
 -> HybridRetriever
 -> LexicalRetriever + SemanticRetriever
 -> RAGRepository lexical + semantic predicates
```

The two repository calls receive the same immutable scope predicate in one retrieval journey, before either channel returns candidates and before RRF. The semantic query text, normalized lexical query text, user input, LLM output, Web agent, and RRF must not rediscover, widen, narrow, or select scope. A user cannot supply an arbitrary source scope.

The existing `HybridRetriever` remains authoritative: PostgreSQL FTS, local FastEmbed, pgvector, RRF, Top-5, provenance, and ContextBuilder are preserved. Its lexical and semantic repository calls must receive the same approved scope predicate before candidate selection/RRF. RRF ranks only candidates already admitted by that scope. A public Getnet request must therefore never rank arbitrary internal cancellation/process chunks merely because terms overlap, and an internal request cannot widen to public material before an explicitly approved Web fallback.

The predicate must be derived from persisted trusted metadata already represented by source origin/type/approval/activity/domain/registry identity; it must not use filenames or user-supplied filters.

### Public Getnet corpus prerequisite

`knowledge/internal/cancellation-process/public/sources.yaml` is an approved registry, not content. `docs/rag-ingestion.md` defines that the registry is parsed and validated **without crawling or fetching URLs**. The local public directory currently supplies the registry rather than locally captured page bodies, while documented publication covers curated internal R1/R2 documents. The implementation must first inspect the approved local PostgreSQL/RAG boundary for active, approved, correctly typed public Getnet documents/chunks.

If those documents already exist, the implementation reuses their trusted provenance. If they are absent, implementation may still deliver semantic `PUBLIC_GETNET` routing, scope enforcement, typed insufficiency, and the approved Web fallback; it must stop before persistent public-corpus publication unless the owner explicitly approves one of these content-acquisition paths:

* **Option A — controlled acquisition:** fetch only exact existing approved Getnet registry URLs; no link discovery, recursive crawling, search-engine discovery, unapproved domain, or automatic registry expansion. Downloaded material remains untrusted DATA and retains URL/title/checksum/retrieval provenance before preparation and publication through the existing controlled pipeline.
* **Option B — owner-supplied snapshots:** accept reviewed local HTML/Markdown/PDF/text snapshots mapped to existing approved registry records; no external fetch; prepare and publish through the existing controlled pipeline.

This SDD authorizes neither option. Registry approval never substitutes for local content or published chunks, and internal chunks cannot satisfy public-corpus availability. The target architecture remains persistent public Getnet RAG grounded in approved website content, with Web as controlled live fallback—not a permanent replacement for the Challenge-required public corpus.

## Authority and Web policies

| Journey | First evidence | Web policy | Prohibition |
|---|---|---|---|
| internal process/rule | scoped internal RAG | `NONE` | public Web cannot override internal rule |
| stable public Getnet | scoped public Getnet RAG | fallback only on typed insufficiency; official Getnet sources prioritized | no internal scope substitution |
| current public information | existing WebKnowledge | `REQUIRED` | stale RAG-only result |
| general public information | bounded existing Web capability | approved general public policy | no internal RAG/OPS substitution |
| customer-specific fact | Customer Support + authorized OPS | `NONE` | Web/RAG as private current-state source |
| security | none | `NONE` | any downstream continuation |

## Typed knowledge outcome

Keep `KnowledgeResult` as the public-safe result shape but derive its status from a validated structured generation outcome, not free-form prose. The validated outcome has at minimum `ANSWERED` and `INSUFFICIENT_EVIDENCE`, cites only evidence IDs supplied by `GroundedContext`, and cannot invent citations, source scope, permissions, or tool actions. An insufficient outcome carries no material answer. Invalid structured output/provider failure is controlled and is not transformed into an answer.

`ContextBuilder` continues to create grounding context, but structural non-emptiness alone cannot establish an answer. Scope admission plus the typed outcome establish whether the existing graph sees `ANSWERED` or `INSUFFICIENT_EVIDENCE`. The existing fallback edge activates only after the latter; a provider failure is not silently masked as successful Web evidence. If Web is also insufficient, return bounded typed insufficiency and preserve existing human-handoff policy.

## Requirements

* `REQ-P11R-KNOW-001`: scope is application-selected and has explicit internal/public Getnet semantics.
* `REQ-P11R-KNOW-002`: lexical and semantic candidate retrieval apply the identical trusted scope filter before RRF.
* `REQ-P11R-KNOW-003`: public Getnet requests cannot consume internal process sources.
* `REQ-P11R-KNOW-004`: public scope availability is verified; absence yields controlled typed behavior.
* `REQ-P11R-KNOW-005`: generation yields validated typed sufficiency, not prose-derived status.
* `REQ-P11R-KNOW-006`: answered output cites only supplied approved grounding evidence.
* `REQ-P11R-KNOW-007`: insufficient/error outcomes cannot be represented as completed answered knowledge.
* `REQ-P11R-KNOW-008`: public-corpus availability is proven from trusted published public chunks; absent content requires visible controlled behavior and explicit owner approval before acquisition/publication.
* `REQ-P11R-WEB-001`: stable public Getnet uses public RAG first and falls back only on typed insufficiency.
* `REQ-P11R-WEB-002`: current public information requires existing Web capability.
* `REQ-P11R-WEB-003`: general public information uses bounded Web rather than ambiguous/internal RAG.
* `REQ-P11R-WEB-004`: public Web never replaces internal rules or authorized private observations.
* `REQ-P11R-WEB-005`: Web fallback preserves transient/non-persistent live evidence.
* `REQ-P11R-WEB-006`: no Web executes after security block or for prohibited scope/policy.
