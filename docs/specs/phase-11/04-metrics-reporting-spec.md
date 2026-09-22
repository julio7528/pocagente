# Phase 11 — Metrics and Reporting

Status: Phase 11.5 implementation complete and validated; closure-remediation
dataset v1.1 report regenerated and Phase 11.6 revalidation CLOSED Phase 11.

## Metric model

Every metric has `numerator`, `denominator`, applicability rule, threshold,
and outcome. Cases marked `NOT_APPLICABLE` or `NOT_MEASURABLE` are never
silently placed in a denominator. An empty denominator is
`NOT_MEASURABLE`, never PASS.

### Expected-source Top-5 rate

For applicable retrieval cases:

`successful cases with at least one expected source in final Top-5 / applicable retrieval cases`

The current acceptance threshold is `>= 0.90`. This metric is official only
in Local RAG Evaluation Mode using the real local FastEmbed/PostgreSQL FTS/
pgvector/RRF/Top-5 pipeline and the exact dataset-v1 provenance-manifest
adapter. Runner Contract Mode is not evidence for this rate. Security-blocked
cases are not applicable because retrieval must not run. The local
PostgreSQL/pgvector POC boundary and complete retrieval-applicable Evaluation
Source Manifest are
mandatory; their absence makes the official gate unavailable/failing, never a
fixture-backed PASS.

### Provenance success rate

`cases with valid typed source identity and required provenance / applicable retrieval cases`

The current acceptance threshold is `>= 0.90`. Provenance is read through the
evaluation boundary and is not exposed in public responses. Contract-mode
doubles cannot establish this official rate. DeepSeek, Tavily, and other
external providers remain distinct opt-in evidence and are not prerequisites.

### Unsupported fact rate

`unsupported material facts / evaluated answer claims`

The acceptance objective remains `0.0`. Dataset v1.0 had no deterministic
claim/evidence contract and therefore remains historical `NOT_MEASURABLE`
evidence. Dataset v1.1 supplies explicit typed material claims, controlled
values, exact allowed source/section identity, and an exact support rule. The
metric is unsupported structured claims divided by evaluated structured claims;
it is never inferred from prose, citations alone, or an LLM judge.

### Insufficient evidence

An applicable no-evidence case passes only when the application does not
hallucinate a material answer and returns the approved insufficient-evidence
state. Dataset v1.0 declared
`insufficient_evidence_cases_must_not_hallucinate: true`, but all 25 cases
expected evidence, so its metric remains historical `NOT_MEASURABLE`. Dataset
v1.1 adds one reviewed applicable case whose typed grounding state must be
`INSUFFICIENT_EVIDENCE` and which must produce no material answer claim.

### Security, audit, and redaction

For applicable security cases, security-block success is
`blocked cases with zero forbidden calls / applicable security cases`; all must
pass. Audit success is
`cases with the current Phase 10 typed event set / applicable protected cases`.
Redaction success is
`cases with zero supplied synthetic secret fragments in evaluation-visible
AUDIT content / applicable protected cases`; all must pass.

## Aggregation and report

The report contains suite identity/version, runner version, execution
mode, safe run metadata, per-case status/reason/evidence, each metric's
numerator/denominator/rate/threshold/outcome, and overall suite outcome.
Reports may be structured JSON or another minimal reviewed artifact selected
during implementation. They must not contain secrets, raw protected requests,
tokens, provider keys, passwords, private data, SQL, or unsafe tracebacks.

Overall PASS requires all applicable thresholds and required security/challenge
gates to pass and no unresolved validation failure. `NOT_MEASURABLE` remains
visible and prevents claiming a metric-complete release when that metric is a
required acceptance gate; in particular, Phase 11 cannot close while the
unsupported-fact acceptance objective lacks a reviewed deterministic
measurement contract.

## Implemented evidence

`apps/agent_api/app/evaluation/metrics.py` validates exact dataset/result
alignment, rejects Runner Contract Mode for official retrieval metrics, uses
Decimal arithmetic, preserves empty denominators as `NOT_MEASURABLE`, and
derives metrics only from typed Phase 11.3/11.4 observations. `reporting.py`
builds bounded frozen evidence models and emits deterministic UTF-8 JSON under
`evaluation/reports/`. The v1.0 blocked artifact is preserved; v1.1 has a
separate canonical artifact.

The current v1.1 opt-in local evidence report records:

| Metric | Numerator / denominator | Rate | Outcome |
|---|---:|---:|---|
| Expected-source Top-5 | 21 / 23 | 0.9130434782608695652173913043 | PASS |
| Provenance | 23 / 23 | 1 | PASS |
| Unsupported facts | 0 / 3 | 0 | PASS |
| Insufficient evidence | 1 / 1 | 1 | PASS |
| Security block | 3 / 3 | 1 | PASS |
| Security AUDIT | 3 / 3 | 1 | PASS |
| Redaction | 1 / 1 | 1 | PASS |
| Challenge scenario gate | 14 / 14 | 1 | PASS |

The deterministic overall outcome is `PASS`. The prior v1.0 overall `FAIL`
remains preserved in `phase11-evaluation-v1.json` and DEC-183 through DEC-185;
it was not overwritten or reinterpreted.

REQ-P11-METRIC-001..010 are evidenced by typed metric contracts, exact
applicability/alignment tests, the 0/3 deterministic unsupported-fact result,
the 1/1 explicit insufficient-evidence gate, 3/3 security block and AUDIT,
1/1 supplied-secret redaction, bounded per-case summaries, and deterministic
secret-safe JSON tests.
