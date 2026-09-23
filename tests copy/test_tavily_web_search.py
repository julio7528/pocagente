"""Mocked Phase 9.8 tests for the controlled Tavily public-evidence boundary."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from apps.agent_api.app.web.config import TavilyConfig, load_tavily_config
from apps.agent_api.app.web.errors import (
    WebSearchConfigurationError,
    WebSearchResponseError,
    WebSearchTimeoutError,
    WebSearchUnavailableError,
)
from apps.agent_api.app.web.models import WebEvidence, WebSearchRequest, WebSearchStatus
from apps.agent_api.app.web.tavily import TavilyWebSearchProvider


def provider(handler: object) -> TavilyWebSearchProvider:
    return TavilyWebSearchProvider(
        TavilyConfig(api_key=SecretStr("unit-test-tavily-key")),
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


def test_config_is_immutable_masks_key_and_loads_only_approved_values(monkeypatch: pytest.MonkeyPatch) -> None:
    config = TavilyConfig(api_key=SecretStr("unit-test-tavily-key"))
    assert "unit-test-tavily-key" not in repr(config)
    with pytest.raises(ValidationError):
        config.timeout_seconds = 2  # type: ignore[misc]
    monkeypatch.setenv("TAVILY_API_KEY", "unit-test-tavily-key")
    monkeypatch.setenv("TAVILY_BASE_URL", "https://example.test/search")
    monkeypatch.setenv("TAVILY_TIMEOUT_SECONDS", "12")
    assert str(load_tavily_config().base_url) == "https://example.test/search"


@pytest.mark.parametrize("key", ["", "  "])
def test_configuration_rejects_missing_or_blank_key_without_leakage(key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", key)
    with pytest.raises(WebSearchConfigurationError) as captured:
        load_tavily_config()
    assert "TAVILY_API_KEY" not in str(captured.value)
    assert "api key must not be empty" not in str(captured.value)


def test_tavily_adapter_returns_bounded_neutral_evidence() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["query"] == "current weather"
        assert payload["max_results"] == 3
        assert payload["include_answer"] is False
        assert payload["include_raw_content"] is False
        assert payload["api_key"] == "unit-test-tavily-key"
        return httpx.Response(200, json={"results": [{"url": "https://weather.example/a", "title": "Weather", "content": "Sunny", "score": 0.9}]})

    result = asyncio.run(provider(handler).search(WebSearchRequest(query="current weather")))
    assert result.status is WebSearchStatus.SUCCESS
    assert result.evidence[0].title == "Weather"
    assert "unit-test-tavily-key" not in result.model_dump_json()


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_http_errors_are_controlled_and_secret_safe(status: int) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="unit-test-tavily-key diagnostics")
    with pytest.raises(WebSearchUnavailableError) as captured:
        asyncio.run(provider(handler).search(WebSearchRequest(query="weather")))
    assert "unit-test-tavily-key" not in str(captured.value)


def test_timeout_and_malformed_or_empty_results_fail_controlled() -> None:
    async def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("unit-test-tavily-key")
    with pytest.raises(WebSearchTimeoutError):
        asyncio.run(provider(timeout).search(WebSearchRequest(query="weather")))
    async def malformed(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [{"url": "https://x", "title": "x"}]})
    with pytest.raises(WebSearchResponseError):
        asyncio.run(provider(malformed).search(WebSearchRequest(query="weather")))
    async def no_results(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []})
    result = asyncio.run(provider(no_results).search(WebSearchRequest(query="weather")))
    assert result.status is WebSearchStatus.NO_RESULTS


def test_web_contracts_are_strict_bounded_and_immutable() -> None:
    with pytest.raises(ValidationError):
        WebSearchRequest(query="q", max_results=6)
    with pytest.raises(ValidationError):
        WebEvidence(url="file:///secret", title="x", content="x", retrieved_at="2026-01-01T00:00:00Z")
    with pytest.raises(ValidationError):
        WebSearchRequest(query="x", arbitrary_url="https://evil.example")
