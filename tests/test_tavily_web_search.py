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
from apps.agent_api.app.telemetry import RuntimeEventKind, runtime_telemetry


def provider(handler: object) -> TavilyWebSearchProvider:
    return TavilyWebSearchProvider(
        TavilyConfig(api_key=SecretStr("unit-test-tavily-key")),
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


async def search_and_close(provider_instance: TavilyWebSearchProvider, request: WebSearchRequest):
    try:
        return await provider_instance.search(request)
    finally:
        await provider_instance.aclose()


def test_config_is_immutable_masks_key_and_loads_only_approved_values(monkeypatch: pytest.MonkeyPatch) -> None:
    config = TavilyConfig(api_key=SecretStr("unit-test-tavily-key"))
    assert "unit-test-tavily-key" not in repr(config)
    with pytest.raises(ValidationError):
        config.timeout_seconds = 2  # type: ignore[misc]
    monkeypatch.setenv("TAVILY_API_KEY", "unit-test-tavily-key")
    monkeypatch.setenv("TAVILY_BASE_URL", "https://example.test/search")
    monkeypatch.setenv("TAVILY_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("WEB_SEARCH_MAX_RESULTS", "2")
    loaded = load_tavily_config()
    assert str(loaded.base_url) == "https://example.test/search"
    assert loaded.max_results == 2
    assert config.max_results == 1


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
        assert payload["max_results"] == 1
        assert payload["include_answer"] is False
        assert payload["include_raw_content"] is False
        assert payload["api_key"] == "unit-test-tavily-key"
        return httpx.Response(200, json={"results": [{"url": "https://weather.example/a", "title": "Weather", "content": "Sunny", "score": 0.9}]})

    result = asyncio.run(search_and_close(provider(handler), WebSearchRequest(query="current weather")))
    assert result.status is WebSearchStatus.SUCCESS
    assert result.evidence[0].title == "Weather"
    assert "unit-test-tavily-key" not in result.model_dump_json()


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_http_errors_are_controlled_and_secret_safe(status: int) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="unit-test-tavily-key diagnostics")
    with pytest.raises(WebSearchUnavailableError) as captured:
        asyncio.run(search_and_close(provider(handler), WebSearchRequest(query="weather")))
    assert "unit-test-tavily-key" not in str(captured.value)


def test_timeout_and_malformed_or_empty_results_fail_controlled() -> None:
    async def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("unit-test-tavily-key")
    with pytest.raises(WebSearchTimeoutError):
        asyncio.run(search_and_close(provider(timeout), WebSearchRequest(query="weather")))
    async def malformed(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [{"url": "https://x", "title": "x"}]})
    with pytest.raises(WebSearchResponseError):
        asyncio.run(search_and_close(provider(malformed), WebSearchRequest(query="weather")))
    async def no_results(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []})
    result = asyncio.run(search_and_close(provider(no_results), WebSearchRequest(query="weather")))
    assert result.status is WebSearchStatus.NO_RESULTS


def test_web_contracts_are_strict_bounded_and_immutable() -> None:
    with pytest.raises(ValidationError):
        WebSearchRequest(query="q", max_results=6)
    with pytest.raises(ValidationError):
        WebEvidence(url="file:///secret", title="x", content="x", retrieved_at="2026-01-01T00:00:00Z")
    with pytest.raises(ValidationError):
        WebSearchRequest(query="x", arbitrary_url="https://evil.example")
    with pytest.raises(ValidationError):
        WebSearchRequest(query="x", max_results=0)
    with pytest.raises(ValidationError):
        WebSearchRequest(query="x", include_domains=("https://evil.example",))


@pytest.mark.parametrize("value", ["0", "6", "invalid"])
def test_web_result_count_configuration_is_bounded(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setenv("WEB_SEARCH_MAX_RESULTS", value)
    with pytest.raises(WebSearchConfigurationError):
        load_tavily_config()


def test_tavily_provider_latency_events_omit_key_query_and_response_content() -> None:
    class Collector:
        def __init__(self) -> None:
            self.events = []

        def emit(self, event) -> None:
            self.events.append(event)

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"results": [{"url": "https://example.test/", "title": "private title", "content": "private body"}]},
        )

    collector = Collector()
    with runtime_telemetry(collector):
        result = asyncio.run(search_and_close(provider(handler), WebSearchRequest(query="private query")))
    assert result.status is WebSearchStatus.SUCCESS
    assert [(event.kind, event.value) for event in collector.events] == [
        (RuntimeEventKind.PROVIDER_HTTP, "STARTED"),
        (RuntimeEventKind.PROVIDER_HTTP, "RESPONSE_RECEIVED"),
        (RuntimeEventKind.PROVIDER_PARSE, "STARTED"),
        (RuntimeEventKind.PROVIDER_PARSE, "COMPLETED"),
        (RuntimeEventKind.PROVIDER_REQUEST, "COMPLETED"),
    ]
    assert "unit-test-tavily-key" not in repr(collector.events)
    assert "private query" not in repr(collector.events)
    assert "private title" not in repr(collector.events)
    assert "private body" not in repr(collector.events)


def test_tavily_reuses_client_and_closes_idempotently() -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"results": [{"url": "https://example.test/", "title": "t", "content": "c"}]})

    async def scenario() -> None:
        instance = provider(handler)
        original_client = instance._client
        await instance.search(WebSearchRequest(query="one"))
        await instance.search(WebSearchRequest(query="two"))
        assert instance._client is original_client
        assert calls == 2
        await instance.aclose()
        await instance.aclose()
        assert original_client.is_closed
        with pytest.raises(WebSearchUnavailableError):
            await instance.search(WebSearchRequest(query="three"))

    asyncio.run(scenario())
