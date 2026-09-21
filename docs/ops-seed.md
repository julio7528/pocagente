# OPS Synthetic Seed JSON Authoring Guide

## Purpose

OPS synthetic scenarios are described as JSON and executed by one reusable, validated seed engine. This is the permanent specification for creating new development/POC scenarios without scenario-specific Python code.

## Architecture

```text
database/seed/ops/scenarios/*.json
        -> loader.py
        -> Pydantic models / validation
        -> scenario_executor.py
        -> runner.py transaction boundary
        -> OperationalRepository
        -> PostgreSQL OPS
```

## Scenario location and naming

Place UTF-8 files under `database/seed/ops/scenarios/`. Use descriptive stable lowercase snake_case names, for example `caso_NNN_descricao.json`. The filename does not define runtime behavior; JSON content does.

## Required top-level contract

Each definition contains `scenario_id`, `protocol_number`, `email`, `attachment`, `establishment`, `request`, `r1`, and `r2`. `r2` may be `null` when the lifecycle legitimately terminates during R1. Exact field types and constrained values are defined by `database/seed/ops/models.py` and the approved OPS physical model.

## JSON authoring rules

- Use valid UTF-8 JSON with no comments.
- Keep `scenario_id` and `protocol_number` unique across discovered files.
- Use timezone-aware ISO-8601 timestamps; naive timestamps are invalid.
- Keep execution events chronological.
- Write human-readable messages in Portuguese.
- Use approved uppercase database status identifiers for technical states.
- Do not include SQL, Python expressions, repository method names, credentials, secrets, `.env` values, or arbitrary executable instructions.

All definitions are discovered and validated before persistent execution.

## Entity sections

- `email`: synthetic incoming-email facts.
- `attachment`: synthetic attachment and validation facts.
- `establishment`: establishment processing and upload/download state.
- `request`: protocol lifecycle and final outcome.
- `r1`: the R1 automation run and chronological events.
- `r2`: the optional R2 automation run and chronological events.

## Event structure

```json
{
  "timestamp": "2026-09-03T09:00:00-04:00",
  "event": "EVENT_IDENTIFIER",
  "status": "SUCCESS",
  "message": "Mensagem humana em português.",
  "references": ["email", "attachment", "request", "establishment"]
}
```

References may identify `email`, `attachment`, `request`, and `establishment`. Events must describe what actually happened, with non-blank messages and supported statuses.

## Lifecycle consistency

The validator enforces lifecycle relationships, not scenario names.

- Successful R1 normally has R1 `SUCCESS`, upload `SUCCESS`, request `WAITING_RESULT`, and an R2 definition for the subsequent result lifecycle.
- Failed R1 has R1 `ERROR`, request R1 status `FAILED`, establishment processing status `ERROR`, and no R2 definition. A failed upload has upload status `ERROR` and no upload timestamp.
- Successful R2 requires a successful R2 lifecycle, a successfully downloaded result, the corresponding download timestamp, and the terminal request and establishment states required by the current model.
- Failed R2 before successful download requires processing `ERROR`, download `ERROR`, `download_at` null, request `FAILED`, and a non-blank `failure_reason`, with error evidence in R2 events. A notification may populate `return_email_at` when it was actually sent.
- Failed R2 after successful download represents verification or later processing failure: download `DOWNLOADED`, `download_at` populated, processing `ERROR`, request `FAILED`, and non-blank `failure_reason`. Notification events and `return_email_at` are optional.

The current Pydantic validator is authoritative for supported combinations.

## Database constraint awareness

JSON validation does not replace PostgreSQL constraints. New lifecycle shapes must remain valid against `database/migrations/0003_ops_tables.sql` and `database/migrations/0005_constraints.sql`. Inspect those sources before introducing a new lifecycle pattern.

## Idempotency

`protocol_number` is checked before persistence. If it already exists, the runner reports `SKIPPED` and leaves the database unchanged. The runner never overwrites or duplicates an existing protocol.

## Transactions

One scenario equals one transaction. Unexpected persistence failure rolls back the transaction, so no partial scenario remains.

## Commands

Run from the `getnet-support` repository root:

```powershell
python -m database.seed.ops.runner --validate
python -m database.seed.ops.runner
python -m database.seed.ops.runner --scenario <scenario_id>
```

The repository root is required so Python can resolve the `database` package.

## Recommended authoring workflow

1. Read this guide.
2. Inspect the current `models.py` contract.
3. Inspect database constraints for a new lifecycle shape.
4. Create a JSON scenario with unique identity and protocol values.
5. Define the lifecycle and chronological events.
6. Run `--validate` and fix validation errors.
7. Execute only the new scenario first.
8. Verify persisted OPS facts.
9. Run the default runner again to confirm idempotency.

## Extension rule

If a valid business lifecycle is not supported by the current generic model, do not falsify the JSON. Confirm compatibility with the approved OPS physical model, then generalize the Pydantic contract and executor while remaining data-driven. Never add a `scenario_id` branch. Add focused tests and preserve compatibility with existing scenarios.
