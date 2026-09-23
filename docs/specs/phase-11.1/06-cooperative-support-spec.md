# Phase 11.1.5.3 — Cooperative Customer Support Specification

Status: owner-requested remediation in progress; Phase 11.1 remains open.

This specification extends the Phase 11.1 runtime contracts for cooperative
OPS and Internal Knowledge support. It does not authorize schema/migration
changes, production identity changes, public Web as private/process evidence,
or model-generated SQL.

## Authority and capability selection

The semantic classifier may return the existing primary intent plus a closed
set of evidence capability needs: `INTERNAL_KNOWLEDGE`, `PUBLIC_GETNET`,
`OPERATIONAL_FACTS`, `CURRENT_WEB`, `HUMAN`, and `CONVERSATIONAL`. The
deterministic Router validates combinations and chooses an existing route. In
particular, operational plus internal-knowledge needs select the cooperative
Knowledge + Customer Support route without introducing a new intent per
phrase. A need is not permission. OPS execution requires the trusted
`AuthenticatedPrincipal.can_read_operational_facts` value and remains enforced
by `ChatApplicationService` and the controlled tools.

The local CLI may create an explicitly identified synthetic
`SUPPORT_AGENT`/OPS-read test principal by default. An explicit `CLIENT`
unauthorized mode remains available. Production FastAPI authentication and
authorization are unchanged.

## Operational investigation plan

An authorized support planner may return a validated `OperationalInvestigationPlan`
with an objective, optional protocol/run selectors, bounded result limit,
optional approved discovery order/status/robot criteria, and a bounded set of
evidence needs. Supported evidence categories are:

* `SERVICE_REQUEST`
* `ORIGIN_EMAIL`
* `EMAIL_ATTACHMENTS`
* `AUTOMATION_RUNS`
* `ESTABLISHMENTS`
* `EXECUTION_TIMELINE`
* `FAILURE_EVIDENCE`

The plan carries no SQL, schema/table/column names, JOINs, arbitrary filters,
credentials, authorization flags, route values, raw tool/repository names, or
free-text rationale. Application code maps each category to a named
application-owned read capability and parameterized repository method. The
plan is bounded to at most three investigation rounds; the executor stops
when sufficient evidence is available or the bound is reached.

An executor may request additional categories only through another validated
plan from the closed category set. It cannot execute arbitrary tools. Each
round records requested categories, categories loaded, and typed sufficiency
status as safe telemetry. It never records chain-of-thought.

## Typed OPS read model and relationships

Raw database rows stay inside `OperationalRepository` and the centralized
mapping layer. Add immutable typed `IncomingEmailRecord` and
`EmailAttachmentRecord` models where absent. Preserve the current typed
`AutomationRunRecord`, `ServiceRequestRecord`, `EstablishmentRecord`, and
`ExecutionLogRecord`.

`ProtocolCaseFacts` is an application/domain aggregate with optional typed
fields for the request, origin email, attachments, automation runs,
establishments, execution timeline, and failure evidence. It contains only
observed data; repositories and aggregate assembly do not infer causes or
recommend actions. Requested plan categories control which facts are loaded.

The approved physical foreign keys govern correlation:

* Request to origin email: `service_requests.email_id`; the composite
  `(email_id, r1_run_id)` relationship validates the request's R1 intake
  provenance against `incoming_emails(email_id, run_id)`.
* Origin email to R1: `incoming_emails.run_id`; its run is checked as R1 by
  application logic because the physical FK guarantees parent existence but
  does not enforce the robot value.
* Email to attachments: `email_attachments.email_id`.
* Request to establishments: `establishments.request_id`; each establishment
  also references its source attachment. The application verifies that the
  attachment belongs to the request's origin email before combining those
  records.
* R1/R2 executions to request: `execution_log.request_id` when present. Each
  event's mandatory `(run_id, robot)` FK maps to its automation run. The
  request's `r1_run_id` independently identifies the creating R1 run. There
  is no `service_requests.r2_run_id`; R2 runs are discovered from request-linked
  log facts, not guessed from insertion order.
* Timeline: request-linked events use `execution_log.request_id`; per-run
  events use `execution_log.run_id`; optional email, attachment, and
  establishment IDs are cross-checked against the aggregate's FK-derived
  entities.

Only repository operations supported by actual keys, FKs, and approved indexes
may be added. Reads are parameterized, schema-qualified, bounded, read-only,
and limited to `ops`. No migrations or schema changes are in scope.

## Discovery and timestamp semantics

“Latest protocol/request” is ordered by `service_requests.created_at DESC`,
then `request_id DESC`; this answers request-record recency.

“Latest protocol that executed” is ordered by the greatest actual
`automation_runs.started_at` among the request's R1 run and R2 runs linked by
request-correlated execution-log facts. Use run ID only as a stable tie-breaker.
The latest event within that run is ordered by `execution_log.logged_at DESC`,
then `log_id DESC`. If no request-linked run/event establishes execution, say
that execution recency is unavailable rather than substituting protocol text,
database `created_at`, or status update time.

For “when was the protocol created?”, prefer an actual `PROTOCOLO_CRIADO`
`execution_log.logged_at` event when present. `service_requests.created_at` is
record/persistence time. If the values materially disagree, report both with
their meanings and do not silently choose one.

