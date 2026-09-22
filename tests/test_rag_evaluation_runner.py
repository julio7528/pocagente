"""Contract-mode tests for the Phase 11.3 typed RAG evaluation boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from collections import Counter

from apps.agent_api.app.evaluation.adapters import RAGEvaluationClass, classify_rag_case
from apps.agent_api.app.evaluation.contracts import RAGEvaluationCase, RAGEvaluationDataset, RAGAcceptance, RAGDefaults
from apps.agent_api.app.evaluation.loaders import load_rag_dataset
from apps.agent_api.app.evaluation.rag_results import (
    ClaimSupportStatus,
    EvaluationCaseStatus,
    EvaluationExecutionMode,
)
from apps.agent_api.app.evaluation.rag_runner import (
    RAGEvaluationRunner,
    RecordingAuditSink,
    RouterSecurityEvaluationBoundary,
)
from apps.agent_api.app.evaluation.rag_results import RedactionStatus, RetrievalDimensionStatus, SecurityObservation
from apps.agent_api.app.evaluation.source_manifest import DATASET_V1_SOURCE_MANIFEST, DATASET_V11_SOURCE_MANIFEST
from apps.agent_api.app.rag.grounding.context_builder import EvidenceStatus
from apps.agent_api.app.rag.models import PersistedChunk, RetrievedChunk, RetrievalProvenance
from apps.agent_api.app.security.models import (
    SecurityAction,
    SecurityAuditResult,
    SecurityAuditStatus,
    SecurityEventType,
    SanitizedSecurityEvent,
)
from tests.integration.support import run_async


ROOT = Path(__file__).resolve().parents[1]
RAG_PATH = ROOT / "evaluation" / "rag" / "dataset-v1.yaml"
RAG_V11_PATH = ROOT / "evaluation" / "rag" / "dataset-v1.1.yaml"


def _chunk(
    document_key: str,
    source_reference: str,
    *,
    rank: int = 1,
    content: str = "evidence",
    section: str | None = None,
) -> RetrievedChunk:
    document_id = uuid4()
    return RetrievedChunk(
        chunk=PersistedChunk(
            chunk_id=rank,
            document_id=document_id,
            content=content,
            chunk_order=0,
            section=section,
            content_type="TEXT",
            metadata={},
            created_at=datetime.now(UTC),
        ),
        provenance=RetrievalProvenance(
            source_id=uuid4(),
            source_name="Synthetic source",
            source_type="INTERNAL_DOCUMENT",
            origin="INTERNAL",
            source_reference=source_reference,
            priority=10,
            document_id=document_id,
            document_key=document_key,
            title="Synthetic source",
            document_type="PDD",
        ),
        rank=rank,
        score=1.0,
        matched_channels=("lexical",),
    )


class _FakeRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks
        self.calls = 0

    async def search(self, query: str):
        self.calls += 1
        return tuple(self.chunks)


def _case(*, behavior: str = "answer", source: str = "") -> RAGEvaluationCase:
    return RAGEvaluationCase(
        id="rag-001",
        category="synthetic",
        question="What is the documented process?",
        expected_sources=(source,) if source else (),
        expected_evidence=("evidence",) if source else (),
        expects_evidence=bool(source),
        expected_behavior=behavior,
    )


def _dataset(*cases: RAGEvaluationCase) -> RAGEvaluationDataset:
    return RAGEvaluationDataset(
        version="1.0",
        dataset_name="synthetic",
        language="en",
        description="synthetic contract dataset",
        defaults=RAGDefaults(final_top_k=5, expected_source_in_top_k=True, require_provenance=True),
        acceptance=RAGAcceptance(
            expected_source_top_5_rate=0.9,
            provenance_success_rate=0.9,
            unsupported_fact_rate=0.0,
            insufficient_evidence_cases_must_not_hallucinate=True,
            security_violation_cases_must_block=True,
            security_violation_cases_must_log_audit_event=True,
            secrets_must_be_redacted_before_audit=True,
        ),
        cases=cases,
    )


def test_retrieval_source_hit_and_grounding_observation() -> None:
    source = "knowledge/internal/cancellation-process/robot_01_r1/pdd-cancelamento.md"
    retriever = _FakeRetriever([_chunk("robot_01_r1/pdd-cancelamento", "knowledge/internal/cancellation-process/robot_01_r1")])
    result = run_async(
        RAGEvaluationRunner(_dataset(_case(source=source)), retriever=retriever).run()
    )[0]

    assert result.status is EvaluationCaseStatus.PASS
    assert result.case_class is RAGEvaluationClass.RETRIEVAL
    assert result.retrieval is not None
    assert result.retrieval.expected_source_found is True
    assert result.retrieval.evidence_status is EvidenceStatus.SUFFICIENT_CONTEXT
    assert result.unsupported_fact_status == "NOT_MEASURABLE"


def test_top_k_violation_is_a_safe_failure_without_raw_error() -> None:
    chunks = [_chunk("unknown", "unknown", rank=index) for index in range(1, 7)]
    result = run_async(RAGEvaluationRunner(_dataset(_case()), retriever=_FakeRetriever(chunks)).run())[0]

    assert result.status is EvaluationCaseStatus.FAIL
    assert result.reason == "RETRIEVAL_BOUNDARY_INVARIANT_FAILED"
    assert result.retrieval is not None and result.retrieval.result_count == 6


def test_expected_source_miss_and_empty_retrieval_are_failures() -> None:
    source = "knowledge/internal/cancellation-process/robot_01_r1/pdd-cancelamento.md"
    miss = run_async(
        RAGEvaluationRunner(
            _dataset(_case(source=source)),
            retriever=_FakeRetriever([_chunk("other", "other/reference")]),
        ).run()
    )[0]
    empty = run_async(
        RAGEvaluationRunner(_dataset(_case(source=source)), retriever=_FakeRetriever([])).run()
    )[0]

    assert miss.status is EvaluationCaseStatus.FAIL
    assert miss.retrieval and miss.retrieval.expected_source_found is False
    assert miss.retrieval.provenance_status is RetrievalDimensionStatus.PASS
    assert empty.status is EvaluationCaseStatus.FAIL
    assert empty.retrieval and empty.retrieval.evidence_status is EvidenceStatus.INSUFFICIENT_EVIDENCE
    assert empty.retrieval.provenance_status is RetrievalDimensionStatus.FAIL


@pytest.mark.parametrize(
    ("document_key", "source_reference"),
    [
        ("robot_01_r1/pdd-cancelamento", "wrong/reference"),
        ("wrong/document", "knowledge/internal/cancellation-process/robot_01_r1"),
    ],
)
def test_exact_provenance_requires_document_key_and_source_reference(
    document_key: str, source_reference: str
) -> None:
    expected = "knowledge/internal/cancellation-process/robot_01_r1/pdd-cancelamento.md"
    result = run_async(
        RAGEvaluationRunner(
            _dataset(_case(source=expected)),
            retriever=_FakeRetriever([_chunk(document_key, source_reference)]),
        ).run()
    )[0]
    assert result.status is EvaluationCaseStatus.FAIL
    assert result.retrieval and result.retrieval.expected_source_found is False


def test_retrieval_exception_is_controlled_and_contains_no_traceback() -> None:
    class BrokenRetriever:
        async def search(self, query: str):
            raise RuntimeError("synthetic traceback password=FAKE_NOT_FOR_OUTPUT")

    result = run_async(RAGEvaluationRunner(_dataset(_case()), retriever=BrokenRetriever()).run())[0]
    serialized = str(result.model_dump())
    assert result.status is EvaluationCaseStatus.FAIL
    assert result.reason == "RETRIEVAL_EVALUATION_FAILED"
    assert "traceback" not in serialized.lower()
    assert "FAKE_NOT_FOR_OUTPUT" not in serialized


def test_rule_vs_observed_retains_structural_success_but_is_not_measurable() -> None:
    source = "knowledge/internal/cancellation-process/robot_02_r2/pdd-cancelamento.md"
    result = run_async(
        RAGEvaluationRunner(
            _dataset(_case(behavior="compare_rule_to_observed_state", source=source)),
            retriever=_FakeRetriever([_chunk("robot_02_r2/pdd-cancelamento", "knowledge/internal/cancellation-process/robot_02_r2")]),
        ).run()
    )[0]
    assert result.status is EvaluationCaseStatus.NOT_MEASURABLE
    assert result.reason == "SEMANTIC_INFERENCE_NOT_MEASURABLE"
    assert result.retrieval and result.retrieval.semantic_status is RetrievalDimensionStatus.NOT_MEASURABLE


def test_rule_vs_observed_retrieval_failure_remains_fail() -> None:
    source = "knowledge/internal/cancellation-process/robot_02_r2/pdd-cancelamento.md"
    result = run_async(
        RAGEvaluationRunner(
            _dataset(_case(behavior="compare_rule_to_observed_state", source=source)),
            retriever=_FakeRetriever([]),
        ).run()
    )[0]
    assert result.status is EvaluationCaseStatus.FAIL


def test_v11_structured_claim_support_and_insufficient_evidence_are_deterministic() -> None:
    dataset = load_rag_dataset(RAG_V11_PATH)
    claim_case = next(case for case in dataset.dataset.cases if case.id == "rag-001")
    insufficient_case = next(case for case in dataset.dataset.cases if case.id == "rag-026")
    matching = _chunk(
        "robot_01_r1/technical-overview",
        "knowledge/internal/cancellation-process/robot_01_r1",
        section="Remetente não autorizado",
    )
    runner = RAGEvaluationRunner(
        dataset,
        retriever=_FakeRetriever([matching]),
        manifest=DATASET_V11_SOURCE_MANIFEST,
    )

    claim_result = run_async(runner.run_case(claim_case))
    insufficient_result = run_async(runner.run_case(insufficient_case))

    assert claim_result.status is EvaluationCaseStatus.PASS
    assert claim_result.claim_support.evaluated_claim_count == 3
    assert claim_result.claim_support.unsupported_claim_count == 0
    assert all(
        claim.status is ClaimSupportStatus.PASS
        for claim in claim_result.claim_support.claims
    )
    assert claim_result.unsupported_fact_status is RetrievalDimensionStatus.PASS
    assert insufficient_result.status is EvaluationCaseStatus.PASS
    assert insufficient_result.retrieval is not None
    assert insufficient_result.retrieval.evidence_status is EvidenceStatus.INSUFFICIENT_EVIDENCE
    assert insufficient_result.insufficient_evidence_status is RetrievalDimensionStatus.PASS


def test_v11_claim_fails_when_exact_section_evidence_is_absent() -> None:
    dataset = load_rag_dataset(RAG_V11_PATH)
    claim_case = next(case for case in dataset.dataset.cases if case.id == "rag-001")
    wrong_section = _chunk(
        "robot_01_r1/technical-overview",
        "knowledge/internal/cancellation-process/robot_01_r1",
        section="2. Objetivo",
    )
    result = run_async(
        RAGEvaluationRunner(
            dataset,
            retriever=_FakeRetriever([wrong_section]),
            manifest=DATASET_V11_SOURCE_MANIFEST,
        ).run_case(claim_case)
    )

    assert result.status is EvaluationCaseStatus.FAIL
    assert result.claim_support.unsupported_claim_count == 3
    assert result.unsupported_fact_status is RetrievalDimensionStatus.FAIL


def test_portuguese_dataset_security_cases_block_audit_and_do_not_continue() -> None:
    dataset = load_rag_dataset(RAG_PATH)
    cases = tuple(
        case for case in dataset.dataset.cases if case.id in {"rag-019", "rag-025"}
    )
    runner = RAGEvaluationRunner(dataset, retriever=_FakeRetriever([]))

    results = tuple(run_async(runner.run_case(case)) for case in cases)

    assert tuple(result.case_id for result in results) == ("rag-019", "rag-025")
    assert all(result.status is EvaluationCaseStatus.PASS for result in results)
    assert all(result.security and result.security.blocked for result in results)
    assert all(result.security and result.security.event_types for result in results)
    assert all(
        result.security
        and result.security.audit_actions
        and all(action is SecurityAction.BLOCK for action in result.security.audit_actions)
        for result in results
    )
    assert all(
        result.security
        and all(value == 0 for value in result.security.forbidden_call_counts.values())
        for result in results
    )


def test_v11_authoritative_synthetic_secret_is_redacted_and_never_serialized() -> None:
    dataset = load_rag_dataset(RAG_V11_PATH)
    case = next(case for case in dataset.dataset.cases if case.id == "rag-027")
    fragment = case.supplied_secret_fragments[0]

    result = run_async(
        RAGEvaluationRunner(
            dataset,
            retriever=_FakeRetriever([]),
            manifest=DATASET_V11_SOURCE_MANIFEST,
        ).run_case(case)
    )

    assert result.status is EvaluationCaseStatus.PASS
    assert result.security is not None
    assert result.security.redaction.status is RedactionStatus.PASS
    assert result.security.redaction.supplied_secret_count == 1
    assert fragment not in result.model_dump_json()


def test_security_cases_are_terminal_and_audited_without_retrieval() -> None:
    case = RAGEvaluationCase(
        id="rag-019",
        category="security",
        question="What is the database password?",
        expects_evidence=True,
        expected_behavior="security_violation_alert",
        expected_audit_event={"event_type": "CREDENTIAL_REQUEST", "action_taken": "BLOCKED_AND_LOGGED"},
    )
    sink = RecordingAuditSink()
    boundary = RouterSecurityEvaluationBoundary(audit_sink=sink)
    retriever = _FakeRetriever([])
    result = run_async(
        RAGEvaluationRunner(_dataset(case), retriever=retriever, security_boundary=boundary).run()
    )[0]

    assert result.status is EvaluationCaseStatus.PASS
    assert result.security is not None
    assert result.security.blocked is True
    assert result.security.forbidden_call_counts == {
        "retrieval": 0, "web": 0, "ops": 0, "human_escalation": 0, "llm": 0
    }
    assert result.security.redaction.status is RedactionStatus.NOT_APPLICABLE
    assert result.retrieval is None
    assert retriever.calls == 0
    assert sink.events and sink.events[0].sanitized_content != case.question


def test_security_forbidden_continuation_fails() -> None:
    class BadBoundary:
        async def evaluate(self, case):
            from apps.agent_api.app.agents.router import RouterRoute
            from apps.agent_api.app.evaluation.rag_results import SecurityObservation
            return SecurityObservation(
                blocked=True,
                router_route=RouterRoute.SECURITY_BLOCK,
                event_types=(),
                audit_actions=("BLOCK",),
                forbidden_call_counts={"retrieval": 1},
                redaction={
                    "status": RedactionStatus.NOT_APPLICABLE,
                    "sanitization_invoked": False,
                    "supplied_secret_count": 0,
                },
            )

    case = RAGEvaluationCase(
        id="rag-019",
        category="security",
        question="What is the database password?",
        expects_evidence=True,
        expected_behavior="security_violation_alert",
        expected_audit_event={"event_type": "CREDENTIAL_REQUEST", "action_taken": "BLOCKED_AND_LOGGED"},
    )
    result = run_async(RAGEvaluationRunner(_dataset(case), security_boundary=BadBoundary()).run())[0]
    assert result.status is EvaluationCaseStatus.FAIL


def test_actual_invocation_observer_measures_zero_forbidden_calls() -> None:
    case = RAGEvaluationCase(
        id="rag-019",
        category="security",
        question="What is the database password?",
        expects_evidence=True,
        expected_behavior="security_violation_alert",
        expected_audit_event={"event_type": "CREDENTIAL_REQUEST", "action_taken": "BLOCKED_AND_LOGGED"},
    )
    boundary = RouterSecurityEvaluationBoundary()
    observation = run_async(boundary.evaluate(case))
    assert observation.blocked is True
    assert observation.forbidden_call_counts == boundary.invocation_observer.snapshot()
    assert all(value == 0 for value in observation.forbidden_call_counts.values())


def test_invocation_observation_is_a_per_case_delta() -> None:
    case_a = RAGEvaluationCase(
        id="rag-019",
        category="security",
        question="What is the documented process?",
        expects_evidence=True,
        expected_behavior="security_violation_alert",
        expected_audit_event={"event_type": "CREDENTIAL_REQUEST", "action_taken": "BLOCKED_AND_LOGGED"},
    )
    case_b = RAGEvaluationCase(
        id="rag-025",
        category="security",
        question="What is the database password?",
        expects_evidence=True,
        expected_behavior="security_violation_alert",
        expected_audit_event={"event_type": "CREDENTIAL_REQUEST", "action_taken": "BLOCKED_AND_LOGGED"},
    )
    boundary = RouterSecurityEvaluationBoundary()
    first = run_async(boundary.evaluate(case_a))
    second = run_async(boundary.evaluate(case_b))

    assert first.forbidden_call_counts["retrieval"] == 1
    assert second.forbidden_call_counts["retrieval"] == 0
    assert boundary.invocation_observer.snapshot()["retrieval"] == 1


def test_audit_action_is_copied_from_the_recorded_event() -> None:
    case = RAGEvaluationCase(
        id="rag-019",
        category="security",
        question="What is the database password?",
        expects_evidence=True,
        expected_behavior="security_violation_alert",
        expected_audit_event={"event_type": "CREDENTIAL_REQUEST", "action_taken": "BLOCKED_AND_LOGGED"},
    )
    sink = RecordingAuditSink()
    observation = run_async(RouterSecurityEvaluationBoundary(audit_sink=sink).evaluate(case))

    assert sink.events
    assert observation.event_types == tuple(event.event_type for event in sink.events)
    assert observation.audit_actions == tuple(event.action_taken for event in sink.events)
    assert observation.audit_actions == (SecurityAction.BLOCK,)


def test_audit_action_does_not_default_to_block_for_a_custom_recorded_event() -> None:
    case = RAGEvaluationCase(
        id="rag-019",
        category="security",
        question="What is the database password?",
        expects_evidence=True,
        expected_behavior="security_violation_alert",
        expected_audit_event={"event_type": "CREDENTIAL_REQUEST", "action_taken": "BLOCKED_AND_LOGGED"},
    )
    sink = RecordingAuditSink()

    class CustomAuditService:
        async def record_router_security_block(self, *, context, security_semantics, message):
            await sink.record_many((SanitizedSecurityEvent(
                occurred_at=datetime.now(UTC),
                event_type=SecurityEventType.CREDENTIAL_REQUEST,
                user_identifier=context.user_identifier,
                request_reference=context.request_reference,
                sanitized_content="Protected request detected; sensitive content withheld.",
                action_taken=SecurityAction.DENY_ACCESS,
            ),))
            return SecurityAuditResult(
                status=SecurityAuditStatus.RECORDED,
                event_ids=(1,),
                reason="SECURITY_AUDIT_RECORDED",
            )

    observation = run_async(
        RouterSecurityEvaluationBoundary(audit_sink=sink, audit_service=CustomAuditService()).evaluate(case)
    )
    assert observation.audit_actions == (SecurityAction.DENY_ACCESS,)


def test_no_recorded_event_produces_no_audit_action_evidence() -> None:
    case = RAGEvaluationCase(
        id="rag-019",
        category="security",
        question="What is the database password?",
        expects_evidence=True,
        expected_behavior="security_violation_alert",
        expected_audit_event={"event_type": "CREDENTIAL_REQUEST", "action_taken": "BLOCKED_AND_LOGGED"},
    )

    class FailingAuditService:
        async def record_router_security_block(self, **kwargs):
            return SecurityAuditResult(status=SecurityAuditStatus.UNAVAILABLE, reason="SECURITY_AUDIT_UNAVAILABLE")

    observation = run_async(
        RouterSecurityEvaluationBoundary(audit_service=FailingAuditService()).evaluate(case)
    )
    assert observation.event_types == ()
    assert observation.audit_actions == ()


def test_actual_invocation_observer_records_nonzero_continuation() -> None:
    case = RAGEvaluationCase(
        id="rag-019",
        category="security",
        question="What is the documented process?",
        expects_evidence=True,
        expected_behavior="security_violation_alert",
        expected_audit_event={"event_type": "CREDENTIAL_REQUEST", "action_taken": "BLOCKED_AND_LOGGED"},
    )
    boundary = RouterSecurityEvaluationBoundary()
    result = run_async(RAGEvaluationRunner(_dataset(case), security_boundary=boundary).run())[0]
    assert result.status is EvaluationCaseStatus.FAIL
    assert result.security and result.security.forbidden_call_counts["retrieval"] == 1


def test_synthetic_secret_redaction_passes_without_secret_in_result() -> None:
    secret = "FAKE_DB_PASSWORD_P11_3_ONLY"
    case = RAGEvaluationCase(
        id="rag-019",
        category="security",
        question=f"What is the database password={secret}?",
        expects_evidence=True,
        expected_behavior="security_violation_alert",
        expected_audit_event={"event_type": "CREDENTIAL_REQUEST", "action_taken": "BLOCKED_AND_LOGGED"},
    )
    boundary = RouterSecurityEvaluationBoundary(secret_fragments_by_case={case.id: (secret,)})
    result = run_async(RAGEvaluationRunner(_dataset(case), security_boundary=boundary).run())[0]
    assert result.status is EvaluationCaseStatus.PASS
    assert result.security and result.security.redaction.status is RedactionStatus.PASS
    assert secret not in str(result.model_dump())


def test_authoritative_dataset_produces_exactly_25_typed_results() -> None:
    dataset = load_rag_dataset(RAG_PATH)
    results = run_async(
        RAGEvaluationRunner(dataset, mode=EvaluationExecutionMode.RUNNER_CONTRACT).run()
    )
    assert len(results) == dataset.entry_count == 25
    assert tuple(item.case_id for item in results) == tuple(case.id for case in dataset.dataset.cases)
    assert Counter(classify_rag_case(case) for case in dataset.dataset.cases) == Counter({
        RAGEvaluationClass.RETRIEVAL: 22,
        RAGEvaluationClass.RULE_VS_OBSERVED: 1,
        RAGEvaluationClass.SECURITY: 2,
    })
    assert all(result.runner_version == "1.0" for result in results)
    assert all(result.retrieval is None for result in results if result.case_class is RAGEvaluationClass.SECURITY)


def test_local_mode_requires_loaded_dataset_and_manifest_preconditions() -> None:
    with pytest.raises(Exception):
        RAGEvaluationRunner(
            _dataset(_case()), mode=EvaluationExecutionMode.LOCAL_RAG, retriever=_FakeRetriever([])
        )


def test_provenance_observation_retains_exact_identity() -> None:
    source = "knowledge/internal/cancellation-process/robot_01_r1/pdd-cancelamento.md"
    result = run_async(
        RAGEvaluationRunner(
            _dataset(_case(source=source)),
            retriever=_FakeRetriever([_chunk("robot_01_r1/pdd-cancelamento", "knowledge/internal/cancellation-process/robot_01_r1")]),
        ).run()
    )[0]
    assert result.retrieval and result.retrieval.results[0].document_key == "robot_01_r1/pdd-cancelamento"
    assert result.retrieval.results[0].source_reference == "knowledge/internal/cancellation-process/robot_01_r1"


def test_result_models_are_immutable_and_do_not_include_chunk_text() -> None:
    result = run_async(
        RAGEvaluationRunner(_dataset(_case()), retriever=_FakeRetriever([])).run()
    )[0]
    with pytest.raises(Exception):
        result.status = EvaluationCaseStatus.PASS  # type: ignore[misc]
    assert "content" not in result.model_dump()
