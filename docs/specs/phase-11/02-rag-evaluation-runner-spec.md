# Phase 11 — RAG Evaluation Runner

Status: Phase 11.3 typed RAG evaluation boundary implemented, observation-
integrity validated, and closure-remediation dataset v1.1 evidence complete.

## Execution modes and evidence classes

### Runner Contract Mode

This mode validates loaders, schemas, versioned adapters, case classification,
orchestration, metric formulas, aggregation, reporting, and failure handling.
It may use typed retrieval/provider doubles, synthetic outputs, and capability
spies. Its results are contract evidence only and MUST NOT be used as official
expected-source Top-5 or provenance-quality evidence.

### Local RAG Evaluation Mode

This mode is the official retrieval-quality gate for applicable dataset v1
cases. It executes the approved local pipeline with real local FastEmbed query
embeddings, PostgreSQL lexical FTS, pgvector semantic retrieval, approved RRF,
final Top-5 ranking, `RetrievedChunk`, `RetrievalProvenance`, and
`ContextBuilder`. The local POC PostgreSQL/pgvector database is mandatory for
Top-5 and provenance metrics and cannot be replaced by repository fixtures.

The mode remains local, bounded to approved POC data, reproducible, and
network-free regarding external providers. DeepSeek and Tavily are not
required for retrieval-quality metrics; generation may be disabled/replaced
through a separately reviewed seam when the metric does not require it. Real
external providers remain separately opt-in.

If local PostgreSQL/pgvector or its approved POC corpus is unavailable, the
official Top-5/provenance gate is unavailable/failing for that run. It MUST NOT
silently fall back to retrieval doubles. This infrastructure is neither a
repository double nor an external-provider validation mode.

### External Provider Validation

DeepSeek, Tavily, and any other external HTTP provider belong to a distinct,
explicit opt-in evidence class. They are not required for Local RAG Evaluation
Mode when a retrieval-quality metric does not require generation.

## Execution boundary

The RAG runner executes every declared `rag-*` case through the approved
application evaluation seam. It does not call retrieval SQL directly, rebuild
PostgreSQL FTS, pgvector, RRF, Top-5 selection, grounding, Router security, or
agent policy. Runner Contract Mode injects typed repository/provider doubles.
Local RAG Evaluation Mode invokes the approved local retrieval boundary.
External Provider Validation alone is separately opt-in.

Security cases are submitted to the Router/application boundary. If blocked,
the runner records zero retrieval, Web, OPS, provider, and Human capability
calls and evaluates security/AUDIT/redaction criteria. It never invokes RAG
just to obtain a Top-5 score for a blocked request.

## Case classes

The versioned adapter distinguishes ordinary evidence-backed cases, declared
rule-versus-observed comparisons such as `rag-020`, protected/security cases,
and the v1.1 explicit insufficient-evidence class. No-evidence behavior is
declared by the reviewed dataset version; it is never inferred from an empty
result.

## Observations

For applicable retrieval cases, the typed evaluation boundary exposes:

- final Top-5 source identities and ranks;
- expected-source matches;
- provenance/source metadata;
- grounding/evidence state;
- answer/result state and supported claims;
- unsupported material-fact observations.

The public `/chat` response is not used as a substitute for typed internal
evidence. Evaluation must not expose that evidence through `/chat`.

For security cases, observations include the Router decision, typed semantic
set when the current Router blocks, sanitized AUDIT event set, safe response
class, and zero forbidden calls. The runner dispatches declared security cases
to this security boundary without invoking retrieval merely for scoring. A
non-blocking Router result is retained as an authentic `FAIL` observation; the
runner does not add a second classifier or reinterpret the question. Raw
requests and secrets are not evaluation artifacts.

## Per-case result

Each case produces `case_id`, suite/dataset version, runner version, case
class, execution mode, status, evidence references, metric applicability, and
a controlled reason. Status is one of `PASS`, `FAIL`, `NOT_APPLICABLE`, or
`NOT_MEASURABLE`. A malformed case is a suite validation failure, not a case
pass.

## Source and security rules

Expected-source success uses the complete retrieval-applicable dataset-v1
Evaluation Source Manifest:
normalized expected path -> exact reviewed `document_key` plus exact reviewed
`source_reference`, compared against typed `RetrievalProvenance`. Existing
runtime publication registries are inputs, not presumed full manifest coverage.
The official run cannot begin until coverage is 6/6 (100%) for current dataset
v1 retrieval paths; security-only expected sources are not retrieval inputs.
Response text, titles, basenames, substrings, UUIDs, and fuzzy/LLM matching
are prohibited. Protected requests are evaluated for block, audit,
sanitization, and terminal behavior; they are excluded from retrieval
denominators.

