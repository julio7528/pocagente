"""Typed Phase 11.3 RAG evaluation boundary.

This module observes the existing retrieval, grounding, Router, and audit
boundaries. It never generates an answer, implements retrieval, or classifies
security text independently.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from apps.agent_api.app.agents.router import RouterAgent, RouterRoute
from apps.agent_api.app.agents.orchestration import LangGraphOrchestrator, OrchestrationRequest
from apps.agent_api.app.agents.knowledge import KnowledgeAgent
from apps.agent_api.app.llm.errors import LLMProviderError
from apps.agent_api.app.llm.models import LLMGenerationRequest
from apps.agent_api.app.rag.grounding.context_builder import ContextBuilder, EvidenceStatus
from apps.agent_api.app.rag.models import RetrievedChunk
from apps.agent_api.app.security.audit import SecurityAuditService
from apps.agent_api.app.security.models import SecurityAuditContext, SanitizedSecurityEvent

from .adapters import (
    RAGEvaluationClass,
    adapt_security_expectation,
    classify_rag_case,
)
from .contracts import (
    EvaluationDatasetContractError,
    LoadedRAGDataset,
    RAGEvaluationCase,
    RAGEvaluationDataset,
)
from .source_manifest import (
    EvaluationSourceManifest,
    expected_source_matches,
    source_manifest_for_version,
    validate_manifest_coverage,
)
from .rag_results import (
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
    RetrievedProvenanceObservation,
    SecurityObservation,
)


class RetrievalBoundary(Protocol):
    async def search(self, query: str) -> Sequence[RetrievedChunk]: ...


class SecurityEvaluationBoundary(Protocol):
    async def evaluate(self, case: RAGEvaluationCase) -> SecurityObservation: ...


class InvocationObserver:
    """Measured invocation counters for injected capability boundaries."""

    def __init__(self) -> None:
        self._counts = {
            "retrieval": 0,
            "web": 0,
            "ops": 0,
            "human_escalation": 0,
            "llm": 0,
        }

    def increment(self, name: str) -> None:
        self._counts[name] += 1

    def snapshot(self) -> dict[str, int]:
        return dict(self._counts)

    @staticmethod
    def delta(before: Mapping[str, int], after: Mapping[str, int]) -> dict[str, int]:
        if tuple(before) != tuple(after):
            raise RuntimeError("evaluation invocation counter set changed")
        result: dict[str, int] = {}
        for name in before:
            value = after[name] - before[name]
            if value < 0:
                raise RuntimeError("evaluation invocation counter decreased")
            result[name] = value
        return result


class _RetrievalInvocationSpy:
    def __init__(self, observer: InvocationObserver) -> None:
        self._observer = observer

    async def search(self, query: str):
        self._observer.increment("retrieval")
        return ()


class _LLMInvocationSpy:
    def __init__(self, observer: InvocationObserver) -> None:
        self._observer = observer

    async def generate(self, request: LLMGenerationRequest):
        self._observer.increment("llm")
        raise LLMProviderError()


class _CustomerSupportInvocationSpy:
    def __init__(self, observer: InvocationObserver) -> None:
        self._observer = observer

    async def answer(self, request):
        self._observer.increment("ops")
        raise RuntimeError("evaluation customer-support capability was unexpectedly invoked")


class _WebInvocationSpy:
    def __init__(self, observer: InvocationObserver) -> None:
        self._observer = observer

    async def answer(self, question: str):
        self._observer.increment("web")
        raise RuntimeError("evaluation web capability was unexpectedly invoked")


class _HumanInvocationSpy:
    def __init__(self, observer: InvocationObserver) -> None:
        self._observer = observer

    def transition(self, request):
        self._observer.increment("human_escalation")
        raise RuntimeError("evaluation human capability was unexpectedly invoked")


class RecordingAuditSink:
    """Non-persistent sink for contract/local evaluation observations."""

    def __init__(self) -> None:
        self.events: list[SanitizedSecurityEvent] = []

    async def record_many(self, events: tuple[SanitizedSecurityEvent, ...]) -> tuple[int, ...]:
        self.events.extend(events)
        return tuple(range(1, len(events) + 1))

    async def record(self, event: SanitizedSecurityEvent) -> int:
        return (await self.record_many((event,)))[0]


class RouterSecurityEvaluationBoundary:
    """Adapt the existing Router and SecurityAuditService for safe observation."""

    def __init__(
        self,
        *,
        router: RouterAgent | None = None,
        audit_service: SecurityAuditService | None = None,
        audit_sink: RecordingAuditSink | None = None,
        orchestrator: LangGraphOrchestrator | None = None,
        invocation_observer: InvocationObserver | None = None,
        secret_fragments_by_case: Mapping[str, tuple[str, ...]] | None = None,
        user_identifier: str = "phase11_evaluation_user",
    ) -> None:
        self._router = router or RouterAgent()
        self._audit_sink = audit_sink or RecordingAuditSink()
        self._audit_service = audit_service or SecurityAuditService(self._audit_sink)
        self._invocation_observer = invocation_observer or InvocationObserver()
        self._orchestrator = orchestrator or LangGraphOrchestrator(
            router=self._router,
            knowledge_agent=KnowledgeAgent(
                _RetrievalInvocationSpy(self._invocation_observer),
                ContextBuilder(),
                _LLMInvocationSpy(self._invocation_observer),
            ),
            customer_support_agent=_CustomerSupportInvocationSpy(self._invocation_observer),  # type: ignore[arg-type]
            web_knowledge_agent=_WebInvocationSpy(self._invocation_observer),
            human_escalation_agent=_HumanInvocationSpy(self._invocation_observer),
            security_audit_service=self._audit_service,
        )
        self._secret_fragments_by_case = dict(secret_fragments_by_case or {})
        self._user_identifier = user_identifier
        self._request_number = 0

    @property
    def invocation_observer(self) -> InvocationObserver:
        return self._invocation_observer

    async def evaluate(self, case: RAGEvaluationCase) -> SecurityObservation:
        self._request_number += 1
        counts_before = self._invocation_observer.snapshot()
        before = len(self._audit_sink.events)
        orchestration_result = await self._orchestrator.execute(
            OrchestrationRequest(
                message=case.question,
                security_audit_context=SecurityAuditContext(
                    user_identifier=self._user_identifier,
                    request_reference=f"P11_RAG_{self._request_number}",
                ),
            )
        )
        forbidden = self._invocation_observer.delta(
            counts_before, self._invocation_observer.snapshot()
        )
        events = tuple(self._audit_sink.events[before:])
        fragments = tuple(
            dict.fromkeys(
                (*case.supplied_secret_fragments, *self._secret_fragments_by_case.get(case.id, ()))
            )
        )
        if orchestration_result.route is not RouterRoute.SECURITY_BLOCK:
            return SecurityObservation(
                blocked=False,
                router_route=orchestration_result.route,
                forbidden_call_counts=forbidden,
                redaction=RedactionObservation(
                    status=RedactionStatus.NOT_APPLICABLE,
                    sanitization_invoked=False,
                    supplied_secret_count=len(fragments),
                ),
            )
        supplied_removed = bool(events) and all(
            event.sanitized_content
            and all(fragment not in event.sanitized_content for fragment in fragments)
            for event in events
        )
        redaction_status = (
            RedactionStatus.PASS if supplied_removed else RedactionStatus.FAIL
        ) if fragments else RedactionStatus.NOT_APPLICABLE
        return SecurityObservation(
            blocked=True,
            router_route=orchestration_result.route,
            event_types=tuple(event.event_type for event in events),
            audit_actions=tuple(event.action_taken for event in events)
            if events
            else (),
            forbidden_call_counts=forbidden,
            redaction=RedactionObservation(
                status=redaction_status,
                sanitization_invoked=bool(events),
                supplied_secret_count=len(fragments),
            ),
        )


class RAGEvaluationRunner:
    """Execute typed RAG observations without generation or aggregate metrics."""

    def __init__(
        self,
        dataset: LoadedRAGDataset | RAGEvaluationDataset,
        *,
        mode: EvaluationExecutionMode = EvaluationExecutionMode.RUNNER_CONTRACT,
        retriever: RetrievalBoundary | None = None,
        context_builder: ContextBuilder | None = None,
        security_boundary: SecurityEvaluationBoundary | None = None,
        manifest: EvaluationSourceManifest | None = None,
    ) -> None:
        self._dataset = dataset.dataset if isinstance(dataset, LoadedRAGDataset) else dataset
        self._mode = mode
        self._retriever = retriever
        self._context_builder = context_builder or ContextBuilder()
        self._security_boundary = security_boundary or RouterSecurityEvaluationBoundary()
        self._manifest = manifest or source_manifest_for_version(self._dataset.version)
        self._retrieval_invocations = 0
        if mode is EvaluationExecutionMode.LOCAL_RAG and retriever is None:
            raise EvaluationDatasetContractError("LOCAL_RAG mode requires the approved retrieval boundary")
        if mode is EvaluationExecutionMode.LOCAL_RAG:
            if not isinstance(dataset, LoadedRAGDataset):
                raise EvaluationDatasetContractError(
                    "LOCAL_RAG mode requires a loaded validated RAG dataset"
                )
            validate_manifest_coverage(dataset, self._manifest)

    @property
    def retrieval_invocation_count(self) -> int:
        return self._retrieval_invocations

    async def run(self) -> tuple[RAGCaseResult, ...]:
        """Process every declared case in dataset order."""

        return tuple([await self.run_case(case) for case in self._dataset.cases])

    async def run_case(self, case: RAGEvaluationCase) -> RAGCaseResult:
        case_class = classify_rag_case(case)
        if case_class is RAGEvaluationClass.SECURITY:
            return await self._run_security(case, case_class)
        return await self._run_retrieval(case, case_class)

    async def _run_security(
        self, case: RAGEvaluationCase, case_class: RAGEvaluationClass
    ) -> RAGCaseResult:
        try:
            observation = await self._security_boundary.evaluate(case)
            expected = adapt_security_expectation(case.expected_audit_event)  # type: ignore[arg-type]
            event_match = bool(set(observation.event_types) & set(expected.acceptable_event_types))
            no_forbidden_calls = all(value == 0 for value in observation.forbidden_call_counts.values())
            passed = (
                observation.blocked
                and observation.router_route is RouterRoute.SECURITY_BLOCK
                and event_match
                and bool(observation.audit_actions)
                and all(action is expected.action for action in observation.audit_actions)
                and no_forbidden_calls
                and observation.redaction.status in {
                    RedactionStatus.PASS,
                    RedactionStatus.NOT_APPLICABLE,
                }
            )
            return self._result(
                case,
                case_class,
                EvaluationCaseStatus.PASS if passed else EvaluationCaseStatus.FAIL,
                None if passed else "SECURITY_TERMINAL_INVARIANT_FAILED",
                security=observation,
            )
        except Exception:
            return self._result(case, case_class, EvaluationCaseStatus.FAIL, "SECURITY_EVALUATION_FAILED")

    async def _run_retrieval(
        self, case: RAGEvaluationCase, case_class: RAGEvaluationClass
    ) -> RAGCaseResult:
        try:
            if self._retriever is None:
                raise EvaluationDatasetContractError("Retrieval boundary is unavailable")
            self._retrieval_invocations += 1
            chunks = tuple(await self._retriever.search(case.question))
            context = self._context_builder.build(
                case.question,
                () if case_class is RAGEvaluationClass.INSUFFICIENT_EVIDENCE else chunks,
            )
            source_matches = tuple(
                any(
                    expected_source_matches(path, item.provenance, self._manifest)
                    for path in case.expected_sources
                )
                for item in chunks
            )
            # Provenance completeness is independent of whether the result
            # matches this case's expected source. Empty retrieval is not
            # valid provenance, despite Python's all(()) convention.
            valid_provenance = bool(chunks) and all(
                bool(item.provenance.document_key and item.provenance.source_reference)
                for item in chunks
            )
            expected_found = any(source_matches)
            provenance_observations = tuple(
                RetrievedProvenanceObservation(
                    rank=item.rank,
                    document_key=item.provenance.document_key,
                    source_reference=item.provenance.source_reference,
                    section=item.chunk.section,
                    expected_source_match=matched,
                )
                for item, matched in zip(chunks, source_matches, strict=True)
            )
            claim_support = self._evaluate_claim_support(
                case, chunks, provenance_observations
            )
            unsupported_fact_status = (
                RetrievalDimensionStatus.PASS
                if claim_support.applicable and claim_support.unsupported_claim_count == 0
                else RetrievalDimensionStatus.FAIL
                if claim_support.applicable
                else RetrievalDimensionStatus.NOT_MEASURABLE
            )
            insufficient_pass = (
                case_class is RAGEvaluationClass.INSUFFICIENT_EVIDENCE
                and context.evidence_status is EvidenceStatus.INSUFFICIENT_EVIDENCE
                and not claim_support.applicable
            )
            insufficient_evidence_status = (
                RetrievalDimensionStatus.PASS
                if insufficient_pass
                else RetrievalDimensionStatus.FAIL
                if case_class is RAGEvaluationClass.INSUFFICIENT_EVIDENCE
                else RetrievalDimensionStatus.NOT_MEASURABLE
            )
            if case_class is RAGEvaluationClass.INSUFFICIENT_EVIDENCE:
                structural_pass = (
                    len(chunks) <= self._dataset.defaults.final_top_k
                    and valid_provenance
                    and insufficient_pass
                )
            else:
                structural_pass = (
                    len(chunks) <= self._dataset.defaults.final_top_k
                    and expected_found
                    and valid_provenance
                    and context.evidence_status is EvidenceStatus.SUFFICIENT_CONTEXT
                    and unsupported_fact_status is not RetrievalDimensionStatus.FAIL
                )
            retrieval_status = (
                RetrievalDimensionStatus.PASS
                if len(chunks) <= self._dataset.defaults.final_top_k
                else RetrievalDimensionStatus.FAIL
            )
            provenance_status = (
                RetrievalDimensionStatus.PASS
                if valid_provenance
                else RetrievalDimensionStatus.FAIL
            )
            grounding_status = (
                RetrievalDimensionStatus.PASS
                if (
                    context.evidence_status is EvidenceStatus.INSUFFICIENT_EVIDENCE
                    if case_class is RAGEvaluationClass.INSUFFICIENT_EVIDENCE
                    else context.evidence_status is EvidenceStatus.SUFFICIENT_CONTEXT
                )
                else RetrievalDimensionStatus.FAIL
            )
            semantic_status = (
                RetrievalDimensionStatus.NOT_MEASURABLE
                if case_class is RAGEvaluationClass.RULE_VS_OBSERVED
                else RetrievalDimensionStatus.NOT_APPLICABLE
            )
            observation = RetrievalObservation(
                result_count=len(chunks),
                final_rank=tuple(item.rank for item in chunks),
                results=provenance_observations,
                expected_source_found=expected_found,
                evidence_status=context.evidence_status,
                evidence_reason=context.reason,
                evidence_count=len(context.evidence),
                citation_count=len(context.citations),
                retrieval_status=retrieval_status,
                provenance_status=provenance_status,
                grounding_status=grounding_status,
                semantic_status=semantic_status,
            )
            status = (
                EvaluationCaseStatus.FAIL
                if not structural_pass
                else EvaluationCaseStatus.NOT_MEASURABLE
                if case_class is RAGEvaluationClass.RULE_VS_OBSERVED
                else EvaluationCaseStatus.PASS
            )
            reason = (
                "SEMANTIC_INFERENCE_NOT_MEASURABLE"
                if status is EvaluationCaseStatus.NOT_MEASURABLE
                else None
                if status is EvaluationCaseStatus.PASS
                else "RETRIEVAL_BOUNDARY_INVARIANT_FAILED"
            )
            return self._result(
                case,
                case_class,
                status,
                reason,
                retrieval=observation,
                claim_support=claim_support,
                unsupported_fact_status=unsupported_fact_status,
                insufficient_evidence_status=insufficient_evidence_status,
            )
        except Exception:
            return self._result(case, case_class, EvaluationCaseStatus.FAIL, "RETRIEVAL_EVALUATION_FAILED")

    def _result(
        self,
        case: RAGEvaluationCase,
        case_class: RAGEvaluationClass,
        status: EvaluationCaseStatus,
        reason: str | None,
        *,
        retrieval: RetrievalObservation | None = None,
        security: SecurityObservation | None = None,
        claim_support: ClaimSupportObservation | None = None,
        unsupported_fact_status: RetrievalDimensionStatus = RetrievalDimensionStatus.NOT_MEASURABLE,
        insufficient_evidence_status: RetrievalDimensionStatus = RetrievalDimensionStatus.NOT_MEASURABLE,
    ) -> RAGCaseResult:
        return RAGCaseResult(
            case_id=case.id,
            dataset_version=self._dataset.version,
            execution_mode=self._mode,
            case_class=case_class,
            status=status,
            reason=reason,
            retrieval=retrieval,
            security=security,
            claim_support=claim_support or ClaimSupportObservation(
                applicable=False,
                evaluated_claim_count=0,
                unsupported_claim_count=0,
            ),
            unsupported_fact_status=unsupported_fact_status,
            insufficient_evidence_status=insufficient_evidence_status,
        )

    def _evaluate_claim_support(
        self,
        case: RAGEvaluationCase,
        chunks: tuple[RetrievedChunk, ...],
        observations: tuple[RetrievedProvenanceObservation, ...],
    ) -> ClaimSupportObservation:
        claims: list[EvaluatedClaimObservation] = []
        for expectation in case.claim_expectations:
            supporting = tuple(
                observation
                for item, observation in zip(chunks, observations, strict=True)
                if item.chunk.section in expectation.allowed_sections
                and any(
                    expected_source_matches(path, item.provenance, self._manifest)
                    for path in expectation.allowed_sources
                )
            )
            claims.append(
                EvaluatedClaimObservation(
                    claim_id=expectation.claim_id,
                    expected_value=expectation.expected_value,
                    status=(
                        ClaimSupportStatus.PASS
                        if supporting
                        else ClaimSupportStatus.FAIL
                    ),
                    supporting_evidence=supporting,
                )
            )
        return ClaimSupportObservation(
            applicable=bool(claims),
            evaluated_claim_count=len(claims),
            unsupported_claim_count=sum(
                claim.status is ClaimSupportStatus.FAIL for claim in claims
            ),
            claims=tuple(claims),
        )
