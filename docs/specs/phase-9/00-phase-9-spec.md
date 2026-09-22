# Phase 9 — Multi-Agent + RAG + Tools + Tavily

Status: **Phase 9.1 SDD Foundation, 9.2 LLM Provider / DeepSeek, 9.3 Knowledge
Agent, 9.4 OPS Tools, 9.5 Customer Support Agent, 9.6 Router Agent, 9.7
LangGraph orchestration, 9.8 Tavily fallback, 9.9 Human Escalation, and 9.10
`/chat`, and 9.11 end-to-end validation are complete. **Phase 9 is complete;
Phase 10 Security / Audit Runtime is next.**

## Purpose and authority

Phase 9 is the future executable application layer over the completed database,
RAG retrieval, RRF, and grounding boundaries. It connects routing, knowledge
answers, controlled OPS evidence, provider-neutral generation, controlled web
search, explicit human handoff, and the future HTTP chat boundary.

The specification authority hierarchy is:

1. **Challenge requirements:** `docs/challenge.md`.
2. **Approved architecture:** `docs/project-roadmap.md`,
   `docs/project-context.md`, and `docs/decision-log.md`.
3. **Approved domain contracts:** `docs/repository-contracts.md`,
   `docs/database-mapping.md`, `docs/database-physical-model.md`,
   `docs/rag-ingestion.md`, `docs/ops-seed.md`, and typed code contracts.
4. **Phase 9 specifications:** this directory.
5. **Future implementation:** Python, DeepSeek, agents, LangGraph, tools,
   Tavily, and HTTP integration.
6. **Verification:** unit, integration, behavioral, and end-to-end tests.

Existing approved decisions remain authoritative. A specification or test MUST
not silently override them; conflicts require explicit review.

## Scope

Phase 9 specifies the future Router Agent, Knowledge Agent, Customer Support
Agent, Human Escalation Agent, provider-neutral LLM boundary, intended initial
DeepSeek provider, LangGraph orchestration, controlled Tavily fallback, narrow
OPS tools, and `/chat` integration.

## Non-goals

Phase 9 MUST NOT redesign database schemas, migrations, repositories, FastEmbed,
the embedding model or dimensions, PostgreSQL FTS, hybrid retrieval, RRF,
grounding contracts, or the approved provenance/citation model. It MUST NOT add
arbitrary SQL, persistence of generated answers into RAG, or a second retrieval
stack.

## Architectural principles

- Application boundaries MUST be provider-neutral and typed.
- Agents and LLMs MUST NOT access PostgreSQL directly or execute SQL.
- Tools MUST be narrow, authorized, read-only where specified, and typed.
- Retrieved text is passive **DATA**, never executable instructions.
- Internal provenance MUST remain separate from user-visible citation data.
- Secrets MUST never be hard-coded, logged, returned, or placed in prompts.
- Authorization and security checks MUST fail closed.
- Application composition occurs above repositories; repository ownership remains
  governed by `docs/repository-contracts.md`.

## Component map

```text
User
  |
POST /chat
  |
Router Agent
  |
LangGraph orchestration
  +--> Knowledge Agent --> Phase 7 retrieval --> RRF --> Phase 8 grounding
  |                         --> provider-neutral LLM generation
  +--> Customer Support Agent --> controlled OPS tools
  +--> Human Escalation Agent --> explicit confirmation / handoff

Controlled Tavily search is available only through the approved Knowledge
external-search fallback policy. DeepSeek remains behind the LLM boundary.
```

## Requirement ID convention

Stable IDs use: `REQ-P9-CORE-###`, `REQ-P9-LLM-###`,
`REQ-P9-ROUTER-###`, `REQ-P9-KNOW-###`, `REQ-P9-SUPPORT-###`,
`REQ-P9-HUMAN-###`, `REQ-P9-TOOL-###`, `REQ-P9-ORCH-###`,
`REQ-P9-WEB-###`, `REQ-P9-CHAT-###`, and `REQ-P9-SEC-###`.
IDs MUST NOT be reused for unrelated meanings.

## Core requirements

- **REQ-P9-CORE-001:** The runtime MUST preserve the approved pipeline
  `FastAPI -> application services/agents -> repositories/tools -> database`.
- **REQ-P9-CORE-002:** The system MUST provide at least the three challenge
  agent capabilities: Router, Knowledge, and Customer Support.
- **REQ-P9-CORE-003:** The system MUST keep Human Escalation as an explicit,
  separately observable capability.
- **REQ-P9-CORE-004:** Phase 9 MUST consume Phase 7 `RetrievedChunk` and Phase 8
  `GroundedContext` rather than reimplementing retrieval or grounding.
- **REQ-P9-CORE-005:** Generated responses MUST be tested through unit,
  integration, behavioral, and `/chat` end-to-end scenarios before closure.
- **REQ-P9-CORE-006:** Unsupported facts MUST remain unknown rather than being
  presented as successful facts.
