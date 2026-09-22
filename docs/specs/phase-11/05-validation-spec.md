# Phase 11 — Validation

Status: Phase 11.3 typed RAG evaluation-boundary validation, Phase 11.4
deterministic Challenge Evaluation Runner, and Phase 11.5 metrics/reporting
are implemented. Evaluation Source Manifest coverage is 6/6
retrieval-applicable. Phase 11.6 closure revalidation is complete; all five
recorded blockers have measured resolutions and Phase 11 closure is CLOSED.

## Requirements and evidence

Every `REQ-P11-*` ID must map to reproducible evidence. The expected traceability
families are:

| Family | Count | Primary evidence |
|---|---:|---|
| CORE-001..009 | 9 | architecture, authority, execution modes, safety, deterministic-mode tests |
| DATA-001..011 | 11 | YAML loader, schema, version, complete source manifest, exact provenance mapping, fail-fast tests |
| RAG-001..009 | 9 | versioned 25/27-case execution, local pipeline, typed observations, security exclusion tests |
| CHAL-001..009 | 9 | 14-scenario execution and exact challenge-014 state tests |
| METRIC-001..010 | 10 | formula, denominator, applicability, measurability, aggregation, report tests |
| VAL-001..009 | 9 | traceability, regression, environment, static, secret-safety, closure evidence |

Total planned requirements: **57**. This is a derived contract count, not an
acceptance shortcut.

## Validation levels

- dataset contract and version/mapping tests;
- metric calculation and denominator unit tests;
- deterministic RAG runner tests for every case in each supported dataset version;
- deterministic challenge runner tests for all 14 scenarios;
- challenge-014 multi-turn state tests;
- security/AUDIT/redaction evaluation tests;
- deterministic normal execution with no network;
- Runner Contract Mode tests using typed doubles, explicitly excluded from official retrieval-quality evidence;
- Local RAG Evaluation Mode using mandatory approved project PostgreSQL/pgvector, the approved local corpus, and the real local retrieval pipeline for official Top-5/provenance evidence;
- explicit opt-in External Provider Validation for DeepSeek, Tavily, and other external HTTP dependencies only;
- existing Phase 9 and Phase 10 regression suites;
- full normal `python -m pytest`;
- `python -m compileall apps tests`;
- `python -m pip check`;
- core imports, `git diff --check`, and secret-safety review.

Aggregate pytest counts are not sufficient. Each applicable requirement needs
direct or clearly shared evidence, and live DeepSeek/Tavily or production
calls are forbidden in normal validation. Every Python command must resolve
and verify the approved project `.venv`; global Python is invalid evidence.

The historical v1.0 dataset had no deterministic typed claim-support contract,
so its unsupported-fact result remains `NOT_MEASURABLE`. Reviewed dataset v1.1
provides an explicit structural claim-support contract and authoritative
insufficient-evidence and supplied-secret cases; closure uses fresh v1.1
evidence rather than reinterpreting the historical result.

### Phase 11.2 evidence

`tests/test_evaluation_contracts.py` covers strict v1 YAML loading, duplicate
and unknown-field rejection, malformed turns, conceptual route/security
adapters, field-driven scenario-ID independence, semantic contradiction
rejection, challenge-014 state semantics, source-path normalization, exact
provenance matching, manifest version/ambiguity/missing coverage, and the
official Local RAG availability gate. It passes with the manifest intentionally
complete. Existing publication and real local PostgreSQL evidence maps all 3
R1 and all 3 R2 retrieval paths; the security-policy path is excluded from
retrieval-manifest coverage as a security-only source. REQ-P11-DATA-001..011
have implementation and validation evidence.

Before official Local RAG Evaluation Mode, Phase 11.2 must validate the complete
versioned Evaluation Source Manifest. Current dataset v1 has 7 unique declared
expected source paths, of which 6 are retrieval-applicable; repository evidence
establishes 3 R1 plus 3 R2 mappings. Official retrieval quality may proceed
from the contract layer with coverage 6/6 (100%) and exact unambiguous runtime
provenance identities.

## Phase 11.3 evidence

`tests/test_rag_evaluation_runner.py` covers immutable typed results, exact
source matching, grounding observations, Top-5 violations, empty retrieval,
security terminal behavior, redaction, forbidden-call observations, and the
versioned 25/27-case dataset iteration. The opt-in
`tests/integration/test_rag_evaluation_runner_real.py` uses the approved local
PostgreSQL/pgvector database, FastEmbed, the existing HybridRetriever, and
ContextBuilder; it processed all 25 cases without LLM/provider generation.
The observed local run produced 19 PASS, 5 FAIL, and 1 NOT_MEASURABLE. Two security cases were
not sent to retrieval; their Router results were retained as authentic FAIL
observations because no second classifier is permitted. This is boundary
evidence, not an aggregate metric or a claim that the current security
vocabulary coverage is complete.

