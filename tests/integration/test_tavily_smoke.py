"""Explicit opt-in smoke for the real Tavily boundary; never runs in normal pytest."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from apps.agent_api.app.web.config import load_tavily_config
from apps.agent_api.app.web.tavily import TavilyWebSearchProvider
from apps.agent_api.app.web.models import WebSearchRequest, WebSearchStatus
from tests.integration.tavily_env import load_tavily_environment


pytestmark = pytest.mark.skipif(os.getenv("GETNET_RUN_TAVILY_INTEGRATION") != "1", reason="Tavily integration is opt-in")


@pytest.fixture(scope="module", autouse=True)
def load_local_tavily_environment() -> None:
    load_tavily_environment(Path(__file__).resolve().parents[2] / ".env")
    if not os.getenv("TAVILY_API_KEY", "").strip():
        pytest.skip("Tavily API key is unavailable for the opt-in smoke test")


def test_real_tavily_public_current_information_smoke() -> None:
    config = load_tavily_config()
    result = asyncio.run(
        TavilyWebSearchProvider(config).search(WebSearchRequest(query="current weather forecast Porto Alegre", max_results=2))
    )
    assert result.status is WebSearchStatus.SUCCESS
    assert result.evidence
    assert all(item.url and item.title and item.content for item in result.evidence)
    assert config.api_key.get_secret_value() not in result.model_dump_json()
