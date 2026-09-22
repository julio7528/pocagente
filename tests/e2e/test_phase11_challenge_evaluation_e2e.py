"""Authenticated deterministic dataset execution evidence for Phase 11.4."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from apps.agent_api.app.evaluation.challenge_runner import ChallengeEvaluationRunner
from apps.agent_api.app.evaluation.loaders import load_challenge_suite


def test_authoritative_challenge_suite_runs_through_authenticated_deterministic_boundary() -> None:
    source = Path(__file__).resolve().parents[2] / "evaluation" / "challenge" / "scenarios-v1.yaml"
    suite = load_challenge_suite(source)
    results = ChallengeEvaluationRunner(suite).run()
    assert len(results) == 14
    assert tuple(item.scenario_id for item in results) == tuple(item.id for item in suite.suite.scenarios)
    assert all(item.execution_mode.value == "DETERMINISTIC_E2E" for item in results)
    # The runner exposes findings per scenario; Phase 11.4 intentionally has
    # no aggregate threshold or report writer.
    distribution = Counter(item.status.value for item in results)
    print(f"Phase 11.4 deterministic scenario distribution: {dict(distribution)}")
    assert distribution["PASS"] + distribution["FAIL"] == suite.entry_count