The corrected observation contract now measures forbidden calls through the
existing LangGraph security terminal and evaluation-only invocation spies,
retains exact `document_key` plus `source_reference`, records separate
retrieval/provenance/grounding/semantic statuses, and distinguishes supplied
secret redaction from `NOT_APPLICABLE`. The corrected local run derived 22
`RETRIEVAL`, 1 `RULE_VS_OBSERVED`, and 2 `SECURITY` cases, invoked retrieval 23
times, and produced 19 `PASS`, 5 `FAIL`, and 1 `NOT_MEASURABLE`. The two
Portuguese security cases remain authentic Router classification findings.

The final observation-integrity correction validates per-case invocation
deltas, cumulative-observer isolation, and direct `SanitizedSecurityEvent`
action observation, including the no-event/no-action invariant.

Closure-remediation v1.1 adds exact structured claim support, an explicit
insufficient-evidence case, and an authoritative synthetic supplied-secret
security case. The fresh real run processed 27 cases (22 `RETRIEVAL`, 1
`RULE_VS_OBSERVED`, 3 `SECURITY`, 1 `INSUFFICIENT_EVIDENCE`) and invoked the
retrieval boundary 24 times. It produced 24 `PASS`, 2 authentic retrieval
`FAIL` observations, and 1 rule-inference `NOT_MEASURABLE`; all required
aggregate gates pass.

## Phase 11.4 evidence

`tests/test_challenge_evaluation_runner.py` and
`tests/e2e/test_phase11_challenge_evaluation_e2e.py` load the authoritative
v1 Challenge suite and execute all 14 scenarios in declared order through the
deterministic authenticated `/chat` composition. The composition preserves the
production Router, LangGraph, Customer Support, OperationalTools, Human
Escalation, SecurityAuditService, request/auth translation, and safe response
boundary. It replaces only live/persistent seams with typed deterministic
knowledge, Web, OPS repository, interpretation-provider, and audit-sink
doubles.

The evidence observes per-scenario/turn invocation deltas, mapped routes,
required and forbidden capabilities, controlled OPS authorization, FACT versus
INFERENCE structure, direct security audit events, public-response safety, and
both conditional persistent-RAG/Web branches. Challenge-014 retains one
conversation and proves `WAITING_CONFIRMATION -> WAITING_HUMAN -> HUMAN`,
automation suspension, different-operator rejection, assigned-operator
resolution, and minimum handoff context. No DeepSeek, Tavily, external HTTP,
database, or automatic ticket/ITSM action is part of deterministic execution.
Per-scenario status is evidence only; aggregate rates, thresholds, and report
generation remain Phase 11.5 work.

The final Phase 11.4 observation-integrity correction proves fallback ordering
from actual invocation sequence, derives authorization from both authorized and
denied journeys, gates PASS on expected tools and applicable FACT/INFERENCE
structure, requires direct typed AUDIT evidence for security, and maps every
declared forbidden capability to measured or explicit architectural evidence.

The DEC-181 implementation reconciliation adds regressions proving that a
premature-Web or Knowledge-skipping primary conditional branch fails despite a
valid fallback branch, and that a non-BLOCK typed audit action fails the
security gate even if a derived protective-action flag is incorrectly set.

## Phase 11.5 evidence

`tests/test_evaluation_metrics_reporting.py` covers alignment rejection,
LOCAL_RAG-only official retrieval evidence, exact Decimal boundary arithmetic,
security/audit/redaction applicability, empty denominators, overall-outcome
precedence, deterministic serialization, and report secret safety.
The historical opt-in `tests/integration/test_phase11_metrics_reporting_real.py` executed
the existing local FastEmbed/PostgreSQL/pgvector RAG boundary and deterministic
Challenge runner, producing the canonical JSON report. It observed 20/23
expected-source successes, 23/23 provenance successes, 0/2 security block and
audit successes, 14/14 Challenge successes, and `FAIL` overall. Unsupported
facts, insufficient evidence, and supplied-secret redaction were
`NOT_MEASURABLE` under the historical v1.0 dataset/runtime contract.

