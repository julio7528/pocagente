# Phase 11.1.5.5 — Temporal and Analytical Customer Support

Status: owner-requested remediation in progress; Phase 11.1 remains open.

## Contract and ownership

Customer Support analytics extend `OperationalInvestigationPlan`; they do not
replace protocol-case investigation. A closed typed analytical plan composes
grain (`PROTOCOL`, `EXECUTION`, `EVENT`), metric (`EXISTS`, `COUNT`, `LIST`,
`FIRST`, `LAST`, `SUMMARY`), temporal expression, status/outcome filter, robot
filter, ordering, grouping, and bounded result limit. It contains no SQL,
schema/table/column identifiers, join clauses, or arbitrary expressions.

The planner selects semantic dimensions only. Application code resolves
relative dates, validates grain-compatible timestamp and status semantics,
checks the authenticated OPS-read context, and maps the validated query to
fixed parameterized read-only repository paths. PostgreSQL performs filtering,
ordering, and aggregation. The language model summarizes typed aggregates and
does not count records itself.
If a synthesis response fails its strict typed JSON contract, the agent may make
one bounded format-only retry with the same question and evidence; the invalid
response is never reused as context, and no new evidence/tool request is added.

An exact `status_filter` remains distinct from normalized `outcome_filter`:
for example, exact event status `ERROR` excludes `EXCEPTION`, while outcome
`FAILURE` includes both. The local CLI may carry the last validated analytics
grain to its next turn as semantic follow-up context; it is bounded to the
closed grain enum, transient to the CLI session, and never grants OPS access.
A unique selected protocol returned by a protocol-grain FIRST/LAST/single-result
query may be carried as a typed CLI selector for one following relational case
question, then cleared; the CLI never extracts it from generated prose.

## Temporal expressions and timezone

Supported expressions are `ALL_TIME`, `TODAY`, `YESTERDAY`, `THIS_WEEK`,
`LAST_WEEK`, `LAST_N_DAYS`, `THIS_MONTH`, `LAST_MONTH`, `CALENDAR_MONTH`,
`BETWEEN_DATES`, `BEFORE_DATE`, and `AFTER_DATE`. The model may provide bounded
integer/date components; it never returns calculated timestamps.

`OperationalTemporalResolver` uses an injectable clock and the single
`OPERATIONAL_TIMEZONE` setting. The local default is `America/Cuiaba`, matching
the project execution environment; deployments may override it. Database
instants remain timezone-aware UTC. Application resolution produces
timezone-aware half-open intervals `[start, end)` and converts boundaries to
UTC before repository execution. `TODAY`/`THIS_WEEK`/`THIS_MONTH` end at the
current instant; complete prior periods end at the next local boundary.
`LAST_WEEK` is the prior complete Monday-through-Sunday calendar week, whereas
`LAST_N_DAYS(7)` is the rolling seven-day interval ending now. A calendar month
without year means the most recent occurrence of that month, not a future
month.

## Grain and domain timestamp semantics

* `PROTOCOL` is one service request. A protocol's creation time is the
  `PROTOCOLO_CRIADO` event time when available, with `service_requests.created_at`
  used only as an explicitly identified persistence-time fallback. Protocol
  execution ordering is derived from correlated `automation_runs.started_at`:
  first is the minimum run start, last is the maximum run start. Time-filtered
  outcomes use `completed_at` for completed requests and the latest correlated
  error/exception event time for failed requests; they do not use request
  persistence/update timestamps as a substitute.
* `EXECUTION` is one R1/R2 automation run. Occurrence uses
  `automation_runs.started_at`; completion uses `finished_at`.
* `EVENT` is one execution-log event and uses `execution_log.logged_at`.

No grain substitutes persistence `created_at` for a requested execution/event
timestamp. Protocol outcome uses the authoritative service-request lifecycle:
`COMPLETED` is success, `FAILED` is failure, and nonterminal/other states remain
separately represented. Execution outcome uses `automation_runs.status`:
`SUCCESS` is success, `ERROR` is failure, and `RUNNING`/`PARTIAL` remain other.
Event outcome uses `execution_log.status`: `SUCCESS` is success, `ERROR` or
`EXCEPTION` is failure, and all rows still count once as events.

The current OPS schema has no trusted process-type attribute. An analytics
question about a named process may use the authorized cancellation OPS dataset
as its operational scope but must not claim an unsupported process-type filter.

## Clarification, authorization, and trace

Clarification is reserved for materially ambiguous grain/filter semantics.
Explicit executions, protocols, or log events choose their matching grain.
Bare “cases” may default to the established protocol-support domain only when
that interpretation is unambiguous; otherwise the agent asks whether protocols
or R1/R2 executions should be counted.

The principal's trusted `can_read_operational_facts` remains mandatory before
any analytics repository call. A plan never grants access. Trace may expose
validated grain, metric, temporal-expression enum, resolved interval, filters,
repository capability, result count, and timing; it never exposes SQL or raw
rows.

## Requirements

* `REQ-P11R-ANALYTICS-001`: one strict composable plan models grain, metric,
  temporal expression, filters, grouping, ordering, and bounded limit without
  phrase-specific workflow enums.
* `REQ-P11R-ANALYTICS-002`: protocol, execution, and event grains have distinct
  meanings and success/error status mappings.
* `REQ-P11R-ANALYTICS-003`: relative and calendar temporal expressions are
  resolved deterministically by application code with injectable clock and
  configured operational timezone; the LLM never calculates timestamps.
* `REQ-P11R-ANALYTICS-004`: domain timestamp semantics distinguish protocol
  creation/outcome time, first/last protocol execution, execution
  start/completion, and log event time from persistence time.
* `REQ-P11R-ANALYTICS-005`: first/last protocol execution ordering uses
  correlated run-domain timestamps, never request persistence ordering.
* `REQ-P11R-ANALYTICS-006`: bounded typed repository analytics use fixed
  parameterized allowlisted SQL and PostgreSQL performs counts/grouping.
* `REQ-P11R-ANALYTICS-007`: ambiguity triggers only a short clarification when
  grain materially changes the answer; complete temporal questions execute.
* `REQ-P11R-ANALYTICS-008`: OPS authorization remains trusted and no analytics
  path can be invoked for unauthorized principals.
* `REQ-P11R-ANALYTICS-009`: real CLI acceptance, unseen paraphrases, typed
  database cross-checks, zero-result periods, safe trace, and latency are
  regression gates.

## Runtime acceptance

The owner-specified Phase 11.1.5.5 22-query matrix and anti-hardcoding
paraphrases in the task are the real-runtime acceptance set. In-process tests
freeze the clock and compare typed query results to repository/database facts.
No seed rows, schema changes, indexes, migrations, or production authorization
changes are allowed for this remediation.
