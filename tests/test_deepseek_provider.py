"""Mocked tests for the initial DeepSeek adapter and neutral contracts."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from apps.agent_api.app.llm.config import DeepSeekConfig
from apps.agent_api.app.llm.deepseek import DeepSeekProvider
from apps.agent_api.app.llm.errors import (
    LLMProviderResponseError,
    LLMProviderTimeoutError,
    LLMProviderUnavailableError,
)
from apps.agent_api.app.llm.models import LLMGenerationRequest, LLMMessage
from apps.agent_api.app.telemetry import RuntimeEventKind, runtime_telemetry


def request() -> LLMGenerationRequest:
    return LLMGenerationRequest(messages=(LLMMessage(role="user", content="Teste unitario."),))


def provider(handler: object) -> DeepSeekProvider:
    return DeepSeekProvider(
        DeepSeekConfig(api_key=SecretStr("unit-test-key")),
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


async def generate_and_close(provider_instance: DeepSeekProvider, generation_request: LLMGenerationRequest):
    try:
        return await provider_instance.generate(generation_request)
    finally:
        await provider_instance.aclose()


def test_deepseek_provider_returns_neutral_generation_result() -> None:
    async def handler(http_request: httpx.Request) -> httpx.Response:
        assert http_request.url == "https://api.deepseek.com/chat/completions"
        assert http_request.headers["Authorization"] == "Bearer unit-test-key"
        payload = json.loads(http_request.content)
        assert payload == {
            "model": "deepseek-flash",
            "messages": [{"role": "user", "content": "Teste unitario."}],
        }
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "Resposta segura."}, "finish_reason": "stop"}
                ],
                "provider_metadata": {"must_not_escape": True},
            },
        )

    result = asyncio.run(generate_and_close(provider(handler), request()))

    assert result.content == "Resposta segura."
    assert result.finish_reason == "stop"
    assert set(result.model_dump()) == {"content", "finish_reason"}


def test_deepseek_provider_maps_neutral_json_mode_to_provider_request() -> None:
    async def handler(http_request: httpx.Request) -> httpx.Response:
        payload = json.loads(http_request.content)
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["thinking"] == {"type": "disabled"}
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]})

    request_with_json = LLMGenerationRequest(
        messages=(LLMMessage(role="user", content="Return JSON."),),
        response_format="json_object",
        reasoning_enabled=False,
    )
    result = asyncio.run(generate_and_close(provider(handler), request_with_json))
    assert result.content == "{}"


def test_timeout_uses_controlled_error_without_key_leakage() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("unit-test-key")

    with pytest.raises(LLMProviderTimeoutError) as captured:
        asyncio.run(generate_and_close(provider(handler), request()))

    assert "unit-test-key" not in str(captured.value)


def test_http_failure_uses_controlled_error_without_provider_diagnostics() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unit-test-key rejected")

    with pytest.raises(LLMProviderUnavailableError) as captured:
        asyncio.run(generate_and_close(provider(handler), request()))

    assert "unit-test-key" not in str(captured.value)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {"content": "   "}}]},
        {"choices": [{"message": {"content": "valid"}, "finish_reason": 1}]},
    ],
)
def test_malformed_response_never_becomes_generated_content(body: object) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    with pytest.raises(LLMProviderResponseError):
        asyncio.run(generate_and_close(provider(handler), request()))


def test_neutral_contracts_are_strict_immutable_and_reject_blank_content() -> None:
    with pytest.raises(ValidationError, match="cannot be blank"):
        LLMMessage(role="user", content="  ")
    with pytest.raises(ValidationError):
        LLMGenerationRequest(messages=())

    message = LLMMessage(role="user", content="Preserve content")
    with pytest.raises(ValidationError):
        message.role = "system"  # type: ignore[misc]


def test_provider_latency_events_are_stage_timed_and_secret_safe() -> None:
    class Collector:
        def __init__(self) -> None:
            self.events = []

        def emit(self, event) -> None:
            self.events.append(event)

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "safe"}}]})

    collector = Collector()
    with runtime_telemetry(collector):
        result = asyncio.run(generate_and_close(provider(handler), request()))

    assert result.content == "safe"
    assert [(event.kind, event.value) for event in collector.events] == [
        (RuntimeEventKind.PROVIDER_HTTP, "STARTED"),
        (RuntimeEventKind.PROVIDER_HTTP, "RESPONSE_RECEIVED"),
        (RuntimeEventKind.PROVIDER_PARSE, "STARTED"),
        (RuntimeEventKind.PROVIDER_PARSE, "COMPLETED"),
        (RuntimeEventKind.PROVIDER_REQUEST, "COMPLETED"),
    ]
    assert all(
        event.elapsed_ms is not None
        for event in collector.events
        if event.value in {"RESPONSE_RECEIVED", "COMPLETED"}
    )
    assert "unit-test-key" not in repr(collector.events)
    assert "Teste unitario" not in repr(collector.events)


def test_deepseek_reuses_one_client_and_closes_idempotently() -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"choices": [{"message": {"content": "safe"}}]})

    async def scenario() -> None:
        instance = provider(handler)
        original_client = instance._client
        collector = type("Collector", (), {"events": [], "emit": lambda self, event: self.events.append(event)})()
        with runtime_telemetry(collector):
            await instance.generate(request())
            await instance.generate(request())
        assert instance._client is original_client
        assert calls == 2
        assert [event.client_reused for event in collector.events if event.kind is RuntimeEventKind.PROVIDER_HTTP and event.value == "STARTED"] == [False, True]
        await instance.aclose()
        await instance.aclose()
        assert original_client.is_closed
        with pytest.raises(LLMProviderUnavailableError):
            await instance.generate(request())

    asyncio.run(scenario())
