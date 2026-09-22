"""Secret-safe deterministic JSON reporting for Phase 11.5."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from .challenge_results import ChallengeScenarioResult
from .contracts import EvaluationDatasetContractError, LoadedChallengeSuite, LoadedRAGDataset
from .metrics import MetricOutcome, calculate_metrics, overall_outcome, validate_challenge_result_alignment, validate_rag_result_alignment
from .rag_results import RAGCaseResult
from .report_results import (
    ChallengeCaseEvidence,
    ClassCount,
    OverallEvaluationOutcome,
    Phase11EvaluationReport,
    RAGCaseEvidence,
    ReportMetadata,
    StatusCount,
)


def _counts(values: tuple[str, ...]) -> tuple[StatusCount, ...]:
    return tuple(StatusCount(status=value, count=values.count(value)) for value in dict.fromkeys(values))


def _class_counts(values: tuple[str, ...]) -> tuple[ClassCount, ...]:
    return tuple(ClassCount(case_class=value, count=values.count(value)) for value in dict.fromkeys(values))


def _rag_evidence(result: RAGCaseResult) -> RAGCaseEvidence:
    retrieval = result.retrieval
    security = result.security
    return RAGCaseEvidence(
        case_id=result.case_id,
        case_class=result.case_class.value,
        status=result.status,
        reason=result.reason,
        expected_source_found=retrieval.expected_source_found if retrieval else None,
        retrieval_status=retrieval.retrieval_status.value if retrieval else None,
        provenance_status=retrieval.provenance_status.value if retrieval else None,
        grounding_status=retrieval.grounding_status.value if retrieval else None,
        semantic_status=retrieval.semantic_status.value if retrieval else None,
        security_blocked=security.blocked if security else None,
        audit_observed=bool(security and security.event_types and security.audit_actions) if security else None,
        redaction_status=security.redaction.status.value if security else None,
        evaluated_claim_count=result.claim_support.evaluated_claim_count,
        unsupported_claim_count=result.claim_support.unsupported_claim_count,
        unsupported_fact_status=result.unsupported_fact_status.value,
        insufficient_evidence_status=result.insufficient_evidence_status.value,
    )


def _challenge_evidence(result: ChallengeScenarioResult) -> ChallengeCaseEvidence:
    return ChallengeCaseEvidence(
        scenario_id=result.scenario_id,
        status=result.status,
        reason=result.reason,
        expected_route=result.expected_route,
        observed_route=result.observed_route,
        authorization_applicable=result.authorization.applicable,
        authorization_respected=result.authorization.respected,
        expected_tools_satisfied=result.tools.expected_tools_satisfied,
        unexpected_tools_absent=result.tools.unexpected_tools_absent,
        forbidden_capabilities_respected=result.forbidden.respected,
        security_blocked=result.security.blocked if result.security else None,
        human_states=result.human.states if result.human else (),
    )


def build_phase11_report(
    dataset: LoadedRAGDataset,
    rag_results: tuple[RAGCaseResult, ...],
    suite: LoadedChallengeSuite,
    challenge_results: tuple[ChallengeScenarioResult, ...],
    *,
    metadata: ReportMetadata | None = None,
) -> Phase11EvaluationReport:
    """Build a report from already executed typed results only."""

    validate_rag_result_alignment(dataset, rag_results)
    validate_challenge_result_alignment(suite, challenge_results)
    metrics = calculate_metrics(dataset, rag_results, suite, challenge_results)
    outcome, reason = overall_outcome(metrics)
    return Phase11EvaluationReport(
        metadata=metadata or ReportMetadata(),
        rag_dataset_name=dataset.dataset.dataset_name,
        rag_dataset_version=dataset.version,
        challenge_suite_name=suite.suite.suite_name,
        challenge_suite_version=suite.version,
        rag_runner_version=rag_results[0].runner_version,
        challenge_runner_version=challenge_results[0].runner_version,
        rag_execution_mode=rag_results[0].execution_mode,
        challenge_execution_mode=challenge_results[0].execution_mode,
        rag_case_count=len(rag_results),
        challenge_scenario_count=len(challenge_results),
        rag_status_counts=_counts(tuple(result.status.value for result in rag_results)),
        rag_class_counts=_class_counts(tuple(result.case_class.value for result in rag_results)),
        challenge_status_counts=_counts(tuple(result.status.value for result in challenge_results)),
        metrics=metrics,
        rag_cases=tuple(_rag_evidence(result) for result in rag_results),
        challenge_cases=tuple(_challenge_evidence(result) for result in challenge_results),
        overall_outcome=(
            OverallEvaluationOutcome.INCOMPLETE_NOT_MEASURABLE
            if outcome is MetricOutcome.NOT_MEASURABLE
            else OverallEvaluationOutcome(outcome.value)
        ),
        overall_reason=reason,
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        # Comparisons are completed with Decimal before serialization. JSON
        # has no Decimal primitive, so the bounded report emits a stable JSON
        # number while retaining exact arithmetic in MetricResult.
        return float(value)
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def serialize_report(report: Phase11EvaluationReport) -> str:
    """Serialize only the bounded report model in stable UTF-8 JSON form."""

    data = _json_safe(report.model_dump(mode="python"))
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def write_report(report: Phase11EvaluationReport, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(serialize_report(report), encoding="utf-8", newline="\n")


def load_serialized_report(text: str) -> dict[str, Any]:
    """Parse a report artifact without rehydrating untrusted execution objects."""

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as error:
        raise EvaluationDatasetContractError("Evaluation report JSON is invalid") from error
    if not isinstance(parsed, dict):
        raise EvaluationDatasetContractError("Evaluation report root must be an object")
    return parsed
