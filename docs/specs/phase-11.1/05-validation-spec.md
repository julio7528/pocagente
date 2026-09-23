# Phase 11.1 — Validation and Traceability Specification

## Evidence rules

All normal tests use the approved project `.venv`, deterministic typed doubles for unstable providers, no external HTTP/DeepSeek/Tavily, and the real local application composition where integration behavior is asserted. Phase 11 historical datasets and canonical reports are read-only regression baselines. Any Phase 11.1 evidence artifact is separately versioned and never overwrites Phase 11 reports.

## Requirement-to-evidence matrix

| Requirement | Required evidence |
|---|---|
| `REQ-P11R-CORE-001` | dependency/import audit; `/chat` composition tests |
| `REQ-P11R-CORE-002` | immutable-artifact checksum/path regression; no historical diff |
| `REQ-P11R-CORE-003` | mapper authorization/scope/policy negative tests |
| `REQ-P11R-CORE-004` | normal test network/provider spies |
| `REQ-P11R-CORE-005` | fixture safety/secret scan/local-only integration record |
| `REQ-P11R-CORE-006` | production-to-evaluation import scan |
| `REQ-P11R-ROUTER-001` | security-before-classifier invocation-order test |
| `REQ-P11R-ROUTER-002` | strict schema/unknown enum/extra-field tests |
| `REQ-P11R-ROUTER-003` | no-tool classifier spy and forbidden output tests |
| `REQ-P11R-ROUTER-004` | intent-to-decision table tests |
| `REQ-P11R-ROUTER-005` | greeting-plus-product/support/security E2E cases |
| `REQ-P11R-ROUTER-006` | missing/authorized OPS context tests |
| `REQ-P11R-ROUTER-007` | timeout/provider/invalid-output degradation tests |
| `REQ-P11R-ROUTER-008` | unmapped/impossible intent-policy rejection tests |
| `REQ-P11R-ROUTER-009` | validation-before-router-state test |
| `REQ-P11R-ROUTER-010` | awaited provider double, timeout/error/invalid-output/no-deadlock tests; source scan rejects `asyncio.run()`/nested-loop routing workarounds; async `/chat` graph compatibility |
| `REQ-P11R-KNOW-001` | typed scope model/mapper tests |
| `REQ-P11R-KNOW-002` | public and internal scope reach both lexical and semantic repository predicates in one journey; mismatch between channels fails before RRF |
| `REQ-P11R-KNOW-003` | public query cannot return internal source provenance test |
| `REQ-P11R-KNOW-004` | absent public corpus controlled-insufficiency test; real local public-corpus availability validation |
| `REQ-P11R-KNOW-005` | structured answered/insufficient/invalid outcome tests |
| `REQ-P11R-KNOW-006` | citation-subset and invented-citation rejection tests |
| `REQ-P11R-KNOW-007` | UNKNOWN-like rendered text cannot create `ANSWERED`; graph assembly test |
| `REQ-P11R-KNOW-008` | registry-only is rejected as publication evidence; real local PostgreSQL/RAG inspection verifies approved public provenance/chunks or exposes absence without silent success |
| `REQ-P11R-WEB-001` | public RAG sufficient/no-Web and insufficient/Web ordered-call tests |
| `REQ-P11R-WEB-002` | weather/current exchange Web-required tests |
| `REQ-P11R-WEB-003` | stable general-public fact and paraphrase Web journey tests |
| `REQ-P11R-WEB-004` | internal/OPS no-Web substitution negatives |
| `REQ-P11R-WEB-005` | live evidence non-persistence observer test |
| `REQ-P11R-WEB-006` | security zero-Web and prohibited-scope tests |
| `REQ-P11R-SEC-001` | preflight ordering and no semantic-call-on-block test |
| `REQ-P11R-SEC-002` | normalized Portuguese/English injection family parameterization |
| `REQ-P11R-SEC-003` | resource-family to typed Phase 10 classification tests |
| `REQ-P11R-SEC-004` | sanitized event/action `BLOCK` terminal integration test |
| `REQ-P11R-SEC-005` | per-request forbidden-capability delta spies |
| `REQ-P11R-SEC-006` | PostgreSQL/pgvector high-level question non-block test |
| `REQ-P11R-SEC-007` | semantic-output cannot change security classification test |
| `REQ-P11R-CONV-001` | `oi`, `bom dia`, `obrigado`, orientation tests |
| `REQ-P11R-CONV-002` | zero-capability invocation observation |
| `REQ-P11R-CONV-003` | substantive-prefix route tests |
| `REQ-P11R-CONV-004` | public response/internal-metadata safety test |
| `REQ-P11R-INTEG-001` | authenticated FastAPI `/chat` E2E |
| `REQ-P11R-INTEG-002` | real graph node/edge invocation integration tests |
| `REQ-P11R-INTEG-003` | OPS authorization and expected-vs-observed E2E |
| `REQ-P11R-INTEG-004` | API model/serialization/secret-safety tests |
| `REQ-P11R-INTEG-005` | CLI source inspection + real-app manual smoke |
| `REQ-P11R-INTEG-006` | end-to-end trusted scope propagation spy: RouterDecision → graph → knowledge request/agent → Hybrid → lexical/semantic repository; query/LLM/Web cannot mutate it; RRF receives admitted candidates only |
| `REQ-P11R-VAL-001` | Challenge scenario family traceability below |
| `REQ-P11R-VAL-002` | unit suite for semantic contract/mapper/security/scope |
| `REQ-P11R-VAL-003` | local integration for retrieval/filter/graph/Web/OPS |
| `REQ-P11R-VAL-004` | authenticated E2E and manual CLI matrix |
| `REQ-P11R-VAL-005` | Phase 11 RAG + Challenge regression execution, artifacts preserved |
| `REQ-P11R-VAL-006` | full pytest, compileall, pip check, imports, diff check, secret scan |

