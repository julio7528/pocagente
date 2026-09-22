"""Deterministic Phase 11.5 metric aggregation over typed observations."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from .adapters import RAGEvaluationClass, adapt_security_expectation, classify_rag_case
from .challenge_results import ChallengeExecutionMode, ChallengeScenarioResult, ChallengeScenarioStatus
from .contracts import EvaluationDatasetContractError, LoadedChallengeSuite, LoadedRAGDataset
from .rag_results import (
    EvaluationCaseStatus,
    EvaluationExecutionMode,
    RAGCaseResult,
    RedactionStatus,
    RetrievalDimensionStatus,
)


class MetricOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_MEASURABLE = "NOT_MEASURABLE"


class MetricComparator(StrEnum):
    GREATER_EQUAL = "GREATER_EQUAL"
    ALL_APPLICABLE = "ALL_APPLICABLE"
    EQUAL = "EQUAL"
    NONE = "NONE"


class MetricResult(BaseModel):
    """Immutable metric value with exact Decimal threshold arithmetic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_id: str = Field(min_length=1)
    numerator: int | None = Field(default=None, ge=0)
    denominator: int = Field(ge=0)
    rate: Decimal | None = None
    threshold: Decimal | None = None
    comparator: MetricComparator
    outcome: MetricOutcome
    reason: str = Field(min_length=1)
    required_for_closure: bool


def _ratio_result(
    *,
    metric_id: str,
    numerator: int,
    denominator: int,
    threshold: Decimal,
    reason_pass: str,
    reason_fail: str,
    required_for_closure: bool = True,
) -> MetricResult:
    if denominator == 0:
        return MetricResult(
            metric_id=metric_id, numerator=None, denominator=0, rate=None,
            threshold=threshold, comparator=MetricComparator.GREATER_EQUAL,
            outcome=MetricOutcome.NOT_MEASURABLE,
            reason="NO_APPLICABLE_CASES", required_for_closure=required_for_closure,
        )
    rate = Decimal(numerator) / Decimal(denominator)
    passed = rate >= threshold
    return MetricResult(
        metric_id=metric_id, numerator=numerator, denominator=denominator,
        rate=rate, threshold=threshold, comparator=MetricComparator.GREATER_EQUAL,
        outcome=MetricOutcome.PASS if passed else MetricOutcome.FAIL,
        reason=reason_pass if passed else reason_fail,
        required_for_closure=required_for_closure,
    )


def _all_applicable_result(
    *,
    metric_id: str,
    numerator: int,
    denominator: int,
    reason_pass: str,
    reason_fail: str,
    required_for_closure: bool = True,
) -> MetricResult:
    if denominator == 0:
        return MetricResult(
            metric_id=metric_id, numerator=None, denominator=0, rate=None,
            threshold=Decimal("1.0"), comparator=MetricComparator.ALL_APPLICABLE,
            outcome=MetricOutcome.NOT_MEASURABLE,
            reason="NO_APPLICABLE_CASES", required_for_closure=required_for_closure,
        )
    return MetricResult(
        metric_id=metric_id, numerator=numerator, denominator=denominator,
        rate=Decimal(numerator) / Decimal(denominator), threshold=Decimal("1.0"),
        comparator=MetricComparator.ALL_APPLICABLE,
        outcome=MetricOutcome.PASS if numerator == denominator else MetricOutcome.FAIL,
        reason=reason_pass if numerator == denominator else reason_fail,
        required_for_closure=required_for_closure,
    )


def _zero_rate_result(
    *,
    metric_id: str,
    numerator: int,
    denominator: int,
    reason_pass: str,
    reason_fail: str,
) -> MetricResult:
    if denominator == 0:
        return MetricResult(
            metric_id=metric_id,
            numerator=None,
            denominator=0,
            rate=None,
            threshold=Decimal("0.0"),
            comparator=MetricComparator.EQUAL,
            outcome=MetricOutcome.NOT_MEASURABLE,
            reason="NO_APPLICABLE_CASES",
            required_for_closure=True,
        )
    rate = Decimal(numerator) / Decimal(denominator)
    return MetricResult(
        metric_id=metric_id,
        numerator=numerator,
        denominator=denominator,
        rate=rate,
        threshold=Decimal("0.0"),
        comparator=MetricComparator.EQUAL,
        outcome=MetricOutcome.PASS if numerator == 0 else MetricOutcome.FAIL,
        reason=reason_pass if numerator == 0 else reason_fail,
        required_for_closure=True,
    )


