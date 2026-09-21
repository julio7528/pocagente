"""Explicit opt-in Phase 9.8 public-current-information end-to-end smoke."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from apps.agent_api.app.agents.knowledge import KnowledgeResult, KnowledgeResultStatus
from apps.agent_api.app.agents.orchestration import LangGraphOrchestrator, OrchestrationRequest
from apps.agent_api.app.agents.router import RouterAgent
from apps.agent_api.app.agents.web_knowledge import WebKnowledgeAgent
from apps.agent_api.app.llm.factory import create_deepseek_provider
from apps.agent_api.app.web.factory import create_tavily_web_search_provider
from tests.integration.deepseek_env import load_deepseek_environment
from tests.integration.tavily_env import load_tavily_environment


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_TAVILY_INTEGRATION") != "1" or os.getenv("GETNET_RUN_DEEPSEEK_INTEGRATION") != "1",
    reason="Tavily and DeepSeek integration is explicitly opt-in",
)


@pytest.fixture(scope="module", autouse=True)
def load_local_provider_environment() -> None:
    dotenv = Path(__file__).resolve().parents[2] / ".env"
    load_tavily_environment(dotenv)
    load_deepseek_environment(dotenv)
    if not os.getenv("TAVILY_API_KEY", "").strip():
        pytest.skip("Tavily API key is unavailable for the opt-in smoke test")


class NoPersistentKnowledge:
    async def answer(self, question: str) -> KnowledgeResult:
        return KnowledgeResult(question=question, status=KnowledgeResultStatus.INSUFFICIENT_EVIDENCE, reason="NOT_USED_FOR_CURRENT_WEB")


class NoSupport:
    async def answer(self, _):
        raise AssertionError("current public web smoke must not invoke Customer Support")


def test_real_current_public_web_knowledge_path() -> None:
    graph = LangGraphOrchestrator(
        RouterAgent(),
        NoPersistentKnowledge(),
        NoSupport(),
        WebKnowledgeAgent(create_tavily_web_search_provider(), create_deepseek_provider()),
    )
    result = asyncio.run(graph.execute(OrchestrationRequest(message="What's the weather forecast in Porto Alegre tomorrow?")))
    assert result.knowledge_result is not None
    assert result.knowledge_result.answer
    assert result.live_web_evidence_used is True
    assert result.knowledge_result.citations
    serialized = result.model_dump_json().lower()
    assert "api_key" not in serialized
    assert "password" not in serialized
