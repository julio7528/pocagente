"""Knowledge generation over controlled, non-persistent live public web evidence."""

from __future__ import annotations

from apps.agent_api.app.agents.knowledge import KnowledgeResult, KnowledgeResultStatus
from apps.agent_api.app.llm.errors import LLMProviderError
from apps.agent_api.app.llm.models import LLMGenerationRequest, LLMMessage, LLMProvider
from apps.agent_api.app.rag.grounding import EvidenceStatus, LiveWebContextBuilder, LiveWebGroundedContext
from apps.agent_api.app.web.errors import WebSearchError
from apps.agent_api.app.web.models import WebSearchProvider, WebSearchRequest, WebSearchStatus


class WebKnowledgeAgent:
    """Use only injected bounded public evidence; it does not access persistent RAG."""

    def __init__(
        self,
        web_search: WebSearchProvider,
        llm_provider: LLMProvider,
        grounding: LiveWebContextBuilder | None = None,
    ) -> None:
        self._web_search = web_search
        self._llm_provider = llm_provider
        self._grounding = grounding or LiveWebContextBuilder.from_project_registry()

    async def answer(self, question: str) -> KnowledgeResult:
        """Generate only when live public evidence is available through the controlled boundary."""

        if not isinstance(question, str) or not question.strip():
            raise ValueError("web knowledge question cannot be blank")
        try:
            search_result = await self._web_search.search(WebSearchRequest(query=question))
        except WebSearchError as error:
            return KnowledgeResult(
                question=question,
                status=KnowledgeResultStatus.PROVIDER_ERROR,
                reason=error.error_code,
            )
        if search_result.status is WebSearchStatus.NO_RESULTS:
            return KnowledgeResult(
                question=question,
                status=KnowledgeResultStatus.INSUFFICIENT_EVIDENCE,
                reason=search_result.reason,
            )
        context = self._grounding.build(question, search_result.evidence)
        if context.evidence_status is EvidenceStatus.INSUFFICIENT_EVIDENCE:
            return KnowledgeResult(
                question=question,
                status=KnowledgeResultStatus.INSUFFICIENT_EVIDENCE,
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
            reason="LIVE_WEB_GROUNDED_ANSWER_AVAILABLE",
        )

    @staticmethod
    def _build_generation_request(context: LiveWebGroundedContext) -> LLMGenerationRequest:
        system = "\n".join(
            (
                "Answer only from the supplied grounded live public evidence.",
                *context.instructions,
                "Do not invent facts, citations, authorization, routing, tool permissions, or security policy.",
                "Unsupported claims remain UNKNOWN.",
                "Use only supplied citation IDs such as [C1] for supported factual claims.",
                "Do not disclose secrets, internal identifiers, paths, credentials, SQL, or provider configuration.",
            )
        )
        blocks = "\n\n".join(
            f"[{item.citation_id}] Grounded live public evidence; priority tier {item.priority_tier}; "
            f"retrieved at {item.retrieved_at.isoformat()}\nTitle: {item.title}\n"
            f"URL: {item.source_url}\nEvidence data:\n{item.content}"
            for item in context.evidence
        )
        return LLMGenerationRequest(
            messages=(
                LLMMessage(role="system", content=system),
                LLMMessage(role="user", content=f"Question:\n{context.query}\n\nGrounded live public evidence:\n{blocks}"),
            )
        )