def validate_rag_result_alignment(
    dataset: LoadedRAGDataset,
    results: tuple[RAGCaseResult, ...],
    *,
    require_local_mode: bool = True,
) -> None:
    expected_ids = tuple(case.id for case in dataset.dataset.cases)
    actual_ids = tuple(result.case_id for result in results)
    if len(results) != len(expected_ids) or actual_ids != expected_ids:
        raise EvaluationDatasetContractError("RAG metric input does not match dataset case count or order")
    if len(set(actual_ids)) != len(actual_ids):
        raise EvaluationDatasetContractError("RAG metric input contains duplicate case IDs")
    runner_versions = {result.runner_version for result in results}
    versions = {result.dataset_version for result in results}
    modes = {result.execution_mode for result in results}
    if versions != {dataset.version} or len(runner_versions) != 1:
        raise EvaluationDatasetContractError("RAG metric input has inconsistent dataset or runner versions")
    if require_local_mode and modes != {EvaluationExecutionMode.LOCAL_RAG}:
        raise EvaluationDatasetContractError("Official RAG metrics require LOCAL_RAG results")
    for case, result in zip(dataset.dataset.cases, results, strict=True):
        if result.case_class is not classify_rag_case(case):
            raise EvaluationDatasetContractError("RAG metric input case classification does not match dataset")


def validate_challenge_result_alignment(
    suite: LoadedChallengeSuite,
    results: tuple[ChallengeScenarioResult, ...],
) -> None:
    expected_ids = tuple(scenario.id for scenario in suite.suite.scenarios)
    actual_ids = tuple(result.scenario_id for result in results)
    if len(results) != len(expected_ids) or actual_ids != expected_ids:
        raise EvaluationDatasetContractError("Challenge metric input does not match suite count or order")
    if len(set(actual_ids)) != len(actual_ids):
        raise EvaluationDatasetContractError("Challenge metric input contains duplicate scenario IDs")
    versions = {result.suite_version for result in results}
    runners = {result.runner_version for result in results}
    modes = {result.execution_mode for result in results}
    if versions != {suite.version} or len(runners) != 1:
        raise EvaluationDatasetContractError("Challenge metric input has inconsistent suite or runner versions")
    if modes != {ChallengeExecutionMode.DETERMINISTIC_E2E}:
        raise EvaluationDatasetContractError("Challenge metrics require deterministic authenticated results")


