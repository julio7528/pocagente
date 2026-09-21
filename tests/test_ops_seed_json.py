"""Focused validation for the JSON-driven OPS seed contract and loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from database.seed.ops.loader import get_scenario, load_scenarios


SCENARIOS = Path("database/seed/ops/scenarios")


def _payload(name: str) -> dict[str, object]:
    return json.loads((SCENARIOS / name).read_text(encoding="utf-8"))


def test_discovery_is_deterministic_and_cases_have_approved_definitions() -> None:
    scenarios = load_scenarios()

    assert [scenario.scenario_id for scenario in scenarios] == [
        "caso_001_sucesso",
        "caso_002_erro_download_r2",
        "caso_003_erro_upload_r1",
        "caso_004_erro_verificacao_download_r2",
        "caso_005_portal_indisponivel_download_r2",
    ]
    case_001, case_002, case_003, case_004, case_005 = scenarios
    assert case_001.protocol_number == "POC-OPS-0001"
    assert len(case_001.r1.events) == 10
    assert len(case_001.r2.events) == 6
    assert case_001.r2.status == "SUCCESS"
    assert case_002.protocol_number == "POC-OPS-0002"
    assert case_002.r1.started_at.isoformat() == "2026-09-03T09:00:00-04:00"
    assert case_002.r2.started_at.isoformat() == "2026-09-04T09:00:00-04:00"
    assert len(case_002.r1.events) == 10
    assert len(case_002.r2.events) == 5
    assert case_002.r2.status == "ERROR"
    assert case_002.request.final_status == "FAILED"
    assert case_002.request.failure_reason
    assert case_002.establishment.final_download_status == "ERROR"
    assert case_002.establishment.final_processing_status == "ERROR"
    assert case_002.establishment.download_at is None
    assert case_002.establishment.return_email_at is None
    assert case_002.request.completed_at is None
    assert case_002.request.return_email_at is None
    assert [event.status for event in case_002.r2.events[-2:]] == ["ERROR", "ERROR"]
    assert case_003.r2 is None
    assert case_003.r1.status == "ERROR"
    assert len(case_003.r1.events) == 11
    assert case_003.request.r1_status == "FAILED"
    assert case_003.establishment.r1_processing_status == "ERROR"
    assert case_003.establishment.r1_upload_status == "ERROR"
    assert case_003.establishment.r1_upload_at is None
    assert case_003.establishment.available_at is None
    assert case_003.establishment.available_processing_status is None
    assert case_003.establishment.available_download_status is None
    assert case_004.r2 is not None
    assert case_004.r2.status == "ERROR"
    assert len(case_004.r2.events) == 8
    assert case_004.establishment.final_processing_status == "ERROR"
    assert case_004.establishment.final_download_status == "DOWNLOADED"
    assert case_004.establishment.download_at is not None
    assert case_004.request.final_status == "FAILED"
    assert case_004.request.failure_reason
    assert case_004.request.return_email_at is not None
    assert case_005.scenario_id == "caso_005_portal_indisponivel_download_r2"
    assert all(event.timestamp.tzinfo is not None for event in (*case_001.r1.events, *case_001.r2.events, *case_002.r1.events, *case_002.r2.events, *case_005.r1.events, *case_005.r2.events))


def test_targeted_selection_and_unknown_scenario() -> None:
    scenarios = load_scenarios()
    assert get_scenario("caso_002_erro_download_r2", scenarios).protocol_number == "POC-OPS-0002"
    assert get_scenario("caso_003_erro_upload_r1", scenarios).r2 is None
    with pytest.raises(ValueError, match="Unknown OPS seed scenario"):
        get_scenario("missing", scenarios)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data.pop("scenario_id"), "Invalid OPS seed scenario"),
        (lambda data: data["r2"].__setitem__("started_at", "2026-09-04T09:00:00"), "Invalid OPS seed scenario"),
        (lambda data: data["r2"].__setitem__("status", "BROKEN"), "Invalid OPS seed scenario"),
        (lambda data: data["r2"].__setitem__("events", data["r2"]["events"][:3]), "Invalid OPS seed scenario"),
    ],
)
def test_loader_rejects_invalid_json_contract(tmp_path: Path, mutation, message: str) -> None:
    data = _payload("caso_002_erro_download_r2.json")
    mutation(data)
    (tmp_path / "invalid.json").write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_scenarios(tmp_path)


def test_loader_rejects_malformed_and_duplicate_definitions(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed OPS seed JSON"):
        load_scenarios(tmp_path)

    (tmp_path / "broken.json").unlink()

    first = _payload("caso_001_sucesso.json")
    second = _payload("caso_001_sucesso.json")
    second["scenario_id"] = "different_id"
    (tmp_path / "a.json").write_text(json.dumps(first), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps(second), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate OPS seed protocol"):
        load_scenarios(tmp_path)


def test_empty_directory_is_a_valid_empty_discovery_result(tmp_path: Path) -> None:
    assert load_scenarios(tmp_path) == ()