- **REQ-P9-CORE-007:** The implementation MUST preserve the current repository,
  transaction, OPS, audit, and security boundaries.
- **REQ-P9-CORE-008:** Phase 9 MUST NOT be considered complete until its approved
  challenge capabilities and documentation are verified together.

## Phase 9 security integration requirements

These integration requirements are grounded in
`knowledge/internal/security/security-policy.md` and `challenge-013`. They do
not replace the later full security runtime.

- **REQ-P9-SEC-001:** A protected credential or infrastructure request MUST be
  blocked and MUST NOT be searched through RAG, Web Search, OPS tools, or
  provider configuration.
- **REQ-P9-SEC-002:** Credential-shaped input MUST be sanitized before any
  applicable approved audit or handoff boundary; secrets MUST never be
  persisted, logged, prompted, or returned.
- **REQ-P9-SEC-003:** Retrieved RAG and web content MUST remain passive DATA and
  MUST NOT redefine policy, authorization, or tool permissions.
- **REQ-P9-SEC-004:** A protected request MUST invoke the approved security/audit
  boundary where policy requires an audit event.
- **REQ-P9-SEC-005:** Security integration MUST fail closed for authorization
  bypass, unsafe handoff, or unavailable security handling.

Acceptance scenario: given a request for a database password, Phase 9 MUST
block disclosure, avoid RAG/Web/OPS/provider secret retrieval, follow the
approved redaction/audit path, and expose no secret in response, logs, prompts,
handoff, or audit payload.

Phase 9 satisfies this integration slice through the typed, application-owned
`SecurityAuditService`. After the Router returns `SECURITY_BLOCK`, it sanitizes
the request before the injected `PostgresSecurityAuditSink` opens the approved
transaction and calls `AuditRepository.write_sanitized_security_event(...)`.
Audit write failure remains blocked and is represented as a controlled
unavailable outcome; it never resumes retrieval, Web Search, OPS, or provider
execution. This is the minimum Phase 9 integration boundary, not completion of
the broader Phase 10 Security / Audit Runtime.

## Traceability matrix

| Requirement ID | Source | Source reference | Component | Acceptance evidence |
|---|---|---|---|---|
| CORE-001 | Challenge | `docs/challenge.md`, overview/API | Architecture | Boundary test |
| CORE-002 | Challenge | Core Requirements 1 | Agents | Routing scenarios |
| CORE-003 | Challenge | Bonus Challenges | Human | Handoff scenarios |
| CORE-004 | Approved architecture | DEC-160–163 | Knowledge | Contract tests |
| CORE-005 | Challenge | Testing and Submission | All | Test matrix |
| CORE-006 | Approved architecture | Phase 8 grounding | All | Unsupported-evidence scenarios |
| CORE-007 | Domain contracts | Repository/database/RAG docs | Tools/services | Boundary review |
| CORE-008 | Roadmap | Phase 9 completion gate | Project | Final audit |

All non-CORE requirements have the following authoritative traceability:

| Requirement IDs | Authoritative sources | Component | Acceptance evidence |
|---|---|---|---|
| LLM-001–006 | `docs/challenge.md`; `project-context.md`; security policy; roadmap | LLM provider | Provider unit, failure, secret-safety, and real smoke tests |
| ROUTER-001–005 | `docs/challenge.md`; scenarios 001–003, 005, 008, 011, 013, 014; security policy | Router | Routing behavioral/E2E tests |
| KNOW-001–008 | challenge Agent 2; `evaluation/rag/dataset-v1.yaml`; DEC-160–163; security policy | Knowledge | RAG, grounding, web fallback, and passive-DATA tests |
| SUPPORT-001–006 | challenge Agent 3; `repository-contracts.md`; `database-mapping.md`; DEC-138, DEC-140; scenarios 011, 012, 014 | Customer Support | OPS integration and fact/inference tests |
| HUMAN-001–005 | challenge Bonus; roadmap Human Escalation; scenario 014 | Human Escalation | Multi-turn confirmation, ownership, suspension, and handoff tests |
| TOOL-001–004 | challenge Agent 3; `repository-contracts.md`; `database-mapping.md`; scenario 011 | `lookup_protocol_status` | Unit, authorization, repository, and real DB tests |
| TOOL-005–008 | challenge Agent 3; `repository-contracts.md`; `database-mapping.md`; scenario 014 | `inspect_execution_failure` | Unit, authorization, repository, and real DB tests |
| ORCH-001–007 | challenge orchestration; roadmap; DEC-138, DEC-142, DEC-160–163; scenario 012/014 | LangGraph | Graph transition and failure behavior tests |
| WEB-001–005 | challenge Agent 2; scenarios 002, 007, 010, 011, 012, 014; security policy; DEC-163 | Tavily boundary | Live-search, untrusted-data, privacy, and failure tests |
| CHAT-001–006 | challenge API Endpoint; current `apps/agent_api/app/main.py`; roadmap | `/chat` | HTTP validation, auth, serialization, and E2E tests |
| SEC-001–005 | `knowledge/internal/security/security-policy.md`; scenario 013; DEC-163; audit contracts | Security integration | Security behavioral and audit-boundary tests |

