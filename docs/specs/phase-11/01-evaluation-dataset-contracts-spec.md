# Phase 11 — Evaluation Dataset Contracts

Status: Phase 11.2 loaders, immutable contracts, semantic adapters, path
normalization, manifest validator, and complete R2 provenance mapping
implemented and validated. Dataset v1.0 and v1.1 retrieval manifest coverage
is 6/6.

## Scope

This contract defines deterministic loading and interpretation of
`evaluation/rag/dataset-v1.yaml`, the reviewed closure-remediation
`evaluation/rag/dataset-v1.1.yaml`, and
`evaluation/challenge/scenarios-v1.yaml`. Dataset definitions are untrusted
data, never executable policy or an authorization grant. The v1.0 artifact is
preserved as historical evidence; v1.1 is the current RAG evaluation input.

## Common suite contract

Each suite requires a scalar `version` and a sequence of unique case/scenario
objects. IDs are immutable within a version and must not be reused for a
different meaning. The loader records source path, suite kind, dataset version,
case count, and runner implementation version.

Malformed YAML, duplicate IDs, missing IDs, wrong root types, missing required
fields, invalid field types, unsupported enum values, and invalid nested
multi-turn structure fail before any case executes. Unknown fields are rejected
unless a future suite version explicitly declares them; no unknown field may be
silently discarded. Defaults are explicit in the versioned schema, never
inferred from message text.

Common typed expectations include expected behavior, evidence requirement,
expected sources, expected route/capabilities, forbidden capabilities,
security expectations, must-not constraints, preconditions, and tool
expectations. Strings are retained as data and cannot alter runner policy.

## RAG datasets v1.0 and v1.1

The historical v1 file is version `1.0` with 25 `rag-*` cases. The current
reviewed file is version `1.1` with 27 cases. The loader validates question,
category, expected sources, evidence expectation, expected behavior, optional
typed material-claim expectations, optional supplied-secret fixtures, and
must-not fields. Case classes are derived only from
declared, versioned fields or an explicit adapter—not from keyword guessing.

The current suite includes ordinary evidence-backed cases, a comparison case,
and security cases such as `rag-019` and `rag-025`. Case classification is
strictly declared by `expected_behavior`: `answer` is `RETRIEVAL`,
`compare_rule_to_observed_state` is `RULE_VS_OBSERVED`, and
`security_violation_alert` is `SECURITY`. Security cases terminate before RAG;
their expected sources remain dataset data but are excluded from the retrieval
manifest and Top-5/provenance denominators. A no-evidence class must be
declared by a reviewed version and must not be silently synthesized by the
runner. Dataset v1.1 does so through `insufficient_evidence`, adds an
authoritative synthetic supplied-secret security case, and introduces the
`explicit_claim_expectations_only` claim-support applicability contract.

The v1.1 claim contract is structural. Each material claim declares a stable
claim ID, controlled expected value, allowed source path, exact section, and
`EXACT_SOURCE_AND_SECTION` support rule. The runner compares these typed fields
with typed retrieval provenance and section metadata; it does not parse answer
prose, invoke an LLM judge, or treat a citation/source hit alone as claim
support. Cases without declared claim expectations are explicitly outside the
unsupported-fact denominator.

## Challenge dataset v1

The current file is version `1.0` with 14 scenarios. The loader validates
message/category, conceptual expected route, expected/forbidden capabilities,
expected behavior, must-not constraints, and tool expectations. Scenario 014
must contain and preserve its two-turn structure, explicit confirmation, and
human-ownership suspension requirements.

## Semantic adapters and current authority

Dataset concepts are mapped to current runtime contracts in a versioned,
auditable adapter:

| Dataset concept | Current evaluation interpretation |
|---|---|
| `knowledge` | approved Knowledge route/state and its typed evidence |
| `conditional_support` | current conditional support orchestration behavior |
| `support_with_knowledge` | current cooperative/support-with-knowledge behavior |
| `customer_support` | current Customer Support route/state |
| `cooperative_knowledge_and_support` | current multi-agent cooperative state |
| `security_block` | Router `SECURITY_BLOCK` and Phase 10 safe terminal outcome |
| `customer_support_to_human_escalation` | two-turn support offer then confirmed human transfer |

The adapter never changes runtime enums merely to match YAML strings. Likewise,
historical dataset security labels are translated to current Phase 10 typed
semantics. `rag-019` may describe `CREDENTIAL_REQUEST` and legacy action
wording; evaluation checks the current approved `CREDENTIAL_REQUEST` plus its
current resource category/action/result/review contract. `rag-025`'s conceptual
`SENSITIVE_ACCESS_REQUEST` maps to one or more current approved semantics,
such as `DATABASE_ACCESS_REQUEST`, `SECRET_REQUEST`, or
`SENSITIVE_INFRASTRUCTURE_REQUEST`, according to the Router result. The runner
must not require a legacy literal and must not weaken Phase 10 to satisfy it.