The closure-remediation integration
`tests/integration/test_phase11_closure_remediation_real.py` executes v1.1 and
records Top-5 21/23 PASS, provenance 23/23 PASS, unsupported facts 0/3 PASS,
insufficient evidence 1/1 PASS, security block 3/3 PASS, security AUDIT 3/3
PASS, redaction 1/1 PASS, Challenge 14/14 PASS, and overall PASS.
REQ-P11-METRIC-001..010 therefore have direct aggregation, applicability,
serialization, and fresh real-evidence traceability.

## Closure gates

Phase 11 may close only when both datasets validate, all applicable cases have
typed results, official retrieval metrics use the real local pipeline, metrics
have explicit denominators, unsupported-fact measurement has a deterministic
reviewed contract, current dataset gaps are resolved by reviewed versioning or
visibly NOT_MEASURABLE with owner-approved disposition, reports are
secret-safe, Phase 9/10 behavior remains intact, and all static/regression
gates pass. No runtime implementation is authorized by this SDD alone.

## Phase 11.6 final traceability matrix

The following matrix revalidates all 57 immutable requirements individually
against dataset v1.1, the current code, and fresh official evidence. Historical
v1.0 failures remain in DEC-185 and the preserved v1 report; they are not
rewritten or treated as the current result.

| Requirement | Status | Implementation evidence | Test/runtime evidence | Closure note |
|---|---|---|---|---|
| REQ-P11-CORE-001 | SATISFIED | Evaluation adapters consume runtime seams | Phase 11.3/11.4 composition tests | No production reimplementation |
| REQ-P11-CORE-002 | SATISFIED | Dataset runners are separate from regression tests | 25-case and 14-scenario ordered runs | Counts are not acceptance alone |
| REQ-P11-CORE-003 | SATISFIED | Deterministic modes forbid external providers | Full normal suite; no provider calls | External validation remains opt-in |
| REQ-P11-CORE-004 | SATISFIED | Router/LangGraph/agents/tools/security are consumed | Phase 9/10 and authenticated evaluation evidence | Ownership preserved |
| REQ-P11-CORE-005 | SATISFIED | Production/credential/customer-data guards | Secret scan and local-only integration | No production access |
| REQ-P11-CORE-006 | SATISFIED | YAML is parsed as typed untrusted data | Unknown-field and policy-independence tests | Dataset cannot authorize capabilities |
| REQ-P11-CORE-007 | SATISFIED | Version/mode fields in typed results/report | Result and report serialization tests | Evidence is versioned |
| REQ-P11-CORE-008 | SATISFIED | Explicit FAIL/NOT_MEASURABLE outcomes | Metric and runner tests | No unresolved decision was guessed |
| REQ-P11-CORE-009 | SATISFIED | Contract and LOCAL_RAG modes are distinct | LOCAL_RAG precondition/alignment tests | Doubles cannot support official quality claims |
| REQ-P11-DATA-001 | SATISFIED | Safe strict YAML loaders | `tests/test_evaluation_contracts.py` | Malformed/root failures covered |
| REQ-P11-DATA-002 | SATISFIED | Version and unique-ID validators | Dataset contract tests | v1.1 27 RAG and v1.0 14 Challenge IDs validated |
| REQ-P11-DATA-003 | SATISFIED | Typed required fields/defaults | Strict schema tests | Invalid types fail fast |
| REQ-P11-DATA-004 | SATISFIED | Forbid unknown fields | Unknown-field negative tests | No silent discard |
| REQ-P11-DATA-005 | SATISFIED | Versioned semantic/security adapters | Adapter and contradiction tests | Current runtime vocabulary preserved |
| REQ-P11-DATA-006 | SATISFIED | Typed acceptance/source/forbidden fields | Loader and adapter tests | Constraints retained as data |
| REQ-P11-DATA-007 | SATISFIED | Controlled contract errors | Negative mutation tests | Invalid definitions cannot pass |
| REQ-P11-DATA-008 | SATISFIED | Independent suite/runner versions | RAG/Challenge result models | Versions retained in evidence |
| REQ-P11-DATA-009 | SATISFIED | Legacy/current mapping notes and adapters | Security and route adapter tests | Phase 9/10 contracts unchanged |
| REQ-P11-DATA-010 | SATISFIED | Exact versioned provenance manifest adapter | Path/matching tests | No fuzzy/title/UUID matching |
| REQ-P11-DATA-011 | SATISFIED | Complete 6/6 retrieval manifest | Manifest coverage and LOCAL_RAG gate | 7 declared, 6 retrieval-applicable |
| REQ-P11-RAG-001 | SATISFIED | RAG runner iterates loaded versioned suite | Fresh LOCAL_RAG: 27/27 v1.1 cases | Dataset order preserved |
| REQ-P11-RAG-002 | SATISFIED | Explicit RAG case classes | Derived 22/1/3/1 classification | Security excluded; no-evidence explicit |
| REQ-P11-RAG-003 | SATISFIED | Typed Top-5/provenance/grounding observations | 24 real retrieval executions; 23 quality cases | Structural evidence retained |
| REQ-P11-RAG-004 | SATISFIED | Exact manifest identity matching | Source-match tests and fresh run | Misses remain authentic |
| REQ-P11-RAG-005 | SATISFIED | Production security terminal and measured invocation observer | Three v1.1 security cases block/audit; zero forbidden calls | Portuguese coverage verified |
| REQ-P11-RAG-006 | SATISFIED | Versioned exact structured claim-support evaluator | 3/3 typed claims evaluated; unsupported 0 | No prose/LLM judgment |
| REQ-P11-RAG-007 | SATISFIED | Frozen typed case results | 27 results with controlled statuses | Evidence status is explicit |
| REQ-P11-RAG-008 | SATISFIED | Reviewed explicit insufficient-evidence class | v1.1 applicable case 1/1 PASS | Historical v1 gap preserved |
| REQ-P11-RAG-009 | SATISFIED | LOCAL_RAG uses FastEmbed/PG/pgvector/RRF/ContextBuilder | Opt-in real run; 24 retrieval calls | Official boundary verified |
| REQ-P11-CHAL-001 | SATISFIED | Challenge runner iterates loaded suite | 14/14 ordered scenarios | No hardcoded execution list |
| REQ-P11-CHAL-002 | SATISFIED | Adapter-driven route/state mapping | Challenge adapter tests/E2E | Dataset strings are not runtime enums |
| REQ-P11-CHAL-003 | SATISFIED | Invocation/capability observers | Challenge runner tests | Required/forbidden calls measured |
| REQ-P11-CHAL-004 | SATISFIED | Typed auth/FACT-INFERENCE/Web/OPS/security observations | 14 deterministic authenticated results | Cooperation evidence retained |
| REQ-P11-CHAL-005 | SATISFIED | Direct typed security/AUDIT observation | Challenge-013 PASS with zero continuation | No second classifier |
| REQ-P11-CHAL-006 | SATISFIED | One-conversation multi-turn runner | Challenge-014 state tests | Suspension and ownership retained |
| REQ-P11-CHAL-007 | SATISFIED | Confirmation/operator gate; no ITSM boundary | Challenge-014 operator tests | No automatic ticket side effect |
| REQ-P11-CHAL-008 | SATISFIED | Structural typed evidence, no prose judge | Challenge tests | No exact-answer grading |
| REQ-P11-CHAL-009 | SATISFIED | WAITING_HUMAN/HUMAN typed state contract | Full challenge-014 sequence | Only HUMAN owns/suspends |
| REQ-P11-METRIC-001 | SATISFIED | Frozen MetricResult numerator/denominator/outcome | Metrics unit tests | Applicability is explicit |
| REQ-P11-METRIC-002 | SATISFIED | Exact Top-5 aggregation and 0.90 threshold | Fresh v1.1: 21/23, 0.913043..., PASS | `rag-021`/`rag-023` remain visible misses |
| REQ-P11-METRIC-003 | SATISFIED | Independent typed provenance aggregation | Fresh result: 23/23, PASS | Not coupled to source relevance |
| REQ-P11-METRIC-004 | SATISFIED | Deterministic structured claim metric | Fresh result: 0/3, rate 0, PASS | Exact source/section support |
| REQ-P11-METRIC-005 | SATISFIED | Explicit no-evidence applicability and gate | Fresh result: 1/1 PASS | No empty denominator |
| REQ-P11-METRIC-006 | SATISFIED | Typed security metric aggregation | Fresh result: block 3/3, audit 3/3 | All protected cases terminal |
| REQ-P11-METRIC-007 | SATISFIED | Supplied-secret applicability is typed | Fresh result: redaction 1/1 PASS | Synthetic fragment absent from report |
| REQ-P11-METRIC-008 | SATISFIED | Per-case status and summaries retained | Report serialization tests | No weighted aggregate score |
| REQ-P11-METRIC-009 | SATISFIED | Bounded report model and JSON writer | Secret scan/round-trip tests | No raw protected material |
| REQ-P11-METRIC-010 | SATISFIED | 0.0 objective and exact typed support contract | Unsupported-fact rate 0/3 = 0 PASS | Empty/unavailable measurement still cannot pass |
| REQ-P11-VAL-001 | SATISFIED | This complete per-ID matrix | 57 rows audited | Reproducible evidence links recorded |
| REQ-P11-VAL-002 | SATISFIED | Contract/adapter fail-fast tests | Phase 11.2 dedicated suite | Pre-runtime validation covered |
| REQ-P11-VAL-003 | SATISFIED | RAG/Challenge deterministic runners | Dedicated tests and real ordered runs | Challenge-014 included |
| REQ-P11-VAL-004 | SATISFIED | Security/AUDIT regression selection | Phase 10 plus opt-in LOCAL_RAG evidence | Failures retained, not waived |
| REQ-P11-VAL-005 | SATISFIED | Normal suite has no external providers | Full normal pytest; provider tests skipped | No production service |
| REQ-P11-VAL-006 | SATISFIED | Closure command set executed | Regression/static evidence below | All requested gates recorded |
| REQ-P11-VAL-007 | SATISFIED | Artifact/fixture secret review | Report scan and unit tests | No secret material found |
| REQ-P11-VAL-008 | SATISFIED | Closure decision is explicit | All five blockers resolved by fresh measured evidence | Phase 11 closes without waiver |
| REQ-P11-VAL-009 | SATISFIED | Approved venv resolved and verified | `sys.executable` is project `.venv` | Global Python not used |

