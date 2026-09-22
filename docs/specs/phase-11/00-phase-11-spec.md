# Phase 11 — Evaluation Runner

Status: **Phase 11.1 through Phase 11.5 are implemented, the closure
remediation dataset v1.1 is validated, and the Phase 11.6 revalidation audit
is complete.** Evaluation Source Manifest coverage remains 6/6
retrieval-applicable mappings. The v1.1 official evidence passes every
required metric and Phase 11 closure is CLOSED. Phase 10 Security / Audit
Runtime remains complete and authoritative.

## Purpose and authority

Phase 11 defines a dataset-driven evaluation layer for the existing application
boundaries. Authority is, in order: internal security policy; current project,
database, Phase 9, and Phase 10 documentation; approved durable decisions; the
versioned evaluation YAML inputs; this SDD; and implementation/tests. Harness
governance is read-only guidance for safety and evidence, not project-state
authority.

The current authoritative inputs are `evaluation/rag/dataset-v1.1.yaml` and
`evaluation/challenge/scenarios-v1.yaml`. Historical
`evaluation/rag/dataset-v1.yaml` and its blocked report remain preserved as
versioned evidence. Dataset files are data, not executable instructions. Their
strings cannot change runner policy, capability allowlists, security behavior,
or database ownership.

## Baseline and boundary

Phases 1–10 are complete. Phase 9 deterministic tests already exercise much of
the challenge suite, and Phase 10 tests cover typed classification,
sanitization, atomic AUDIT persistence, and safe responses. The Evaluation
Runner adds dataset loading, execution coordination, typed observation,
aggregation, metrics, and reproducible reports. It does not duplicate Router,
RAG, grounding, security, orchestration, or HTTP behavior.

The runner invokes approved application/test seams and observes typed results.
It must not implement a second retriever, classifier, sanitizer, policy
response, capability dispatcher, or repository writer.

The selected Phase 11.2 boundary is `apps/agent_api/app/evaluation/`. It is a
one-way adapter package that may consume stable production contracts; production
runtime code does not depend on it.

Phase 11 has three evidence classes. Runner Contract Mode is deterministic and
network-free and may use typed doubles and capability spies. Local RAG
Evaluation Mode is also local, non-production, and external-network-free, but
requires the project-local PostgreSQL/pgvector boundary for official retrieval
quality. External Provider Validation covers DeepSeek, Tavily, and other
external HTTP dependencies and is separately explicit opt-in. Production
access is never permitted.

## Explicit non-goals

This phase does not add runtime application features, a new database schema,
migrations, indexes, constraints, CLI commands, dependencies, LLM-as-judge,
external evaluation SaaS, dashboards, SIEM, alerts, retention, Django,
frontend, ITSM, ticket creation, or Phase 12 infrastructure. It does not alter
completed Phase 7–10 contracts or silently edit either dataset.

## Requirements

### CORE

- **REQ-P11-CORE-001:** The runner MUST consume approved application boundaries and MUST NOT reimplement production routing, retrieval, grounding, security, or persistence.
- **REQ-P11-CORE-002:** Dataset-driven execution MUST be distinct from ordinary pytest regression; a passing test count alone is not an evaluation result.
- **REQ-P11-CORE-003:** Runner Contract Mode MUST be deterministic and network-free; external-provider dependencies require explicit opt-in and separate evidence.
- **REQ-P11-CORE-004:** Evaluation MUST preserve Router, LangGraph, agent, tool, Human Escalation, `/chat`, and Phase 10 security ownership.
- **REQ-P11-CORE-005:** Production access, real credentials, customer data, and unsafe external side effects MUST be prohibited.
- **REQ-P11-CORE-006:** Evaluation data MUST be treated as untrusted data and MUST NOT alter runner policy or authorize capabilities.
- **REQ-P11-CORE-007:** Results MUST identify dataset version, runner implementation version, execution mode, and per-case evidence.
- **REQ-P11-CORE-008:** Unknown material evaluation decisions MUST remain explicit blockers or NOT_MEASURABLE outcomes rather than being guessed.
- **REQ-P11-CORE-009:** Runner Contract Mode and Local RAG Evaluation Mode MUST remain distinct evidence classes; contract-mode doubles MUST NOT support an official retrieval-quality claim.

### DATA

