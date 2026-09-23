"""Deterministic Phase 11.2 dataset-contract and adapter tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from apps.agent_api.app.agents.human_escalation import HumanEscalationState
from apps.agent_api.app.agents.router import RouterCapability, RouterRoute, WebSearchPolicy
from apps.agent_api.app.evaluation.adapters import (
    CHALLENGE_014_CLIENT_STATES,
    CHALLENGE_014_OPERATOR_ACCEPTANCE_STATE,
    adapt_challenge_route,
    adapt_challenge_scenario,
    adapt_challenge_014_operator_acceptance,
    adapt_security_expectation,
)
from apps.agent_api.app.evaluation.contracts import EvaluationDatasetContractError, RAGAuditExpectation, RAGDefaults
from apps.agent_api.app.evaluation.loaders import (
    load_challenge_suite,
    load_rag_dataset,
    validate_evaluation_contracts,
)
from apps.agent_api.app.evaluation.source_manifest import (
    DATASET_V11_SOURCE_MANIFEST,
    DATASET_V1_SOURCE_MANIFEST,
    EvaluationSourceManifest,
    EvaluationSourceManifestEntry,
    expected_source_matches,
    normalize_dataset_path,
    all_declared_dataset_paths,
    required_retrieval_dataset_paths,
    validate_manifest_coverage,
)
from apps.agent_api.app.rag.models import RetrievalProvenance


ROOT = Path(__file__).resolve().parents[1]
RAG_PATH = ROOT / "evaluation" / "rag" / "dataset-v1.yaml"
RAG_V11_PATH = ROOT / "evaluation" / "rag" / "dataset-v1.1.yaml"
CHALLENGE_PATH = ROOT / "evaluation" / "challenge" / "scenarios-v1.yaml"


def _provenance(*, document_key: str, source_reference: str) -> RetrievalProvenance:
    return RetrievalProvenance(
        source_id=UUID("00000000-0000-0000-0000-000000000001"),
        source_name="Synthetic source",
        source_type="INTERNAL_DOCUMENT",
        origin="INTERNAL",
        source_reference=source_reference,
        priority=10,
        document_id=UUID("00000000-0000-0000-0000-000000000002"),
        document_key=document_key,
        title="Synthetic document",
        document_type="PDD",
        last_ingested_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_loads_authoritative_v1_datasets_and_retains_challenge_014_turns() -> None:
    rag = load_rag_dataset(RAG_PATH)
    challenge = load_challenge_suite(CHALLENGE_PATH)

    assert rag.version == "1.0"
    assert rag.entry_count == 25
    assert challenge.version == "1.0"
    assert challenge.entry_count == 14
    scenario = next(item for item in challenge.suite.scenarios if item.id == "challenge-014")
    assert tuple(turn.turn for turn in scenario.turns) == (1, 2)


def test_loads_authoritative_v11_claim_insufficient_and_redaction_contracts() -> None:
    rag = load_rag_dataset(RAG_V11_PATH)

    assert rag.version == "1.1"
    assert rag.entry_count == 27
    assert rag.dataset.claim_support_applicability == "explicit_claim_expectations_only"
    assert sum(len(case.claim_expectations) for case in rag.dataset.cases) == 3
    assert sum(case.expected_behavior == "insufficient_evidence" for case in rag.dataset.cases) == 1
    assert sum(bool(case.supplied_secret_fragments) for case in rag.dataset.cases) == 1
    assert len(all_declared_dataset_paths(rag)) == 7
    assert len(required_retrieval_dataset_paths(rag)) == 6
    validate_manifest_coverage(rag, DATASET_V11_SOURCE_MANIFEST)
    validated = validate_evaluation_contracts(
        RAG_V11_PATH, CHALLENGE_PATH, DATASET_V11_SOURCE_MANIFEST
    )
    assert validated.rag.version == "1.1"


def test_v11_contract_rejects_missing_claim_policy_and_wrong_manifest_version(
    tmp_path: Path,
) -> None:
    missing_policy = RAG_V11_PATH.read_text(encoding="utf-8").replace(
        "claim_support_applicability: explicit_claim_expectations_only\n", "", 1
    )
    path = tmp_path / "v11-missing-policy.yaml"
    path.write_text(missing_policy, encoding="utf-8")
    with pytest.raises(EvaluationDatasetContractError):
        load_rag_dataset(path)
    with pytest.raises(EvaluationDatasetContractError):
        validate_manifest_coverage(load_rag_dataset(RAG_V11_PATH), DATASET_V1_SOURCE_MANIFEST)


def test_rag_loader_rejects_malformed_yaml_and_missing_case_id(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.yaml"
    malformed.write_text("cases: [unterminated", encoding="utf-8")
    with pytest.raises(EvaluationDatasetContractError):
        load_rag_dataset(malformed)

    missing_id = tmp_path / "missing-id.yaml"
    missing_id.write_text(
        RAG_PATH.read_text(encoding="utf-8").replace("- id: rag-001\n", "", 1),
        encoding="utf-8",
    )
    with pytest.raises(EvaluationDatasetContractError):
        load_rag_dataset(missing_id)


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ("[not-a-mapping]", "root"),
        ("version: '2.0'\ncases: []\n", "version"),
        ("version: '1.0'\ndataset_name: x\nlanguage: pt\ndescription: x\ndefaults: {}\nacceptance: {}\ncases: []\n", "cases"),
    ],
)
def test_rag_loader_fails_fast_for_invalid_root_version_or_cases(tmp_path: Path, content: str, reason: str) -> None:
    path = tmp_path / "dataset.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(EvaluationDatasetContractError):
        load_rag_dataset(path)


def test_rag_loader_rejects_duplicate_ids_unknown_fields_and_wrong_types(tmp_path: Path) -> None:
    base = RAG_PATH.read_text(encoding="utf-8")
    duplicate = base.replace("- id: rag-002", "- id: rag-001", 1)
    unknown = base.replace("  category: robot-01-remetente", "  unexpected: true\n  category: robot-01-remetente", 1)
    wrong_type = base.replace("  expects_evidence: true", "  expects_evidence: 'true'", 1)
    for name, content in (("duplicate", duplicate), ("unknown", unknown), ("wrong", wrong_type)):
        path = tmp_path / f"{name}.yaml"
        path.write_text(content, encoding="utf-8")
        with pytest.raises(EvaluationDatasetContractError):
            load_rag_dataset(path)


def test_challenge_loader_rejects_duplicate_id_invalid_route_field_and_malformed_turns(tmp_path: Path) -> None:
    base = CHALLENGE_PATH.read_text(encoding="utf-8")
    duplicate = base.replace('- id: "challenge-002"', '- id: "challenge-001"', 1)
    malformed_turn = base.replace("      - turn: 2", "      - turn: 3", 1)
    invalid_route = base.replace('expected_route: "knowledge"', 'expected_route: "unsupported"', 1)
    for name, content in (("duplicate", duplicate), ("turn", malformed_turn), ("route", invalid_route)):
        path = tmp_path / f"{name}.yaml"
        path.write_text(content, encoding="utf-8")
        with pytest.raises(EvaluationDatasetContractError):
            load_challenge_suite(path)


@pytest.mark.parametrize(
    ("concept", "route"),
    [
        ("knowledge", RouterRoute.KNOWLEDGE),
        ("conditional_support", RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT),
        ("support_with_knowledge", RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT),
        ("customer_support", RouterRoute.CUSTOMER_SUPPORT),
        ("cooperative_knowledge_and_support", RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT),
        ("security_block", RouterRoute.SECURITY_BLOCK),
        ("customer_support_to_human_escalation", RouterRoute.CUSTOMER_SUPPORT),
    ],
)
def test_challenge_route_adapter_is_explicit(concept: str, route: RouterRoute) -> None:
    assert adapt_challenge_route(concept).route is route


def test_unmapped_challenge_route_and_historical_security_terms_fail_or_map_explicitly() -> None:
    with pytest.raises(EvaluationDatasetContractError):
        adapt_challenge_route("unknown")
    assert adapt_security_expectation(RAGAuditExpectation(event_type="CREDENTIAL_REQUEST", action_taken="BLOCKED_AND_LOGGED")).acceptable_event_types[0].value == "CREDENTIAL_REQUEST"
    assert {item.value for item in adapt_security_expectation(RAGAuditExpectation(event_type="SENSITIVE_ACCESS_REQUEST", action_taken="BLOCKED_AND_LOGGED")).acceptable_event_types} == {"SENSITIVE_INFRASTRUCTURE_REQUEST", "SECRET_REQUEST", "DATABASE_ACCESS_REQUEST"}


def test_challenge_014_adapter_preserves_waiting_human_before_operator_acceptance() -> None:
    assert CHALLENGE_014_CLIENT_STATES == (
        HumanEscalationState.BOT,
        HumanEscalationState.WAITING_CONFIRMATION,
        HumanEscalationState.WAITING_HUMAN,
    )
    assert CHALLENGE_014_OPERATOR_ACCEPTANCE_STATE is HumanEscalationState.HUMAN
    scenario = next(item for item in load_challenge_suite(CHALLENGE_PATH).suite.scenarios if item.id == "challenge-014")
    expectation = adapt_challenge_scenario(scenario)
    assert expectation.turn_states == (HumanEscalationState.WAITING_CONFIRMATION, HumanEscalationState.WAITING_HUMAN)
    assert expectation.terminal_state is HumanEscalationState.WAITING_HUMAN
    assert expectation.automation_suspended is False
    accepted = adapt_challenge_014_operator_acceptance()
    assert accepted.terminal_state is HumanEscalationState.HUMAN
    assert accepted.automation_suspended is True


@pytest.mark.parametrize(
    ("scenario_id", "route", "capabilities", "web_policy"),
    [
        ("challenge-002", RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK, (RouterCapability.KNOWLEDGE, RouterCapability.WEB_FALLBACK), WebSearchPolicy.REQUIRED),
        ("challenge-007", RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK, (RouterCapability.KNOWLEDGE, RouterCapability.WEB_FALLBACK), WebSearchPolicy.REQUIRED),
        ("challenge-010", RouterRoute.KNOWLEDGE, (RouterCapability.KNOWLEDGE,), WebSearchPolicy.FALLBACK_IF_RAG_INSUFFICIENT),
    ],
)
def test_scenario_adapter_maps_declared_web_semantics(scenario_id, route, capabilities, web_policy) -> None:
    scenario = next(item for item in load_challenge_suite(CHALLENGE_PATH).suite.scenarios if item.id == scenario_id)
    expectation = adapt_challenge_scenario(scenario)
    assert expectation.route is route
    assert expectation.capabilities == capabilities
    assert expectation.web_search_policy is web_policy


def test_scenario_adapter_is_independent_of_scenario_id() -> None:
    suite = load_challenge_suite(CHALLENGE_PATH).suite
    current_info = next(item for item in suite.scenarios if item.id == "challenge-002")
    fallback = next(item for item in suite.scenarios if item.id == "challenge-010")
    current_info_clone = current_info.model_copy(update={"id": "challenge-902"})
    fallback_clone = fallback.model_copy(update={"id": "challenge-910"})
    assert adapt_challenge_scenario(current_info_clone).route is RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK
    assert adapt_challenge_scenario(current_info_clone).web_search_policy is WebSearchPolicy.REQUIRED
    assert adapt_challenge_scenario(fallback_clone).route is RouterRoute.KNOWLEDGE
    assert adapt_challenge_scenario(fallback_clone).web_search_policy is WebSearchPolicy.FALLBACK_IF_RAG_INSUFFICIENT


@pytest.mark.parametrize(
    "mutation",
    [
        lambda item: item.model_copy(update={"freshness_requirement": "required", "expected_capabilities": ()}),
        lambda item: item.model_copy(update={"expected_capabilities": ("web_search",), "freshness_requirement": "stable_or_semi_stable"}),
        lambda item: item.model_copy(update={"rag_requirement": "not_required", "freshness_requirement": "stable_or_semi_stable"}),
        lambda item: item.model_copy(update={"expected_route": "security_block", "expected_capabilities": ("security_guardrail", "redaction"), "tool_class": ("security_audit",), "security_expectation": "block_redact_and_audit"}),
        lambda item: item.model_copy(update={"expected_route": "knowledge", "expected_capabilities": ("security_audit",)}),
        lambda item: item.model_copy(update={"expected_capabilities": ("approved_public_getnet_rag", "web_search_if_rag_insufficient"), "tool_class": ("public_rag",)}),
    ],
)
def test_semantic_adapter_rejects_contradictory_declared_fields(mutation) -> None:
    scenario = next(item for item in load_challenge_suite(CHALLENGE_PATH).suite.scenarios if item.id == "challenge-001")
    with pytest.raises(EvaluationDatasetContractError):
        adapt_challenge_scenario(mutation(scenario))


def test_security_adapter_returns_non_empty_runtime_guardrail_capability() -> None:
    scenario = next(item for item in load_challenge_suite(CHALLENGE_PATH).suite.scenarios if item.id == "challenge-013")
    expectation = adapt_challenge_scenario(scenario)
    assert expectation.capabilities == (RouterCapability.SECURITY_GUARDRAIL,)


@pytest.mark.parametrize(
    ("value", "normalized"),
    [
        ("knowledge/internal/file.md", "knowledge/internal/file.md"),
        ("knowledge\\internal\\file.md", "knowledge/internal/file.md"),
        ("knowledge/internal/./file.md", "knowledge/internal/file.md"),
    ],
)
def test_dataset_path_normalization(value: str, normalized: str) -> None:
    assert normalize_dataset_path(value) == normalized


@pytest.mark.parametrize("value", ("", "/absolute.md", "knowledge/../secret.md", "file.md?x=1", "file.md#part"))
def test_dataset_path_normalization_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(EvaluationDatasetContractError):
        normalize_dataset_path(value)


def test_manifest_enumerates_all_dataset_paths_but_current_evidence_is_incomplete() -> None:
    dataset = load_rag_dataset(RAG_PATH)
    assert len(all_declared_dataset_paths(dataset)) == 7
    assert len(required_retrieval_dataset_paths(dataset)) == 6
    assert "knowledge/internal/security/security-policy.md" not in required_retrieval_dataset_paths(dataset)
    assert len(DATASET_V1_SOURCE_MANIFEST.entries) == 6
    validate_manifest_coverage(dataset, DATASET_V1_SOURCE_MANIFEST)
    validated = validate_evaluation_contracts(RAG_PATH, CHALLENGE_PATH, DATASET_V1_SOURCE_MANIFEST)
    assert validated.rag.entry_count == 25
    assert validated.challenge.entry_count == 14


def test_manifest_rejects_duplicate_or_ambiguous_entries() -> None:
    entry = DATASET_V1_SOURCE_MANIFEST.entries[0]
    with pytest.raises(ValueError):
        EvaluationSourceManifest(dataset_version="2.0", entries=(entry,))
    with pytest.raises(ValueError):
        EvaluationSourceManifest(dataset_version="1.0", entries=(entry, entry))
    with pytest.raises(ValueError):
        EvaluationSourceManifest(
            dataset_version="1.0",
            entries=(entry, EvaluationSourceManifestEntry(dataset_path="knowledge/internal/other.md", document_key=entry.document_key, source_reference=entry.source_reference)),
        )


def test_provenance_matching_is_exact_and_never_uses_title_or_fuzzy_fallback() -> None:
    entry = DATASET_V1_SOURCE_MANIFEST.entries[0]
    assert expected_source_matches(entry.dataset_path, _provenance(document_key=entry.document_key, source_reference=entry.source_reference), DATASET_V1_SOURCE_MANIFEST)
    assert not expected_source_matches(entry.dataset_path, _provenance(document_key="wrong", source_reference=entry.source_reference), DATASET_V1_SOURCE_MANIFEST)
    assert not expected_source_matches(entry.dataset_path, _provenance(document_key=entry.document_key, source_reference="wrong"), DATASET_V1_SOURCE_MANIFEST)
    with pytest.raises(EvaluationDatasetContractError):
        expected_source_matches("knowledge/internal/not-in-manifest.md", _provenance(document_key=entry.document_key, source_reference=entry.source_reference), DATASET_V1_SOURCE_MANIFEST)


def test_strict_defaults_reject_string_coercion_and_unknown_fields() -> None:
    with pytest.raises(ValueError):
        RAGDefaults(final_top_k="5", expected_source_in_top_k=True, require_provenance=True)
    with pytest.raises(ValueError):
        RAGDefaults(final_top_k=5, expected_source_in_top_k=True, require_provenance=True, extra=True)


@pytest.mark.parametrize("path_name", ("does-not-exist.yaml", "a-directory"))
def test_loader_file_failures_are_controlled(tmp_path: Path, path_name: str) -> None:
    path = tmp_path / path_name
    if path_name == "a-directory":
        path.mkdir()
    with pytest.raises(EvaluationDatasetContractError) as error:
        load_rag_dataset(path)
    assert str(error.value) in {"Evaluation dataset could not be read", "Evaluation dataset must be valid UTF-8"}


def test_security_only_cases_are_classified_without_text_heuristics() -> None:
    dataset = load_rag_dataset(RAG_PATH)
    security_cases = [case for case in dataset.dataset.cases if case.expected_behavior == "security_violation_alert"]
    assert security_cases
    assert "knowledge/internal/security/security-policy.md" in {
        path for case in security_cases for path in case.expected_sources
    }
    assert len(required_retrieval_dataset_paths(dataset)) == 6
