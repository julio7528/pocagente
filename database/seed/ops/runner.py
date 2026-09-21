"""CLI runner for persistent repository-based OPS seed scenarios.
POWERSHELL EXECUTION: before python -m database.seed.ops.runner --validate after python -m database.seed.ops.runner

Rules: .json file need to be a new protocol and must be placed in .scenarios folder before running the runner command.

"""

from __future__ import annotations

import argparse
import asyncio
import os
import selectors
from collections.abc import Sequence
from pathlib import Path

from apps.agent_api.app.database.config import DatabaseConfig, load_database_config
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.repositories.operational import OperationalRepository
from database.seed.ops.loader import get_scenario, load_scenarios
from database.seed.ops.models import OpsSeedResult, OpsSeedScenario
from database.seed.ops.scenario_executor import execute_ops_scenario


_DATABASE_ENVIRONMENT_KEYS = frozenset(
    {
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_SSLMODE",
        "POSTGRES_CONNECT_TIMEOUT_SECONDS",
        "POSTGRES_POOL_MIN_SIZE",
        "POSTGRES_POOL_MAX_SIZE",
        "POSTGRES_POOL_TIMEOUT_SECONDS",
    }
)


def load_seed_database_config() -> DatabaseConfig:
    """Load local .env values into this CLI process, then use the approved loader."""

    dotenv_path = Path(__file__).resolve().parents[3] / ".env"
    if not dotenv_path.is_file():
        raise RuntimeError("Local .env is required to run OPS seed scenarios")

    for raw_line in dotenv_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in _DATABASE_ENVIRONMENT_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)

    return load_database_config()


async def execute_scenario(
    database: PostgresDatabase,
    scenario: OpsSeedScenario,
) -> OpsSeedResult:
    """Run one scenario atomically through its injected repository connection."""

    async with database.transaction() as connection:
        return await execute_ops_scenario(OperationalRepository(connection), scenario)


async def run_scenarios(
    config: DatabaseConfig,
    scenarios: Sequence[OpsSeedScenario],
) -> tuple[OpsSeedResult, ...]:
    """Own one explicit pool lifecycle while running selected scenarios."""

    database = PostgresDatabase(config)
    await database.open()
    try:
        results: list[OpsSeedResult] = []
        for scenario in scenarios:
            results.append(await execute_scenario(database, scenario))
        return tuple(results)
    finally:
        await database.close()


def _parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute synthetic OPS seed scenarios")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--scenario", help="Stable scenario identifier")
    selection.add_argument("--all", action="store_true", help="Run all discovered scenarios")
    parser.add_argument("--validate", action="store_true", help="Validate JSON scenarios without database access")
    return parser.parse_args(argv)


def _format_result(result: OpsSeedResult) -> str:
    if not result.created:
        return (
            f"{result.scenario_id} / {result.protocol_number} -> SKIPPED: already exists; database unchanged."
        )
    return (
        f"{result.scenario_id} / {result.protocol_number} -> CREATED: "
        f"R1 run={result.r1_run_id}, R2 run={result.r2_run_id}, "
        f"email={result.email_id}, attachment={result.attachment_id}, "
        f"request={result.request_id}, establishment={result.establishment_id}."
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run selected seed scenarios without printing configuration secrets."""

    arguments = _parse_arguments(argv)
    discovered = load_scenarios()
    if arguments.validate:
        print(f"Validated {len(discovered)} OPS JSON scenario(s).")
        return 0
    scenarios = (get_scenario(arguments.scenario, discovered),) if arguments.scenario else discovered
    results = asyncio.run(
        run_scenarios(load_seed_database_config(), scenarios),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )
    for result in results:
        print(_format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