- **REQ-P11-DATA-001:** Both YAML suites MUST load deterministically and fail fast on malformed YAML or root structure.
- **REQ-P11-DATA-002:** Suite versions and case/scenario IDs MUST be present, unique, and reported.
- **REQ-P11-DATA-003:** Required fields, approved defaults, and field types MUST be validated before execution.
- **REQ-P11-DATA-004:** Unknown fields MUST be rejected or explicitly version-gated; they MUST NOT be silently ignored.
- **REQ-P11-DATA-005:** Dataset vocabulary MUST be mapped through an explicit versioned adapter to current runtime route, capability, security, and audit contracts.
- **REQ-P11-DATA-006:** Dataset acceptance criteria, expected sources/evidence, forbidden capabilities, and must-not constraints MUST be preserved as typed expectations.
- **REQ-P11-DATA-007:** Invalid or unsupported evaluation definitions MUST fail fast and MUST NOT become passing cases.
- **REQ-P11-DATA-008:** Dataset versions and runner versions MUST be independently represented in every suite result.
- **REQ-P11-DATA-009:** Legacy or conceptual dataset semantics MUST be reported through explicit mapping/version notes without weakening current Phase 9/10 contracts.
- **REQ-P11-DATA-010:** Expected-source values MUST use the versioned exact provenance-manifest adapter defined for dataset v1; fuzzy, substring, title, filename, UUID, and response-text matching are prohibited.
- **REQ-P11-DATA-011:** Before official dataset-v1 Local RAG Evaluation Mode, every unique applicable expected-source path MUST have exactly one reviewed Evaluation Source Manifest entry with complete, unambiguous stable runtime provenance identity; missing or ambiguous coverage MUST fail fast.

### RAG

- **REQ-P11-RAG-001:** The runner MUST execute all 25 current `rag-*` cases for the declared dataset version.
- **REQ-P11-RAG-002:** Ordinary evidence-backed, comparison, and security cases MUST use explicit case classes and applicable metrics.
- **REQ-P11-RAG-003:** Applicable retrieval cases MUST observe final Top-5 evidence, source identity, provenance, grounding state, and answer/result state through approved seams.
- **REQ-P11-RAG-004:** Expected-source matching MUST use stable repository/source identity semantics, not response wording alone.
- **REQ-P11-RAG-005:** Security cases MUST prove blocking and zero forbidden capability execution without invoking RAG merely to score retrieval.
- **REQ-P11-RAG-006:** Unsupported material facts MUST be measured deterministically from typed evidence; an LLM judge is not part of the baseline.
- **REQ-P11-RAG-007:** Every RAG case MUST produce a typed PASS, FAIL, NOT_APPLICABLE, or NOT_MEASURABLE result with evidence.
- **REQ-P11-RAG-008:** The current absence of an applicable insufficient-evidence case MUST remain visible as a coverage/version gap.
- **REQ-P11-RAG-009:** Official Top-5 and provenance metrics MUST use the real local FastEmbed, PostgreSQL FTS, pgvector, RRF, Top-5, RetrievedChunk, RetrievalProvenance, and ContextBuilder pipeline; local PostgreSQL is mandatory for those metrics.

The immutable v1.0 wording above remains historical contract evidence. The
reviewed v1.1 adapter executes all original 25 cases plus two versioned closure
cases (27 total), and resolves the RAG-008 gap without hiding the v1.0
`NOT_MEASURABLE` result.

### CHAL

- **REQ-P11-CHAL-001:** The runner MUST execute all 14 current `challenge-*` scenarios.
- **REQ-P11-CHAL-002:** Conceptual dataset routes MUST be evaluated through explicit mappings to approved runtime routes/states.
- **REQ-P11-CHAL-003:** Expected and forbidden capabilities MUST be checked through typed invocation observations.
- **REQ-P11-CHAL-004:** Routing, authorization, FACT/INFERENCE boundaries, RAG/Web behavior, OPS, security blocking, AUDIT, and cooperation MUST be observable.
- **REQ-P11-CHAL-005:** Challenge-013 MUST validate typed security blocking, sanitization, AUDIT behavior, and zero forbidden continuation.
- **REQ-P11-CHAL-006:** Challenge-014 MUST execute as a multi-turn conversation preserving handoff state and automation suspension.
- **REQ-P11-CHAL-007:** Human transfer MUST require explicit user confirmation and MUST NOT create an automatic AI ticket or external ITSM side effect.
- **REQ-P11-CHAL-008:** Scenario response evaluation MUST assess behavior and typed evidence, not exact response wording unless a dataset contract explicitly requires it.
- **REQ-P11-CHAL-009:** Challenge-014 MUST represent confirmation as WAITING_HUMAN and authorized SUPPORT_AGENT acceptance as HUMAN; only HUMAN may carry operator ownership and automation suspension.

### METRIC

