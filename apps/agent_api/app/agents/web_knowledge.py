"""Knowledge generation over controlled, non-persistent live public web evidence."""

from __future__ import annotations

import re
from time import perf_counter

from apps.agent_api.app.agents.grounded_generation import (
    GroundedGenerationError,
    GroundedGenerationStatus,
    generate_grounded_outcome,
)
from apps.agent_api.app.agents.knowledge import KnowledgeResult, KnowledgeResultStatus
from apps.agent_api.app.llm.errors import LLMProviderError
from apps.agent_api.app.llm.models import LLMProvider
from apps.agent_api.app.rag.grounding import EvidenceStatus, LiveWebContextBuilder
from apps.agent_api.app.rag.scope import KnowledgeScope
from apps.agent_api.app.web.errors import WebSearchError
from apps.agent_api.app.web.models import WebSearchProvider, WebSearchRequest, WebSearchStatus
from apps.agent_api.app.telemetry import RuntimeEventKind, emit_runtime_event


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

    _WEATHER_PATTERN = re.compile(
        r"\b(?:weather|forecast|previs[aã]o\s+(?:do\s+)?tempo|vai\s+chover|chover[aá]?|temperatura)\b",
        re.IGNORECASE,
    )
    _LOCATION_PATTERN = re.compile(
        r"\b(?:in|at|near|em|no|na|perto\s+de|para)\s+"
        r"(?!my\b|your\b|here\b|aqui\b|minha\s+cidade\b|sua\s+cidade\b|amanh[aã]\b|hoje\b)"
        r"[a-zà-ÿ][a-zà-ÿ-]*(?:\s+[a-zà-ÿ][a-zà-ÿ-]*){0,3}\b",
        re.IGNORECASE,
    )

    async def answer(self, question: str, *, knowledge_scope: KnowledgeScope = KnowledgeScope.NONE) -> KnowledgeResult:
        """Generate only when live public evidence is available through the controlled boundary."""

        if not isinstance(question, str) or not question.strip():
            raise ValueError("web knowledge question cannot be blank")
        if self._WEATHER_PATTERN.search(question) and not self._LOCATION_PATTERN.search(question):
            emit_runtime_event(
                RuntimeEventKind.WEB_SEARCH,
                name="weather_forecast",
                value="SKIPPED_LOCATION_REQUIRED",
            )
            return KnowledgeResult(
                question=question,
                status=KnowledgeResultStatus.ANSWERED,
                answer="Para qual cidade ou região você quer a previsão do tempo?",
                reason="WEATHER_LOCATION_REQUIRED",
            )
        search_started_at = perf_counter()
        emit_runtime_event(RuntimeEventKind.WEB_SEARCH, value="STARTED")
        try:
            approved_domains = (
                getattr(self._grounding, "approved_public_domains", ())
                if knowledge_scope is KnowledgeScope.PUBLIC_GETNET
                else ()
            )
            search_result = await self._web_search.search(
                WebSearchRequest(query=question, include_domains=approved_domains)
            )
        except WebSearchError as error:
            emit_runtime_event(
                RuntimeEventKind.WEB_SEARCH,
                value="CONTROLLED_ERROR",
                elapsed_ms=int((perf_counter() - search_started_at) * 1000),
            )
            return KnowledgeResult(
                question=question,
                status=KnowledgeResultStatus.PROVIDER_ERROR,
                reason=error.error_code,
            )
        emit_runtime_event(
            RuntimeEventKind.WEB_SEARCH,
            value=search_result.status.value,
            count=len(search_result.evidence),
            elapsed_ms=int((perf_counter() - search_started_at) * 1000),
        )
        if search_result.status is WebSearchStatus.NO_RESULTS:
            return KnowledgeResult(
                question=question,
                status=KnowledgeResultStatus.INSUFFICIENT_EVIDENCE,
                reason=search_result.reason,
            )
        context = self._grounding.build(question, search_result.evidence)
        emit_runtime_event(
            RuntimeEventKind.GROUNDING,
            name="live_web",
            value=context.evidence_status.value,
            count=len(context.evidence),
        )
        if context.evidence_status is EvidenceStatus.INSUFFICIENT_EVIDENCE:
            return KnowledgeResult(
                question=question,
                status=KnowledgeResultStatus.INSUFFICIENT_EVIDENCE,
                reason=context.reason,
            )
        try:
            generated = await generate_grounded_outcome(
                self._llm_provider,
                question=context.query,
                grounding_instructions=context.instructions,
                evidence_blocks=tuple(
                    f"[{item.citation_id}] Grounded live public evidence; priority tier {item.priority_tier}; "
                    f"retrieved at {item.retrieved_at.isoformat()}\nTitle: {item.title}\n"
                    f"URL: {item.source_url}\nEvidence data:\n{item.content}"
                    for item in context.evidence
                ),
                available_citation_ids=tuple(item.citation_id for item in context.evidence),
            )
        except (LLMProviderError, GroundedGenerationError) as error:
            return KnowledgeResult(
                question=question,
                status=KnowledgeResultStatus.PROVIDER_ERROR,
                reason=getattr(error, "error_code", "invalid_grounded_generation"),
            )
        if generated.status is GroundedGenerationStatus.INSUFFICIENT_EVIDENCE:
            return KnowledgeResult(
                question=question,
                status=KnowledgeResultStatus.INSUFFICIENT_EVIDENCE,
                reason="GENERATION_INSUFFICIENT_EVIDENCE",
            )
        citations_by_id = {citation.id: citation for citation in context.citations}
        return KnowledgeResult(
            question=question,
            status=KnowledgeResultStatus.ANSWERED,
            answer=generated.answer,
            citations=tuple(citations_by_id[item] for item in generated.citation_ids),
            reason="LIVE_WEB_GROUNDED_ANSWER_AVAILABLE",
        )