## Phase 11.6 closure blocker register

| Blocker | Related requirements | Category | Revalidation evidence | Disposition |
|---|---|---|---|---|
| P11-CLOSE-001 | REQ-P11-METRIC-002 | RETRIEVAL_QUALITY | Fresh v1.1 Top-5 is 21/23 (0.913043...), with only `rag-021` and `rag-023` retained as misses | RESOLVED |
| P11-CLOSE-002 | REQ-P11-RAG-005, REQ-P11-METRIC-006 | SECURITY_ROUTING | All 3 v1.1 security cases route `SECURITY_BLOCK`, emit typed BLOCK AUDIT evidence, and have zero forbidden continuation | RESOLVED |
| P11-CLOSE-003 | REQ-P11-RAG-006, REQ-P11-METRIC-004, REQ-P11-METRIC-010 | MEASUREMENT_CONTRACT | Versioned exact source/section claim contract evaluates 3 claims; unsupported rate 0/3 | RESOLVED |
| P11-CLOSE-004 | REQ-P11-RAG-008, REQ-P11-METRIC-005 | DATASET_COVERAGE | Reviewed v1.1 explicit insufficient-evidence case passes 1/1 | RESOLVED |
| P11-CLOSE-005 | REQ-P11-METRIC-007 | DATASET_COVERAGE | Reviewed v1.1 synthetic supplied-secret case redacts and passes 1/1; fragment absent from report | RESOLVED |

