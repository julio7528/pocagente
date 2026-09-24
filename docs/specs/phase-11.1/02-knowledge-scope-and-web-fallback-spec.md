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

`knowledge/internal/cancellation-process/public/sources.yaml` is the single authoritative public-source registry, not content. The existing preparation pipeline parses and validates this registry without acquiring page bodies. The owner has now explicitly authorized Option A: controlled acquisition of exact URLs already present as approved, active, ingestion-enabled registry records, followed by the existing preparation and atomic publication path. This authorization permits neither crawling nor child-link discovery, arbitrary Web/search-result ingestion, registry expansion, nor ingestion of dynamically discovered URLs. The implementation must inspect the local PostgreSQL/RAG boundary before treating a registry entry as published content.

If those documents already exist, the implementation reuses their trusted provenance. If they are absent, this remediation may acquire only exact validated registry URLs and publish through the current pipeline. Registry approval never substitutes for successfully acquired content or published chunks, and internal chunks cannot satisfy public-corpus availability. If no exact approved URL covers a requested topic, that is a coverage gap for owner review; do not add a URL. Stable approved content is served from persistent public RAG when sufficient, while absent, insufficient, or freshness-sensitive evidence retains the controlled Web fallback.

Public acquisition is bounded to the exact URL in a fully validated registry record. Redirects may only remain on that record's approved host. The fetcher may not discover, follow, persist, or ingest links. Public HTML extraction produces normalized text and structural headings/lists for the existing deterministic chunker. Public provenance includes registry source identity, exact approved reference, retrieval time, content checksum, and document/chunk provenance. Preparation, embeddings, and publication use the existing `IngestionPreparationService`, FastEmbed adapter, and transactional `RAGPublicationService`; a failed operation must leave prior active chunks intact and expose no partial replacement. Web evidence remains transient and cannot enter this publication path.

* **Option A — controlled acquisition:** fetch only exact existing approved Getnet registry URLs; no link discovery, recursive crawling, search-engine discovery, unapproved domain, or automatic registry expansion. Downloaded material remains untrusted DATA and retains URL/title/checksum/retrieval provenance before preparation and publication through the existing controlled pipeline.
* **Option B — owner-supplied snapshots:** accept reviewed local HTML/Markdown/PDF/text snapshots mapped to existing approved registry records; no external fetch; prepare and publish through the existing controlled pipeline.

The target architecture remains persistent public Getnet RAG grounded in approved website content, with Web as controlled live fallback—not a permanent replacement for the Challenge-required public corpus.

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
* A location-dependent current question such as a weather forecast must request the missing city/region before searching; it must not silently assume a location from search ranking or deployment defaults.
* `REQ-P11R-WEB-003`: general public information uses bounded Web rather than ambiguous/internal RAG.
* `REQ-P11R-WEB-004`: public Web never replaces internal rules or authorized private observations.
* `REQ-P11R-WEB-005`: Web fallback preserves transient/non-persistent live evidence.
* `REQ-P11R-WEB-006`: no Web executes after security block or for prohibited scope/policy.
* `REQ-P11R-KNOW-010`: approved active ingestion-enabled public registry records become retrievable `PUBLIC_GETNET` content only after successful controlled publication through the existing pipeline.
* `REQ-P11R-KNOW-011`: acquisition validates the single authoritative registry and fetches only each record's exact approved URL; crawling, child-link discovery, arbitrary search-result ingestion, unapproved redirects, and automatic registry expansion are prohibited.
* `REQ-P11R-KNOW-012`: each published public document/chunk preserves approved source identity, exact reference, retrieval time, checksum, and existing typed provenance.
* `REQ-P11R-KNOW-013`: public preparation, embedding, and publication are atomic per document; failures preserve the last valid active publication and create no partially retrievable chunk set.
* `REQ-P11R-KNOW-014`: stable public Getnet evidence that is sufficiently represented in persistent `PUBLIC_GETNET` RAG is answered there before Web is considered.
* `REQ-P11R-WEB-007`: typed missing/insufficient or freshness-sensitive evidence retains the existing governed Web behavior; live Web results remain transient and are never auto-published.