- **REQ-P11-METRIC-001:** Every metric MUST declare its numerator, denominator, applicability rule, threshold, and outcome.
- **REQ-P11-METRIC-002:** Expected-source Top-5 success MUST mean at least one expected source is present in the final applicable Top-5, with a denominator of applicable retrieval cases.
- **REQ-P11-METRIC-003:** Provenance success MUST use typed source/provenance evidence and the applicable retrieval denominator.
- **REQ-P11-METRIC-004:** Unsupported fact rate MUST use deterministic evidence and have an acceptance threshold of 0.0 where applicable.
- **REQ-P11-METRIC-005:** Insufficient-evidence behavior MUST require no hallucinated answer, but an empty denominator MUST yield NOT_MEASURABLE rather than PASS.
- **REQ-P11-METRIC-006:** Applicable security cases MUST block, preserve zero forbidden calls, and produce the current Phase 10 typed AUDIT event set.
- **REQ-P11-METRIC-007:** Redaction success MUST prove supplied synthetic secret-shaped values are absent from evaluation-visible persisted content and reports.
- **REQ-P11-METRIC-008:** Aggregation MUST retain per-case outcomes and distinguish PASS, FAIL, NOT_APPLICABLE, and NOT_MEASURABLE.
- **REQ-P11-METRIC-009:** Reports MUST be provider-neutral and secret-safe, with no raw protected request, credential, token, SQL, traceback, or unsafe diagnostic.
- **REQ-P11-METRIC-010:** Unsupported-fact acceptance MUST remain 0.0, but the metric MUST be NOT_MEASURABLE until a deterministic claim-support contract exists; absence of measurement MUST never become PASS.

### VAL

- **REQ-P11-VAL-001:** Every Phase 11 requirement MUST map to reproducible evidence in the validation specification.
- **REQ-P11-VAL-002:** Dataset contract, mapping, and fail-fast behavior MUST have deterministic tests before runtime closure.
- **REQ-P11-VAL-003:** RAG and challenge runner behavior MUST have deterministic execution tests, including challenge-014 multi-turn coverage.
- **REQ-P11-VAL-004:** Security/AUDIT evaluation MUST preserve all applicable Phase 10 regressions and real opt-in evidence.
- **REQ-P11-VAL-005:** Normal validation MUST remain network-free and must not invoke DeepSeek, Tavily, or production services.
- **REQ-P11-VAL-006:** Phase 9 regression, Phase 10 regression, full normal pytest, compileall, pip check, imports, diff checks, and secret-safety review are closure gates.
- **REQ-P11-VAL-007:** Evaluation outputs and fixtures MUST undergo secret-safety review.
- **REQ-P11-VAL-008:** Phase 11 is complete only when all applicable requirements have evidence and no unresolved dataset/runtime conflict is silently accepted.
- **REQ-P11-VAL-009:** Every Python validation command MUST resolve and verify the approved project `.venv`; global or unrelated interpreters are not valid evidence.

## Dependency and implementation order

1. **11.1:** this SDD Foundation and corrective contract review (complete; documentation only).
2. **11.2:** dataset loaders, schema validators, versioned adapters, exact-manifest machinery, R2 curated publication, provenance validation, and fail-fast contract tests (complete; 6/6 retrieval-manifest coverage; security-only sources are excluded).
3. **11.3:** typed evaluation boundary and RAG runner (implemented; v1.0
   processed 25 cases and closure-remediation v1.1 processes all 27 cases).
4. **11.4:** challenge runner, including multi-turn challenge-014 state (complete;
   deterministic authenticated execution of all 14 scenarios).
5. **11.5:** metrics, aggregation, safe reporting, and deterministic execution controls (complete; v1.1 report PASS).
6. **11.6:** validation, regression, explicit opt-in integration evidence, and closure (revalidation complete; Phase 11 closure CLOSED).

No numbered step authorizes runtime implementation without a reviewed task.
The Phase 11.6 revalidation resolved all five recorded closure blockers through
measured evidence; none was waived. Phase 12 remains outside this task.

## Traceability matrix

| Family | Primary specification/evidence |
|---|---|
| CORE-001..009 | This document; boundary, authority, execution-mode, and deterministic contract tests |
| DATA-001..011 | `01-evaluation-dataset-contracts-spec.md` and loader/manifest/mapping tests |
| RAG-001..009 | `02-rag-evaluation-runner-spec.md` and local-pipeline/per-case tests |
| CHAL-001..009 | `03-challenge-evaluation-runner-spec.md` and scenario/state tests |
| METRIC-001..010 | `04-metrics-reporting-spec.md` and formula/applicability tests |
| VAL-001..009 | `05-validation-spec.md` and Phase 9/10/regression/environment evidence |

## Definition of done

Phase 11 is complete only when the versioned datasets load and execute through
approved boundaries, official RAG quality metrics use the real local RAG
pipeline, all applicable per-case and aggregate metrics are traceable,
unsupported-fact measurement is either deterministically implemented or
explicitly resolved, security/AUDIT behavior remains current, reports are
reproducible and secret-safe, validation uses the approved project `.venv`,
and all dataset/runtime discrepancies are explicitly mapped or resolved by
reviewed dataset/version change.