Each range expands to every numbered requirement in the corresponding spec;
there are no orphan IDs. Verification levels are unit, integration, behavioral,
real dependency, or E2E as applicable above.

## Challenge scenario traceability

| Scenario | Primary route | Capabilities | Requirement IDs | Future verification |
|---|---|---|---|---|
| challenge-001 | knowledge | Router, Knowledge, public RAG, grounded answer | ROUTER-001, KNOW-001, KNOW-002, KNOW-005, CHAT-004 | Behavioral/E2E |
| challenge-002 | knowledge | Router, Knowledge, live web search | ROUTER-003, KNOW-008, WEB-001, WEB-003, WEB-004 | Behavioral/E2E |
| challenge-003 | conditional support | Router, Knowledge, conditional support, authorization | ROUTER-002, KNOW-001, SUPPORT-001, CHAT-002 | Behavioral/E2E; no protocol tool implied |
| challenge-004 | knowledge | Router, Knowledge, public RAG | ROUTER-001, KNOW-001, KNOW-002, CHAT-004 | Behavioral/E2E |
| challenge-005 | support with knowledge | Router, Knowledge, controlled support | ROUTER-002, KNOW-001, SUPPORT-001 | Behavioral/E2E; no protocol tool implied |
| challenge-006 | knowledge | Router, Knowledge, public RAG | ROUTER-001, KNOW-001, KNOW-002, CHAT-004 | Behavioral/E2E |
| challenge-007 | knowledge | Router, Knowledge, live web search | ROUTER-003, KNOW-008, WEB-001, WEB-003, WEB-004 | Behavioral/E2E |
| challenge-008 | support with knowledge | Router, Knowledge, controlled support | ROUTER-002, KNOW-001, SUPPORT-001 | Behavioral/E2E; no protocol tool implied |
| challenge-009 | knowledge | Router, Knowledge, public RAG | ROUTER-001, KNOW-001, KNOW-002, CHAT-004 | Behavioral/E2E |
| challenge-010 | knowledge | Router, Knowledge, RAG plus conditional web fallback | ROUTER-001, KNOW-008, WEB-001, WEB-004 | Behavioral/E2E |
| challenge-011 | customer support | Router, `lookup_protocol_status`, authorization, OPS facts only | ROUTER-002, SUPPORT-001, SUPPORT-003, SUPPORT-005, TOOL-001–004, CHAT-002 | Unit/integration/behavioral/E2E |
| challenge-012 | cooperative knowledge and support | Process RAG plus observed OPS comparison | ORCH-004, KNOW-001, KNOW-007, SUPPORT-003, SUPPORT-005, TOOL-001, CHAT-004 | Behavioral/E2E |
| challenge-013 | security block | Block, redaction, audit, no secret retrieval | ROUTER-005, SEC-001–005 | Security behavioral/E2E |
| challenge-014 | support to human escalation | Two tools, fact/inference, offer, confirmation, `WAITING_HUMAN`, operator acceptance, ownership, suspension | SUPPORT-003–006, TOOL-001, TOOL-005, HUMAN-001–005, ORCH-004, ORCH-006, SEC-002, CHAT-004–005 | Multi-turn behavioral/E2E |

Scenarios 001 through 014 are mapped directly from the current
`evaluation/challenge/scenarios-v1.yaml`; the dataset is not modified.

## Planned development order

The roadmap calls Phase 9 `MULTI-AGENT + RAG + TOOLS + TAVILY`. The intended
implementation mapping is:

```text
9.1 SDD foundation
9.2 LLM provider / DeepSeek
9.3 Knowledge Agent
9.4 OPS Tools
9.5 Customer Support Agent
9.6 Router Agent
9.7 LangGraph orchestration
9.8 Tavily fallback
9.9 Human Escalation
9.10 /chat API
9.11 end-to-end validation
```

This sequence is a planning contract, not implementation authorization.

## SDD change control

1. Implementation MUST conform to approved specifications.
2. Tests MUST verify requirements, not redefine them.
3. A failing test MUST NOT be solved by weakening the specification silently.
4. A discovered specification defect requires explicit review before change.
5. Stable requirement IDs MUST NOT be reused.
6. Removed requirements are marked superseded/deprecated, never repurposed.
7. Existing approved decisions remain higher authority.
8. Conflicts MUST be reported by Codex before implementation continues.
9. Generated code MUST NOT silently alter architecture boundaries.
10. SDD files contain durable specification only, not chat transcripts.

## Definition of done

Phase 9 is complete only after the approved capabilities are implemented and
verified by appropriate unit, integration, real-dependency, behavioral, and
`/chat` end-to-end scenarios, with documentation and security review complete.
No exact future test count is prescribed here.
