"""Discovery and loading of JSON-only OPS seed definitions."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from database.seed.ops.models import OpsSeedScenario


DEFAULT_SCENARIOS_DIRECTORY = Path(__file__).with_name("scenarios")


def load_scenarios(directory: Path = DEFAULT_SCENARIOS_DIRECTORY) -> tuple[OpsSeedScenario, ...]:
    """Discover, validate, and order every JSON scenario deterministically."""

    scenarios: list[OpsSeedScenario] = []
    for path in sorted(directory.glob("*.json"), key=lambda candidate: candidate.name):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"Malformed OPS seed JSON: {path.name}") from error
        try:
            scenarios.append(OpsSeedScenario.model_validate(payload))
        except ValidationError as error:
            raise ValueError(f"Invalid OPS seed scenario: {path.name}") from error
    _validate_unique_scenarios(scenarios)
    return tuple(sorted(scenarios, key=lambda scenario: scenario.scenario_id))


def get_scenario(scenario_id: str, scenarios: Iterable[OpsSeedScenario]) -> OpsSeedScenario:
    """Select one already-validated scenario by its stable identity."""

    for scenario in scenarios:
        if scenario.scenario_id == scenario_id:
            return scenario
    raise ValueError(f"Unknown OPS seed scenario: {scenario_id}")


def _validate_unique_scenarios(scenarios: Iterable[OpsSeedScenario]) -> None:
    identities: set[str] = set()
    protocols: set[str] = set()
    for scenario in scenarios:
        if scenario.scenario_id in identities:
            raise ValueError(f"Duplicate OPS seed scenario ID: {scenario.scenario_id}")
        if scenario.protocol_number in protocols:
            raise ValueError(f"Duplicate OPS seed protocol: {scenario.protocol_number}")
        identities.add(scenario.scenario_id)
        protocols.add(scenario.protocol_number)