Any mapping not defined for the declared dataset version is a validation
failure, not an automatic pass.

### Field-driven challenge adaptation

Challenge expectations are derived from declared typed fields, never from the
scenario identifier or message text. A `knowledge` route with required
freshness, `web_search` and `freshness_check` capabilities, public Web Search,
and `rag_requirement: not_required` maps to the required Web fallback route.
A `knowledge` route declaring public RAG plus
`web_search_if_rag_insufficient` maps to the conditional fallback policy.
Ordinary public RAG, Customer Support, cooperation, and security-block cases
map from their declared route/capability/tool/security combinations. Security
maps to the non-empty runtime `SECURITY_GUARDRAIL` capability. Contradictory
combinations fail central validation before manifest validation.

The human-handoff adapter preserves two client turns and maps them to
`WAITING_CONFIRMATION` then `WAITING_HUMAN`; a separate authorized operator
acceptance continuation maps to `HUMAN` and automation suspension. Scenario IDs
remain traceability data only.

## Versioned Evaluation Source Manifest

Repository inspection shows that dataset `expected_sources[]` values are
repository-relative file paths such as
`knowledge/internal/cancellation-process/robot_01_r1/pdd-cancelamento.md`.
They do not equal the runtime `RetrievalProvenance.source_reference` alone
(the registered source directory), nor `document_key` alone (the published
document key), and UUID fields are environment-generated.

Phase 11.2 MUST create a versioned Evaluation Source Manifest for each
supported RAG dataset version.
It belongs only to the evaluation adapter boundary: runtime publication
artifacts such as `CURATED_DOCUMENTS`, source registries, ingestion metadata,
or persisted records are authoritative inputs, but are not automatically the
complete evaluation manifest. The manifest format may be a narrow immutable
Python mapping, YAML/JSON artifact, or another reviewed typed representation.
Each entry contains only the normalized `dataset_path`, exact runtime
`document_key`, and exact runtime `source_reference`, plus `origin` or
`source_type` only when repository evidence proves they are required to
disambiguate the current provenance identity.

Dataset v1 currently has 7 unique declared expected-source paths, of which 6
are retrieval-applicable. Existing publication
configuration, the real R1 corpus, and the validated R2 publication establish
identities for all 6 retrieval paths. The security-policy path is security-only
and is not required for the retrieval manifest.

The implemented v1.0 and v1.1 manifests contain exactly the same 3 R1 and 3 R2
proven mappings. Dataset v1.1 adds no retrieval source path. Their strict
extras policy rejects entries not required by the declared retrieval-applicable
paths, and each coverage validator passes the 6/6 set. Security-only and
explicitly insufficient-evidence cases remain excluded from retrieval coverage.

The adapter uses the following exact rule:

1. Normalize the dataset value as a POSIX repository-relative path: replace
   backslashes with `/`, remove `.` segments, reject absolute paths, `..`
   traversal, empty values, and query/fragment syntax.
2. Look up that exact normalized path in the versioned Evaluation Source
   Manifest. The manifest entry must be derived from reviewed publication,
   ingestion, source-registration, persisted-provenance, or equivalent
   authoritative repository evidence.
3. A retrieved item matches only when its typed provenance has the manifest's
   exact `document_key` and exact registered source reference for that path.

This is an exact manifest lookup, not fuzzy matching, substring matching,
title/filename/basename guessing, UUID matching, response-text matching, or an
LLM decision. A missing or ambiguous manifest entry is a dataset-contract
failure. The manifest adapter is versioned with the dataset and must be
reported in results. The dataset YAML is not changed by this SDD.

### Phase 11.2 manifest-coverage gate

Before any official Local RAG Evaluation Mode run, both YAML suites, IDs, and
version adapters must validate; every required expected-source path must have
exactly one reviewed manifest entry; and every entry must resolve to stable
typed runtime provenance semantics. Datasets v1.0 and v1.1 each require
`6 / 6` retrieval mappings (100% coverage); security-only and no-evidence
cases are excluded from this gate.
Duplicate/ambiguous entries and missing mappings fail fast;
the runner must not substitute doubles or omit cases to create a quality score.

## Versioning and results

Dataset version and runner version are separate required result fields. A
dataset change requires schema/adapter review and a new version or explicit
compatibility decision. Results preserve raw case IDs but never raw protected
content in reports.
