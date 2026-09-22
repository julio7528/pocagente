"""Safe, strict loaders for the versioned Phase 11 YAML inputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from .contracts import (
    ChallengeEvaluationSuite,
    EvaluationDatasetContractError,
    LoadedChallengeSuite,
    LoadedRAGDataset,
    RAGEvaluationDataset,
)
from .adapters import adapt_challenge_scenario, adapt_security_expectation, classify_rag_case, RAGEvaluationClass
from .source_manifest import EvaluationSourceManifest, validate_manifest_coverage


class ValidatedEvaluationContracts(BaseModel):
    """Narrow future-runner input after both suite contracts have validated."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rag: LoadedRAGDataset
    challenge: LoadedChallengeSuite


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError) as error:
        raise EvaluationDatasetContractError("Evaluation dataset could not be read") from error
    except UnicodeDecodeError as error:
        raise EvaluationDatasetContractError("Evaluation dataset must be valid UTF-8") from error
    except yaml.YAMLError as error:
        raise EvaluationDatasetContractError("Malformed evaluation YAML") from error
    if not isinstance(raw, dict):
        raise EvaluationDatasetContractError("Evaluation dataset root must be a mapping")
    return raw


def load_rag_dataset(path: Path) -> LoadedRAGDataset:
    try:
        dataset = RAGEvaluationDataset.model_validate(_load_mapping(path))
    except ValidationError as error:
        raise EvaluationDatasetContractError("Invalid RAG evaluation dataset") from error
    return LoadedRAGDataset(source_path=path, dataset=dataset)


def load_challenge_suite(path: Path) -> LoadedChallengeSuite:
    try:
        suite = ChallengeEvaluationSuite.model_validate(_load_mapping(path))
    except ValidationError as error:
        raise EvaluationDatasetContractError("Invalid challenge evaluation suite") from error
    return LoadedChallengeSuite(source_path=path, suite=suite)


def validate_evaluation_contracts(
    rag_path: Path,
    challenge_path: Path,
    manifest: EvaluationSourceManifest,
) -> ValidatedEvaluationContracts:
    """Fail fast before a future runner can execute either dataset."""

    rag = load_rag_dataset(rag_path)
    challenge = load_challenge_suite(challenge_path)
    _validate_semantics(rag, challenge)
    validate_manifest_coverage(rag, manifest)
    return ValidatedEvaluationContracts(rag=rag, challenge=challenge)


def _validate_semantics(rag: LoadedRAGDataset, challenge: LoadedChallengeSuite) -> None:
    for case in rag.dataset.cases:
        classification = classify_rag_case(case)
        if classification is RAGEvaluationClass.SECURITY:
            if case.expected_audit_event is None:
                raise EvaluationDatasetContractError("Security RAG cases must declare an audit expectation")
            adapt_security_expectation(case.expected_audit_event)
        elif case.expected_audit_event is not None:
            raise EvaluationDatasetContractError("Only security RAG cases may declare an audit expectation")

    for scenario in challenge.suite.scenarios:
        expectation = adapt_challenge_scenario(scenario)
        if scenario.freshness_requirement == "required" and expectation.web_search_policy.value != "REQUIRED":
            raise EvaluationDatasetContractError("Freshness-required challenge scenarios must require Web Search")