No blocker was waived. The remediation changed the existing semantic owners and
introduced one coherent reviewed dataset version; it did not lower thresholds,
remove cases, edit source expectations, tune RRF/Top-K, or use evaluator-only
case-ID overrides.

## Phase 11.6 audit result

The fresh approved `.venv` evidence processed 27 v1.1 RAG cases (22
`RETRIEVAL`, 1 `RULE_VS_OBSERVED`, 3 `SECURITY`, 1
`INSUFFICIENT_EVIDENCE`), 24 retrieval executions, and Challenge 14/14 PASS.
Top-5 is 21/23 PASS; provenance 23/23 PASS; unsupported facts 0/3 PASS;
insufficient evidence 1/1 PASS; security block 3/3 PASS; security AUDIT 3/3
PASS; redaction 1/1 PASS; overall `PASS`. The canonical v1.1 JSON report was
regenerated from fresh results and checked for deterministic reproducibility,
JSON validity, and secret safety. All 57 requirements are SATISFIED and Phase
11 closure is therefore **CLOSED**.

Closure command evidence used the verified project `.venv` interpreter:
dataset contracts 44 passed; RAG runner 25 passed; Challenge runner 15 passed;
metrics/reporting 11 passed; Phase 11 Challenge E2E 1 passed; selected Phase
9/10/runtime regressions 223 passed; selected real PostgreSQL regressions 8
passed; official v1.0/v1.1 Phase 11 integrations 3 passed; and the full normal
suite 539 passed, 35 skipped opt-in tests, 0 failed, with 2 known warnings.
`compileall apps tests`, `pip check`, core imports, `git diff --check`, JSON
round-trip, secret scan, requirement-ID audit, and production-to-evaluation
dependency scan all passed. Two consecutive fresh v1.1 report generations had
identical bytes.