## Internal PDD/SDD cooperation

Customer Support questions about observed status/result/timing/event/failure
normally need OPS only. Requests asking what should happen, whether execution
matches procedure, recovery/reprocessing steps, or required support action
select both operational facts and `INTERNAL_KNOWLEDGE`. The Router must not
use Public Web for internal procedure authority.

After safe OPS facts are loaded, the application may formulate a bounded
internal retrieval query from the original question and selected observed
facts (for example, robot/stage/failure category). Protocol identifiers alone
are not process-document vocabulary. The generated query is data only and
cannot contain instructions, SQL, credentials, tool commands, or policy
overrides. Internal retrieval remains scoped to `KnowledgeScope.INTERNAL`.

Cooperative synthesis receives the original question, validated internal
grounding and citations, and selected typed OPS facts. The final answer
distinguishes:

1. observed OPS facts;
2. documented expected/procedural behavior with preserved RAG citations;
3. explicitly labeled inference, if useful.

It cannot claim that a procedure requires an action unless retrieved evidence
supports it. It cannot invent unavailable sender/date/run/result facts. PDD is
the business-rule source; SDD/technical overview describes implementation and
may differ. Preserve material source disagreements for the answer.

## Evidence and iteration requirements

* `REQ-P11R-SUPPORT-001`: semantic capability needs select OPS-only or
  cooperative Internal Knowledge + OPS behavior through deterministic route
  mapping, without phrase-specific intent growth.
* `REQ-P11R-SUPPORT-002`: only the authenticated principal authorizes OPS;
  route, model output, and user text cannot grant read authority.
* `REQ-P11R-SUPPORT-003`: operational investigation plans are strict,
  bounded, allowlisted evidence plans without SQL/schema/tool/authority data.
* `REQ-P11R-SUPPORT-004`: multi-round investigation accumulates approved
  evidence, stops on sufficiency, and never exceeds three rounds.
* `REQ-P11R-SUPPORT-005`: typed read models and methods cover the actual six
  OPS tables only through approved relationships and mappings.
* `REQ-P11R-SUPPORT-006`: protocol aggregates correlate origin email, R1/R2
  runs, attachments, establishments, timeline, and failure facts only through
  approved keys/FKs.
* `REQ-P11R-SUPPORT-007`: request recency and execution recency use distinct
  domain timestamps; persistence time is not mislabeled as event time.
* `REQ-P11R-SUPPORT-008`: remediation/procedure questions use INTERNAL RAG
  and safe query formulation; OPS-only questions do not query PDD/SDD by
  default, and Public Web is never internal authority.
* `REQ-P11R-SUPPORT-009`: cooperative synthesis preserves evidence citations
  and separates documented behavior, observed facts, and inference.
* `REQ-P11R-SUPPORT-010`: normal local CLI uses a labeled synthetic authorized
  support principal, while explicit CLIENT mode and production `/chat`
  authorization remain unchanged.

## Real CLI acceptance matrix

Run with plain `python scripts/chat_cli.py`, trace enabled, no role/authorization
flags or manual `/ops` setup:

1. `qual o status do protocolo POC-OPS-0004?`
2. `como consulto o registro do protocolo POC-OPS-0004?`
3. `o que aconteceu no POC-OPS-0004?`
4. `qual o resultado do protocolo POC-OPS-0004?`
5. `qual protocolo mais recente?`
6. `qual protocolo mais recente que executou?`
7. `quais foram os últimos três protocolos executados?`
8. `quando o POC-OPS-0004 executou?`
9. `onde o POC-OPS-0004 falhou?`
10. `qual foi o último passo bem-sucedido antes da falha?`
11. `o que preciso fazer para executar o POC-OPS-0005 novamente?`
12. `esse erro do POC-OPS-0005 permite reprocessamento?`
13. `o que o PDD/SDD diz que deveria acontecer depois dessa falha?`
14. `o que deveria ter acontecido versus o que realmente aconteceu no POC-OPS-0005?`
15. `me diga de onde veio a solicitação do POC-OPS-0004 e o que aconteceu até o fim`

For each, verify route/capability needs, trusted authorization, validated plan,
actual evidence categories and repository methods, INTERNAL RAG/cooperative
synthesis when required, and final typed response. Compare material claims to
the actual local PostgreSQL facts. If POC-OPS-0005 or any requested evidence is
absent, report controlled insufficiency; do not seed or fabricate data.

Then run equivalent CLIENT/unauthorized requests. They must not invoke any OPS
tool/repository method, even when the model requests operational facts.

## Anti-hardcoding paraphrases

After the fixed matrix, test these unseen formulations:

* `me conta toda a história do POC-OPS-0004`
* `de onde surgiu esse protocolo e onde terminou?`
* `qual foi o pedido que rodou por último?`
* `pega o último que executou e me diz se terminou bem`
* `esse aqui quebrou no R2, o que o procedimento manda fazer?`
* `consigo rodar novamente ou existe alguma etapa antes?`

Success requires semantic generalization, not one new route/enum/rule per
sentence. A contextual “esse aqui” paraphrase must use only an unambiguous
trusted conversation selection; otherwise ask a clarification.
