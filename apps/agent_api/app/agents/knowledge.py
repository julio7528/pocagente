"""Knowledge capability composed from approved retrieval, grounding, and LLM boundaries."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.agent_api.app.llm.errors import LLMProviderError
from apps.agent_api.app.llm.models import LLMGenerationRequest, LLMMessage, LLMProvider
from apps.agent_api.app.rag.grounding.context_builder import (
    Citation,
    EvidenceStatus,
    GroundedContext,
)
from apps.agent_api.app.rag.models import RetrievedChunk


class RetrievalBoundary(Protocol):
    """Existing Phase 7 retrieval boundary consumed by the Knowledge Agent."""

    async def search(self, query: str) -> Sequence[RetrievedChunk]:
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
    ) -> None:
        self._retrieval = retrieval
        self._context_builder = context_builder
        self._llm_provider = llm_provider

    async def answer(self, question: str) -> KnowledgeResult:
        """Answer only from structurally sufficient approved grounded context."""

        if not isinstance(question, str) or not question.strip():
            raise ValueError("knowledge question cannot be blank")

        retrieved_chunks = await self._retrieval.search(question)
        context = self._context_builder.build(question, retrieved_chunks)
        if context.evidence_status is EvidenceStatus.INSUFFICIENT_EVIDENCE:
            return KnowledgeResult(
                question=question,
                status=KnowledgeResultStatus.INSUFFICIENT_EVIDENCE,
                citations=(),
                reason=context.reason,
            )

        request = self._build_generation_request(context)
        try:
            generated = await self._llm_provider.generate(request)
        except LLMProviderError as error:
            return KnowledgeResult(
                question=question,
                status=KnowledgeResultStatus.PROVIDER_ERROR,
                citations=context.citations,
                reason=error.error_code,
            )

        return KnowledgeResult(
            question=question,
            status=KnowledgeResultStatus.ANSWERED,
            answer=generated.content,
            citations=context.citations,
            reason="GROUNDED_ANSWER_AVAILABLE",
        )

    @staticmethod
    def _build_generation_request(context: GroundedContext) -> LLMGenerationRequest:
        """Provide only safe evidence data, citations, and fixed grounding instructions."""

        system_instruction = "\n".join(
            (
                "Answer only from the supplied evidence.",
                *context.instructions,
                "Use only supplied citation IDs such as [C1] for supported factual claims.",
                "Do not invent citations, facts, authorization, routing, or tool permissions.",
                "Do not disclose internal identifiers, paths, checksums, or storage details.",
            )
        )
        evidence_blocks = "\n\n".join(
            (
                f"[{item.citation_id}] Priority tier {item.priority_tier}\n"
                f"Evidence data:\n{item.content}"
                for item in context.evidence
            )
        )
        user_content = f"Question:\n{context.query}\n\nGrounded evidence:\n{evidence_blocks}"
        return LLMGenerationRequest(
            messages=(
                LLMMessage(role="system", content=system_instruction),
                LLMMessage(role="user", content=user_content),
            )
        )
