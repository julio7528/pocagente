"""Knowledge capability composed from approved retrieval, grounding, and LLM boundaries."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from time import perf_counter
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.agent_api.app.llm.errors import LLMProviderError
from apps.agent_api.app.llm.models import LLMProvider
from apps.agent_api.app.agents.grounded_generation import (
    GroundedGenerationError,
    GroundedGenerationStatus,
    generate_grounded_outcome,
)
from apps.agent_api.app.agents.search_query_formulation import SearchQueryFormulation
from apps.agent_api.app.rag.grounding.context_builder import (
    Citation,
    EvidenceStatus,
    GroundedContext,
)
from apps.agent_api.app.rag.models import RetrievedChunk
from apps.agent_api.app.rag.scope import KnowledgeScope
from apps.agent_api.app.telemetry import RuntimeEventKind, emit_runtime_event


class KnowledgeRequest(BaseModel):
    """Trusted persistent Knowledge request; scope is never user-selected."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question: str = Field(min_length=1)
    knowledge_scope: KnowledgeScope

    @model_validator(mode="after")
    def require_persistent_scope(self) -> KnowledgeRequest:
        if not self.question.strip():
            raise ValueError("question must not be blank")
        if self.knowledge_scope not in {KnowledgeScope.INTERNAL, KnowledgeScope.PUBLIC_GETNET}:
            raise ValueError("persistent Knowledge requires an explicit retrieval scope")
        return self


class RetrievalBoundary(Protocol):
    """Existing Phase 7 retrieval boundary consumed by the Knowledge Agent."""

    async def search(self, query: str, knowledge_scope: KnowledgeScope) -> Sequence[RetrievedChunk]:
        """Return approved ranked retrieval results."""


class GroundingBoundary(Protocol):
    """Existing Phase 8 grounding boundary consumed by the Knowledge Agent."""

    def build(
        self,
        query: str,
        retrieved_chunks: Sequence[RetrievedChunk],
    ) -> GroundedContext:
        """Build the approved immutable grounding context."""


class KnowledgeResultStatus(StrEnum):
    """Controlled outcomes of one knowledge request."""

    ANSWERED = "ANSWERED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PROVIDER_ERROR = "PROVIDER_ERROR"


class KnowledgeResult(BaseModel):
    """Safe user-facing knowledge result with no internal evidence provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question: str = Field(min_length=1)
    status: KnowledgeResultStatus
    answer: str | None = None
    citations: tuple[Citation, ...] = ()
    reason: str = Field(min_length=1)
    retrieval_query: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def result_fields_match_status(self) -> KnowledgeResult:
        if self.status is KnowledgeResultStatus.ANSWERED and not self.answer:
            raise ValueError("answered knowledge results require an answer")
        if self.status is not KnowledgeResultStatus.ANSWERED and self.answer is not None:
            raise ValueError("non-success knowledge results cannot contain an answer")
        return self


class KnowledgeAgent:
    """Orchestrate, but never reimplement, retrieval, grounding, and generation."""

    def __init__(
        self,
        retrieval: RetrievalBoundary,
        context_builder: GroundingBoundary,
        llm_provider: LLMProvider,
        query_formulator: SearchQueryFormulation | None = None,
    ) -> None:
        self._retrieval = retrieval
        self._context_builder = context_builder
        self._llm_provider = llm_provider
        self._query_formulator = query_formulator

    async def answer(self, request: KnowledgeRequest) -> KnowledgeResult:
        """Answer only from structurally sufficient approved grounded context."""

        question = request.question

        retrieval_query = question
        if request.knowledge_scope is KnowledgeScope.PUBLIC_GETNET and self._query_formulator is not None:
            try:
                formulated = await self._query_formulator.formulate(question)
            except Exception:
                formulated = None
            if isinstance(formulated, str) and formulated.strip():
                retrieval_query = formulated.strip()[:200]

        retrieval_started_at = perf_counter()
        retrieved_chunks = await self._retrieval.search(retrieval_query, request.knowledge_scope)
        emit_runtime_event(
            RuntimeEventKind.RAG,
            name="hybrid_retrieval",
            value=request.knowledge_scope.value,
            count=len(retrieved_chunks),
            elapsed_ms=int((perf_counter() - retrieval_started_at) * 1000),
        )
        context = self._context_builder.build(question, retrieved_chunks)
        emit_runtime_event(
            RuntimeEventKind.GROUNDING,
            value=context.evidence_status.value,
            count=len(context.evidence),
        )
        if context.evidence_status is EvidenceStatus.INSUFFICIENT_EVIDENCE:
            return KnowledgeResult(
                question=question,
                status=KnowledgeResultStatus.INSUFFICIENT_EVIDENCE,
                citations=(),
                reason=context.reason,
                retrieval_query=retrieval_query if retrieval_query != question else None,
            )

        try:
            generated = await generate_grounded_outcome(
                self._llm_provider,
                question=context.query,
                grounding_instructions=context.instructions,
                evidence_blocks=tuple(
                    f"[{item.citation_id}] Priority tier {item.priority_tier}\nEvidence data:\n{item.content}"
                    for item in context.evidence
                ),
                available_citation_ids=tuple(item.citation_id for item in context.evidence),
            )
        except (LLMProviderError, GroundedGenerationError) as error:
            return KnowledgeResult(
                question=question,
                status=KnowledgeResultStatus.PROVIDER_ERROR,
                reason=getattr(error, "error_code", "invalid_grounded_generation"),
                retrieval_query=retrieval_query if retrieval_query != question else None,
            )
        if generated.status is GroundedGenerationStatus.INSUFFICIENT_EVIDENCE:
            return KnowledgeResult(
                question=question,
                status=KnowledgeResultStatus.INSUFFICIENT_EVIDENCE,
                citations=(),
                reason="GENERATION_INSUFFICIENT_EVIDENCE",
                retrieval_query=retrieval_query if retrieval_query != question else None,
            )
        citations_by_id = {citation.id: citation for citation in context.citations}
        return KnowledgeResult(
            question=question,
            status=KnowledgeResultStatus.ANSWERED,
            answer=generated.answer,
            citations=tuple(citations_by_id[item] for item in generated.citation_ids),
            reason="GROUNDED_ANSWER_AVAILABLE",
        )