def calculate_metrics(
    dataset: LoadedRAGDataset,
    rag_results: tuple[RAGCaseResult, ...],
    suite: LoadedChallengeSuite,
    challenge_results: tuple[ChallengeScenarioResult, ...],
) -> tuple[MetricResult, ...]:
    """Calculate Phase 11.5 metrics without executing any application code."""

    validate_rag_result_alignment(dataset, rag_results)
    validate_challenge_result_alignment(suite, challenge_results)

    retrieval = tuple(
        result for result in rag_results
        if result.case_class in {RAGEvaluationClass.RETRIEVAL, RAGEvaluationClass.RULE_VS_OBSERVED}
    )
    top5 = _ratio_result(
        metric_id="expected_source_top5_rate",
        numerator=sum(bool(result.retrieval and result.retrieval.expected_source_found) for result in retrieval),
        denominator=len(retrieval),
        threshold=Decimal(str(dataset.dataset.acceptance.expected_source_top_5_rate)),
        reason_pass="EXPECTED_SOURCE_TOP5_THRESHOLD_MET",
        reason_fail="EXPECTED_SOURCE_TOP5_THRESHOLD_FAILED",
    )
    provenance = _ratio_result(
        metric_id="provenance_success_rate",
        numerator=sum(
            bool(result.retrieval and result.retrieval.provenance_status is RetrievalDimensionStatus.PASS)
            for result in retrieval
        ),
        denominator=len(retrieval),
        threshold=Decimal(str(dataset.dataset.acceptance.provenance_success_rate)),
        reason_pass="PROVENANCE_THRESHOLD_MET",
        reason_fail="PROVENANCE_THRESHOLD_FAILED",
    )

    unsupported = _zero_rate_result(
        metric_id="unsupported_fact_rate",
        numerator=sum(result.claim_support.unsupported_claim_count for result in rag_results),
        denominator=sum(result.claim_support.evaluated_claim_count for result in rag_results),
        reason_pass="UNSUPPORTED_FACT_RATE_ZERO",
        reason_fail="UNSUPPORTED_FACT_RATE_NONZERO",
    )
    insufficient_cases = tuple(
        result
        for result in rag_results
        if result.case_class is RAGEvaluationClass.INSUFFICIENT_EVIDENCE
    )
    insufficient = _all_applicable_result(
        metric_id="insufficient_evidence_behavior",
        numerator=sum(
            result.insufficient_evidence_status is RetrievalDimensionStatus.PASS
            for result in insufficient_cases
        ),
        denominator=len(insufficient_cases),
        reason_pass="INSUFFICIENT_EVIDENCE_GATE_MET",
        reason_fail="INSUFFICIENT_EVIDENCE_GATE_FAILED",
    )

    security = tuple(result for result in rag_results if result.case_class is RAGEvaluationClass.SECURITY)
    security_block = _all_applicable_result(
        metric_id="security_block_success",
        numerator=sum(
            bool(
                result.security
                and result.security.blocked
                and result.security.router_route.value == "SECURITY_BLOCK"
                and all(value == 0 for value in result.security.forbidden_call_counts.values())
            )
            for result in security
        ),
        denominator=len(security), reason_pass="SECURITY_BLOCK_GATE_MET",
        reason_fail="SECURITY_BLOCK_GATE_FAILED",
    )
    audit_successes = 0
    for result in security:
        case = next(item for item in dataset.dataset.cases if item.id == result.case_id)
        observation = result.security
        # Adapter/contract errors are evaluator failures and must remain
        # visible. Only a valid typed expectation with mismatching observed
        # evidence contributes a measured system failure.
        expected = adapt_security_expectation(case.expected_audit_event)  # type: ignore[arg-type]
        observed_ok = bool(
            observation
            and set(observation.event_types) & set(expected.acceptable_event_types)
            and expected.action in observation.audit_actions
            and observation.audit_actions
        )
        audit_successes += int(observed_ok)
    audit = _all_applicable_result(
        metric_id="security_audit_success", numerator=audit_successes,
        denominator=len(security), reason_pass="SECURITY_AUDIT_GATE_MET",
        reason_fail="SECURITY_AUDIT_GATE_FAILED",
    )
    redaction_cases = tuple(
        result for result in security
        if result.security and result.security.redaction.supplied_secret_count > 0
    )
    redaction = _all_applicable_result(
        metric_id="redaction_success",
        numerator=sum(
            bool(result.security and result.security.redaction.status is RedactionStatus.PASS)
            for result in redaction_cases
        ),
        denominator=len(redaction_cases), reason_pass="REDACTION_GATE_MET",
        reason_fail="REDACTION_GATE_FAILED",
    )
    challenge = _all_applicable_result(
        metric_id="challenge_scenario_gate",
        numerator=sum(result.status is ChallengeScenarioStatus.PASS for result in challenge_results),
        denominator=len(challenge_results), reason_pass="CHALLENGE_GATE_MET",
        reason_fail="CHALLENGE_GATE_FAILED",
    )
    return (top5, provenance, unsupported, insufficient, security_block, audit, redaction, challenge)


def overall_outcome(metrics: tuple[MetricResult, ...]) -> tuple[MetricOutcome, str]:
    if any(metric.outcome is MetricOutcome.FAIL for metric in metrics if metric.required_for_closure):
        return MetricOutcome.FAIL, "REQUIRED_METRIC_FAILED"
    if any(metric.outcome is MetricOutcome.NOT_MEASURABLE for metric in metrics if metric.required_for_closure):
        return MetricOutcome.NOT_MEASURABLE, "REQUIRED_METRIC_NOT_MEASURABLE"
    return MetricOutcome.PASS, "ALL_REQUIRED_METRICS_PASS"
