"""Strict structured grounded-generation contract and parser coverage."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from apps.agent_api.app.agents.grounded_generation import (
    GroundedGenerationError,
    GroundedGenerationOutcome,
    GroundedGenerationStatus,
    parse_grounded_generation,
    validate_grounded_citations,
)


def outcome(**overrides) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": "1.0",
        "status": "ANSWERED",
        "answer": "Resposta [C1].",
        "citation_ids": ["C1"],
    }
    value.update(overrides)
    return value


def test_contract_accepts_only_valid_answered_and_insufficient_states() -> None:
    answered = GroundedGenerationOutcome.model_validate_json(json.dumps(outcome()))
    insufficient = GroundedGenerationOutcome.model_validate_json(json.dumps({
        "schema_version": "1.0", "status": "INSUFFICIENT_EVIDENCE", "answer": None, "citation_ids": []
    }))
    assert answered.status is GroundedGenerationStatus.ANSWERED
    assert insufficient.status is GroundedGenerationStatus.INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize("changes", [
    {"status": "UNKNOWN"},
    {"schema_version": "2.0"},
    {"schema_version": None},
    {"status": "ANSWERED", "answer": None},
    {"status": "ANSWERED", "citation_ids": []},
    {"status": "INSUFFICIENT_EVIDENCE", "answer": "Unsupported [C1]"},
    {"status": "INSUFFICIENT_EVIDENCE", "citation_ids": ["C1"]},
    {"citation_ids": ["C1", "C1"], "answer": "Repeated [C1]."},
    {"route": "WEB"},
    {"confidence": 0.99},
    {"tool": "search"},
])
def test_contract_rejects_invalid_or_authoritative_extra_fields(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        GroundedGenerationOutcome.model_validate_json(json.dumps(outcome(**changes)))


def test_parser_accepts_raw_json_and_rejects_non_json_and_duplicate_keys() -> None:
    good = json.dumps(outcome())
    assert parse_grounded_generation(good).answer == "Resposta [C1]."
    invalid = (
        "A resposta é {\"status\":\"ANSWERED\"}",
        f"```json\n{good}\n```",
        "{bad json}",
        '{"schema_version":"1.0","schema_version":"1.0","status":"ANSWERED","answer":"x [C1]","citation_ids":["C1"]}',
        "",
    )
    for content in invalid:
        with pytest.raises(GroundedGenerationError):
            parse_grounded_generation(content)


def test_citation_subset_and_inline_consistency_are_enforced() -> None:
    valid = GroundedGenerationOutcome.model_validate_json(json.dumps(outcome(
        answer="A [C1] e B [C3].", citation_ids=["C1", "C3"]
    )))
    validate_grounded_citations(valid, ("C1", "C2", "C3"))
    invalid_outputs = (
        outcome(answer="A [C1] e B [C9].", citation_ids=["C1", "C9"]),
        outcome(answer="A [C1].", citation_ids=["C1", "C2"]),
        outcome(answer="Sem marcador.", citation_ids=["C1"]),
    )
    for data in invalid_outputs:
        parsed = GroundedGenerationOutcome.model_validate_json(json.dumps(data))
        with pytest.raises(GroundedGenerationError):
            validate_grounded_citations(parsed, ("C1", "C2", "C3"))


def test_insufficient_state_is_structural_and_answer_words_do_not_change_status() -> None:
    insufficient = parse_grounded_generation(
        '{"schema_version":"1.0","status":"INSUFFICIENT_EVIDENCE","answer":null,"citation_ids":[]}'
    )
    answered_unknown = parse_grounded_generation(
        '{"schema_version":"1.0","status":"ANSWERED","answer":"An unknown outcome was recorded [C1].","citation_ids":["C1"]}'
    )
    assert insufficient.status is GroundedGenerationStatus.INSUFFICIENT_EVIDENCE
    assert answered_unknown.status is GroundedGenerationStatus.ANSWERED
