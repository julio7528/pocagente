# Phase 9.4 — Customer Support tools

Status: Phase 9.4 implementation complete. Both tools are read-only,
authorization-gated, repository-bound, and validated with mocked repositories
and opt-in real PostgreSQL synthetic OPS records. Customer Support reasoning is
not implemented.

Tools are narrow application interfaces over approved repository methods. They
never expose SQL, tables, cursors, connection objects, or arbitrary query
parameters.

## `lookup_protocol_status`

Purpose: retrieve observed operational facts for one protocol.

Input contract: a non-blank `protocol_number` and the caller authorization
context supplied by the application boundary. The caller cannot choose a table,
SQL statement, or repository query.

Output contract: typed `ProtocolStatusFacts` from
`apps/agent_api/app/database/models.py`, with safe absence/error states.

- **REQ-P9-TOOL-001:** The tool MUST be read-only.
- **REQ-P9-TOOL-002:** It MUST use parameterized approved repository access.
- **REQ-P9-TOOL-003:** It MUST return typed facts, not raw rows or cursors.
- **REQ-P9-TOOL-004:** It MUST NOT infer diagnosis or probable root cause.

### `lookup_protocol_status` acceptance

```text
Given: an authorized valid protocol identifier.
When: the tool executes.
Then: it uses the approved OperationalRepository path and returns
      ProtocolStatusFacts or a controlled absence/error result.
And: it exposes no SQL, cursor, table, credential, or arbitrary database access.
```

The same contract MUST return a controlled validation result for a blank
protocol, a controlled absence for an unknown protocol, an authorization denial
for an unauthorized caller, and a sanitized controlled error for repository
failure.

## `inspect_execution_failure`

Purpose: retrieve observed failure evidence for one protocol and optional run
identifier.

Input contract: non-blank protocol number and optional approved `run_id`; no
table, SQL, or arbitrary filter is accepted.

Output contract: typed `ExecutionFailureEvidence` from the approved database
model/repository boundary, with sanitized controlled errors.

- **REQ-P9-TOOL-005:** The tool MUST be read-only and repository-bound.
- **REQ-P9-TOOL-006:** It MUST return observed facts/evidence only.
- **REQ-P9-TOOL-007:** It MUST NOT perform cross-schema SQL outside the approved
  `OperationalRepository` ownership boundary.
- **REQ-P9-TOOL-008:** It MUST not expose SQL, credentials, raw diagnostics, or
  unsupported root-cause claims.

### `inspect_execution_failure` acceptance

```text
Given: an authorized valid protocol and optional valid run identifier.
When: the tool executes.
Then: it returns typed observed ExecutionFailureEvidence when available.
And: no evidence, invalid input, unauthorized access, and repository failure
     produce distinct controlled safe outcomes.
And: the tool returns facts only; any later diagnosis remains agent inference.
```

Both tools require future unit tests with mocked repositories, authorization and
error tests, and real PostgreSQL integration tests using existing synthetic OPS
records. They are not direct agent-to-database interfaces.