Dataset v1.0 exposed no typed claim-support contract, so its unsupported-fact
and insufficient-evidence dimensions remain historical `NOT_MEASURABLE`
evidence. Dataset v1.1 supplies a reviewed deterministic structural contract:
typed claim ID and value, exact allowed source identity, exact section, and an
exact support rule. The runner observes claim support without generating or
parsing answer prose and without an LLM judge. V1.1 also declares an explicit
insufficient-evidence case; the runner records the approved grounding state
and verifies that no material answer claim is produced.

## Phase 11.3 implementation evidence

`apps/agent_api/app/evaluation/rag_runner.py` consumes the versioned dataset,
the exact Evaluation Source Manifest, the existing `HybridRetriever`, the
existing `ContextBuilder`, and the existing Router plus `SecurityAuditService`
boundary. `rag_results.py` contains frozen typed observations with no chunk
content or raw request fields. Runner Contract Mode is covered by deterministic
double tests; the opt-in Local RAG run processed all 25 dataset cases using
local PostgreSQL/pgvector and FastEmbed without generation. The observed run
was 19 PASS, 5 FAIL, and 1 NOT_MEASURABLE; the two security cases remained out of retrieval and
were retained as authentic Router/security findings rather than being
reclassified or tailored.

## Observation-integrity correction

Security observations are produced by executing the existing
`LangGraphOrchestrator` security terminal with evaluation-only invocation
spies at the Knowledge/retrieval, Web, Customer Support/OPS, provider, and
Human Escalation boundaries. `forbidden_call_counts` is a per-case delta
snapshot of measured invocations, not an initialized assertion. A valid
security result requires all measured counts to be zero; a non-blocking Router
result remains `FAIL`.

Retrieval observations retain one frozen
`RetrievedProvenanceObservation` per final result containing both exact
`document_key` and `source_reference`, plus the manifest match. Structural
retrieval, provenance, grounding, and semantic-conclusion dimensions are
separate. A successful `RULE_VS_OBSERVED` retrieval is therefore
`NOT_MEASURABLE` with `SEMANTIC_INFERENCE_NOT_MEASURABLE`, never full `PASS`.

Provenance completeness is independent of expected-source relevance. A
non-empty result set whose typed provenance contains both required identity
fields for every result may have `provenance_status=PASS` while
`expected_source_found=False`; the case can still be structurally `FAIL` due
to the expected-source requirement. Empty retrieval always has failing
provenance status.

Redaction is represented by `PASS`, `FAIL`, or `NOT_APPLICABLE`. Dataset
questions that supply no secret-shaped value use `NOT_APPLICABLE`; dedicated
synthetic tests provide an explicit fake fragment and verify its absence after
the real audit sanitizer boundary. Local RAG mode requires a loaded validated
supported dataset and its matching complete manifest coverage before execution.

Security forbidden-call counts are per-case deltas between observer snapshots;
the observer may remain cumulative for lifetime diagnostics, but prior cases
cannot contribute to a later observation. Audit actions are copied directly
from recorded `SanitizedSecurityEvent.action_taken` values. Route or
orchestration status cannot synthesize a successful audit action, and no
recorded event produces no audit-action evidence.

## Closure-remediation evidence

The reviewed v1.1 dataset contains 27 cases: 22 `RETRIEVAL`, 1
`RULE_VS_OBSERVED`, 3 `SECURITY`, and 1 `INSUFFICIENT_EVIDENCE`. The official
run invokes retrieval 24 times: 23 quality-denominator cases plus the explicit
no-evidence observation. The production Router's centralized Phase 10 security
semantic owner now recognizes the missing Portuguese credential, database,
and protected-infrastructure aliases before normal Knowledge/Ambiguous routing.
All three v1.1 security cases block, emit typed sanitized AUDIT events with
`SecurityAction.BLOCK`, and have zero forbidden continuation.

PostgreSQL FTS query normalization now converts natural-language questions to
a bounded deduplicated OR query after removing question boilerplate. This fixes
the prior all-term `websearch_to_tsquery` overconstraint without changing
Top-K, RRF, candidate limits, source identity, corpus, or evaluation policy.
Fresh official evidence has 21/23 expected-source matches and 23/23 complete
provenance. The remaining misses (`rag-021`, `rag-023`) stay visible as
authentic per-case failures; the 0.90 aggregate acceptance threshold passes.
