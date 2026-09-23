"""Deterministic Phase 11.5 metric and report contract tests."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from apps.agent_api.app.agents.router import RouterRoute
from apps.agent_api.app.evaluation.adapters import RAGEvaluationClass, classify_rag_case
from apps.agent_api.app.evaluation.challenge_runner import ChallengeEvaluationRunner
from apps.agent_api.app.evaluation.challenge_results import ChallengeScenarioStatus
from apps.agent_api.app.evaluation.contracts import EvaluationDatasetContractError
from apps.agent_api.app.evaluation.loaders import load_challenge_suite, load_rag_dataset
from apps.agent_api.app.evaluation.metrics import (
    MetricComparator,
    MetricOutcome,
    MetricResult,
    _ratio_result,
    calculate_metrics,
    overall_outcome,
)
from apps.agent_api.app.evaluation.rag_results import (
    ClaimSupportObservation,
    ClaimSupportStatus,
    EvaluatedClaimObservation,
    EvaluationCaseStatus,
    EvaluationExecutionMode,
    RAGCaseResult,
    RedactionObservation,
    RedactionStatus,
    RetrievalDimensionStatus,
    RetrievalObservation,
    SecurityObservation,
)
from apps.agent_api.app.evaluation.reporting import (
    build_phase11_report,
    load_serialized_report,
    serialize_report,
)
from apps.agent_api.app.security.models import SecurityAction, SecurityEventType
from apps.agent_api.app.rag.grounding.context_builder import EvidenceStatus


ROOT = Path(__file__).resolve().parents[1]
RAG_PATH = ROOT / "evaluation" / "rag" / "dataset-v1.yaml"
RAG_V11_PATH = ROOT / "evaluation" / "rag" / "dataset-v1.1.yaml"
CHALLENGE_PATH = ROOT / "evaluation" / "challenge" / "scenarios-v1.yaml"


def _synthetic_rag_results(dataset):
    results = []
    for case in dataset.dataset.cases:
        case_class = classify_rag_case(case)
        if case_class is RAGEvaluationClass.SECURITY:
            supplied_count = len(case.supplied_secret_fragments)
            results.append(RAGCaseResult(
                case_id=case.id, dataset_version=dataset.version,
                execution_mode=EvaluationExecutionMode.LOCAL_RAG,
                case_class=case_class, status=EvaluationCaseStatus.FAIL,
                security=SecurityObservation(
                    blocked=False, router_route=RouterRoute.KNOWLEDGE,
                    event_types=(), audit_actions=(), forbidden_call_counts={"retrieval": 0},
                    redaction=RedactionObservation(
                        status=(RedactionStatus.PASS if supplied_count else RedactionStatus.NOT_APPLICABLE),
                        sanitization_invoked=bool(supplied_count), supplied_secret_count=supplied_count,
                    ),
                ),
            ))
            continue
        if case_class is RAGEvaluationClass.INSUFFICIENT_EVIDENCE:
            results.append(RAGCaseResult(
                case_id=case.id,
                dataset_version=dataset.version,
                execution_mode=EvaluationExecutionMode.LOCAL_RAG,
                case_class=case_class,
                status=EvaluationCaseStatus.PASS,
                retrieval=RetrievalObservation(
                    result_count=1,
                    final_rank=(1,),
                    results=(),
                    expected_source_found=False,
                    evidence_status=EvidenceStatus.INSUFFICIENT_EVIDENCE,
                    evidence_reason="NO_APPROVED_EVIDENCE",
                    evidence_count=0,
                    citation_count=0,
                    retrieval_status=RetrievalDimensionStatus.PASS,
                    provenance_status=RetrievalDimensionStatus.PASS,
                    grounding_status=RetrievalDimensionStatus.PASS,
                    semantic_status=RetrievalDimensionStatus.NOT_APPLICABLE,
                ),
                insufficient_evidence_status=RetrievalDimensionStatus.PASS,
            ))
            continue
        retrieval = RetrievalObservation(
            result_count=1, final_rank=(1,), results=(), expected_source_found=True,
            evidence_status=EvidenceStatus.SUFFICIENT_CONTEXT, evidence_reason="synthetic",
            evidence_count=1, citation_count=1,
            retrieval_status=RetrievalDimensionStatus.PASS,
            provenance_status=RetrievalDimensionStatus.PASS,
            grounding_status=RetrievalDimensionStatus.PASS,
            semantic_status=(
                RetrievalDimensionStatus.NOT_MEASURABLE
                if case_class is RAGEvaluationClass.RULE_VS_OBSERVED
                else RetrievalDimensionStatus.NOT_APPLICABLE
            ),
        )
        claims = tuple(
            EvaluatedClaimObservation(
                claim_id=expectation.claim_id,
                expected_value=expectation.expected_value,
                status=ClaimSupportStatus.PASS,
            )
            for expectation in case.claim_expectations
        )
        results.append(RAGCaseResult(
            case_id=case.id, dataset_version=dataset.version,
            execution_mode=EvaluationExecutionMode.LOCAL_RAG,
            case_class=case_class,
            status=(EvaluationCaseStatus.NOT_MEASURABLE
                    if case_class is RAGEvaluationClass.RULE_VS_OBSERVED
                    else EvaluationCaseStatus.PASS),
            retrieval=retrieval,
            claim_support=ClaimSupportObservation(
                applicable=bool(claims),
                evaluated_claim_count=len(claims),
                unsupported_claim_count=0,
                claims=claims,
            ),
            unsupported_fact_status=(
                RetrievalDimensionStatus.PASS
                if claims
                else RetrievalDimensionStatus.NOT_MEASURABLE
            ),
        ))
    return tuple(results)


@pytest.fixture()
def inputs():
    return load_rag_dataset(RAG_PATH), load_challenge_suite(CHALLENGE_PATH)


def test_exact_decimal_rate_boundary_and_empty_denominator() -> None:
    met = _ratio_result(
        metric_id="test", numerator=9, denominator=10, threshold=Decimal("0.90"),
        reason_pass="ok", reason_fail="bad",
    )
    failed = _ratio_result(
        metric_id="test", numerator=8, denominator=10, threshold=Decimal("0.90"),
        reason_pass="ok", reason_fail="bad",
    )
    empty = _ratio_result(
        metric_id="test", numerator=0, denominator=0, threshold=Decimal("0.90"),
        reason_pass="ok", reason_fail="bad",
    )
    assert met.rate == Decimal("0.9") and met.outcome is MetricOutcome.PASS
    assert failed.rate == Decimal("0.8") and failed.outcome is MetricOutcome.FAIL
    assert empty.numerator is None and empty.rate is None and empty.outcome is MetricOutcome.NOT_MEASURABLE


def test_alignment_rejects_missing_duplicate_order_version_and_contract_mode(inputs) -> None:
    dataset, suite = inputs
    rag = _synthetic_rag_results(dataset)
    challenge = ChallengeEvaluationRunner(suite).run()
    with pytest.raises(EvaluationDatasetContractError):
        calculate_metrics(dataset, rag[:-1], suite, challenge)
    with pytest.raises(EvaluationDatasetContractError):
        calculate_metrics(dataset, rag[:-1] + (rag[0],), suite, challenge)
    with pytest.raises(EvaluationDatasetContractError):
        calculate_metrics(dataset, (rag[1], rag[0], *rag[2:]), suite, challenge)
    with pytest.raises(EvaluationDatasetContractError):
        calculate_metrics(dataset, (rag[0].model_copy(update={"dataset_version": "2.0"}), *rag[1:]), suite, challenge)
    with pytest.raises(EvaluationDatasetContractError):
        calculate_metrics(dataset, (rag[0].model_copy(update={"execution_mode": EvaluationExecutionMode.RUNNER_CONTRACT}), *rag[1:]), suite, challenge)
    with pytest.raises(EvaluationDatasetContractError):
        calculate_metrics(dataset, rag, suite, challenge[:-1])


def test_metrics_exclude_security_and_include_rule_vs_observed(inputs) -> None:
    dataset, suite = inputs
    rag = _synthetic_rag_results(dataset)
    metrics = calculate_metrics(dataset, rag, suite, ChallengeEvaluationRunner(suite).run())
    by_id = {metric.metric_id: metric for metric in metrics}
    assert by_id["expected_source_top5_rate"].denominator == 23
    assert by_id["provenance_success_rate"].denominator == 23
    assert by_id["security_block_success"].denominator == 2
    assert by_id["unsupported_fact_rate"].outcome is MetricOutcome.NOT_MEASURABLE
    assert by_id["insufficient_evidence_behavior"].denominator == 0
    assert by_id["redaction_success"].denominator == 0


def test_v11_metrics_make_claim_insufficient_and_redaction_dimensions_measurable() -> None:
    dataset = load_rag_dataset(RAG_V11_PATH)
    suite = load_challenge_suite(CHALLENGE_PATH)
    metrics = {
        metric.metric_id: metric
        for metric in calculate_metrics(
            dataset,
            _synthetic_rag_results(dataset),
            suite,
            ChallengeEvaluationRunner(suite).run(),
        )
    }

    assert metrics["unsupported_fact_rate"].numerator == 0
    assert metrics["unsupported_fact_rate"].denominator == 3
    assert metrics["unsupported_fact_rate"].rate == Decimal("0")
    assert metrics["unsupported_fact_rate"].outcome is MetricOutcome.PASS
    assert metrics["insufficient_evidence_behavior"].numerator == 1
    assert metrics["insufficient_evidence_behavior"].denominator == 1
    assert metrics["insufficient_evidence_behavior"].outcome is MetricOutcome.PASS
    assert metrics["redaction_success"].numerator == 1
    assert metrics["redaction_success"].denominator == 1
    assert metrics["redaction_success"].outcome is MetricOutcome.PASS


def test_v11_unsupported_claim_increments_numerator_and_fails_zero_rate_gate() -> None:
    dataset = load_rag_dataset(RAG_V11_PATH)
    suite = load_challenge_suite(CHALLENGE_PATH)
    rag = list(_synthetic_rag_results(dataset))
    claim_index = next(
        index for index, result in enumerate(rag) if result.claim_support.applicable
    )
    claim_support = rag[claim_index].claim_support
    claims = list(claim_support.claims)
    claims[0] = claims[0].model_copy(update={"status": ClaimSupportStatus.FAIL})
    rag[claim_index] = rag[claim_index].model_copy(
        update={
            "claim_support": claim_support.model_copy(
                update={"unsupported_claim_count": 1, "claims": tuple(claims)}
            ),
            "unsupported_fact_status": RetrievalDimensionStatus.FAIL,
        }
    )

    metrics = {
        metric.metric_id: metric
        for metric in calculate_metrics(
            dataset,
            tuple(rag),
            suite,
            ChallengeEvaluationRunner(suite).run(),
        )
    }
    unsupported = metrics["unsupported_fact_rate"]
    assert unsupported.numerator == 1
    assert unsupported.denominator == 3
    assert unsupported.rate == Decimal(1) / Decimal(3)
    assert unsupported.outcome is MetricOutcome.FAIL


def test_expected_source_and_provenance_metric_numerators_are_independent(inputs) -> None:
    dataset, suite = inputs
    rag = list(_synthetic_rag_results(dataset))
    first_retrieval = next(index for index, result in enumerate(rag) if result.retrieval is not None)
    retrieval = rag[first_retrieval].retrieval
    assert retrieval is not None
    rag[first_retrieval] = rag[first_retrieval].model_copy(update={
        "retrieval": retrieval.model_copy(update={"expected_source_found": False}),
    })
    metrics = {metric.metric_id: metric for metric in calculate_metrics(
        dataset, tuple(rag), suite, ChallengeEvaluationRunner(suite).run()
    )}
    assert metrics["expected_source_top5_rate"].numerator == 22
    assert metrics["provenance_success_rate"].numerator == 23


def test_redaction_metric_counts_only_supplied_secret_cases(inputs) -> None:
    dataset, suite = inputs
    rag = list(_synthetic_rag_results(dataset))
    security_index = next(index for index, result in enumerate(rag) if result.security is not None)
    security = rag[security_index].security
    assert security is not None
    redaction = RedactionObservation(
        status=RedactionStatus.PASS, sanitization_invoked=True, supplied_secret_count=1,
    )
    rag[security_index] = rag[security_index].model_copy(update={
        "security": security.model_copy(update={"redaction": redaction}),
    })
    metrics = {metric.metric_id: metric for metric in calculate_metrics(
        dataset, tuple(rag), suite, ChallengeEvaluationRunner(suite).run()
    )}
    assert metrics["redaction_success"].numerator == 1
    assert metrics["redaction_success"].denominator == 1
    assert metrics["redaction_success"].outcome is MetricOutcome.PASS


def test_invalid_security_expectation_fails_fast_as_contract_error(inputs) -> None:
    dataset, suite = inputs
    security_case = next(case for case in dataset.dataset.cases if case.expected_audit_event is not None)
    invalid_event = security_case.expected_audit_event.model_copy(update={"action_taken": "UNSUPPORTED_ACTION"})
    invalid_case = security_case.model_copy(update={"expected_audit_event": invalid_event})
    cases = tuple(invalid_case if case.id == security_case.id else case for case in dataset.dataset.cases)
    invalid_dataset = dataset.model_copy(update={
        "dataset": dataset.dataset.model_copy(update={"cases": cases}),
    })
    with pytest.raises(EvaluationDatasetContractError):
        calculate_metrics(invalid_dataset, _synthetic_rag_results(invalid_dataset), suite, ChallengeEvaluationRunner(suite).run())


def test_failed_security_and_audit_observations_are_not_compensated(inputs) -> None:
    dataset, suite = inputs
    rag = _synthetic_rag_results(dataset)
    metrics = {metric.metric_id: metric for metric in calculate_metrics(dataset, rag, suite, ChallengeEvaluationRunner(suite).run())}
    assert metrics["security_block_success"].outcome is MetricOutcome.FAIL
    assert metrics["security_audit_success"].outcome is MetricOutcome.FAIL


def test_overall_precedence_failure_then_not_measurable_then_pass() -> None:
    def metric(outcome: MetricOutcome) -> MetricResult:
        return MetricResult(
            metric_id="x", numerator=1 if outcome is MetricOutcome.PASS else None,
            denominator=1, rate=Decimal("1") if outcome is MetricOutcome.PASS else None,
            threshold=Decimal("1"), comparator=MetricComparator.ALL_APPLICABLE,
            outcome=outcome, reason="test", required_for_closure=True,
        )
    assert overall_outcome((metric(MetricOutcome.FAIL), metric(MetricOutcome.NOT_MEASURABLE)))[0] is MetricOutcome.FAIL
    assert overall_outcome((metric(MetricOutcome.NOT_MEASURABLE),))[0] is MetricOutcome.NOT_MEASURABLE
    assert overall_outcome((metric(MetricOutcome.PASS),))[0] is MetricOutcome.PASS


def test_report_is_deterministic_bounded_and_secret_safe(inputs) -> None:
    dataset, suite = inputs
    rag = _synthetic_rag_results(dataset)
    challenge = ChallengeEvaluationRunner(suite).run()
    report = build_phase11_report(dataset, rag, suite, challenge)
    first = serialize_report(report)
    second = serialize_report(report.model_copy(deep=True))
    assert first == second
    assert "What is the database password?" not in first
    assert "Authorization: Bearer" not in first
    assert "postgresql://" not in first
    assert "DATABASE_URL" not in first
    assert "traceback" not in first.lower()
    assert "F:\\My Drive" not in first
    assert load_serialized_report(first)["report_schema_version"] == "1.0"