## Scenario traceability

The design is evaluated semantically, never by literal-question routing rules. `docs/challenge.md` examples provide family evidence: Get Clássica vs Get Smart, Pix, receivables advance, crediário, Payment Link/WhatsApp, and appropriate machine/support information test public Getnet scope; weather tomorrow/current exchange test current Web; settlement/deposit/protocol and transaction decline test controlled support/OPS; expected-vs-observed tests cooperation. Paraphrases, accents, polite prefixes, Portuguese and English variants are required.

Mandatory added cases include public Getnet insufficient-to-Web fallback; RAG+Web both insufficient typed outcome; internal insufficiency without public substitution; classifier timeout/invalid output; credential/direct DB/protected-infrastructure requests; `ignore`/`desconsidere` variants; high-level architecture non-blocking; greeting plus substantive public/OPS/security messages; and every listed conversational message.

Scope integration must additionally prove `PUBLIC_GETNET` and `INTERNAL` reach both retrieval channels with exactly the same trusted predicate, that query wording and model/Web output cannot alter it, and that RRF receives only already-admitted candidates. Real local public-corpus validation must distinguish registry records from active published documents/chunks and reject INTERNAL provenance as public-corpus evidence. No validation may fetch registry URLs.

## Regression and closure gates

Later implementation must run Router, LangGraph, Knowledge, WebKnowledge, security/AUDIT, OPS authorization, `/chat`, Human Escalation, lexical/semantic/Hybrid/RRF/grounding, unit/integration/E2E/manual CLI tests, plus full normal pytest, compileall, pip check, imports, `git diff --check`, dependency-direction scan, and secret scan. Existing Phase 11 Local RAG and deterministic Challenge evaluation must be re-run as regression evidence without altering their historical datasets/reports. External provider validation remains explicit opt-in and outside normal closure.

## Validation requirements

* `REQ-P11R-VAL-001`: Challenge families and paraphrases trace to semantic, not literal, validation.
* `REQ-P11R-VAL-002`: deterministic unit coverage proves contracts and negative invariants.
* `REQ-P11R-VAL-003`: integration proves real repository/graph/security/authorization boundaries.
* `REQ-P11R-VAL-004`: authenticated E2E and CLI validate the actual application path.
* `REQ-P11R-VAL-005`: closed Phase 11 RAG/Challenge evidence is preserved and re-run only as regression.
* `REQ-P11R-VAL-006`: static, environment, dependency, and secret-safety gates pass.
