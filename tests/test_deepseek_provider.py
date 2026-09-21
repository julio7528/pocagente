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


def request() -> LLMGenerationRequest:
    return LLMGenerationRequest(messages=(LLMMessage(role="user", content="Teste unitario."),))


def provider(handler: object) -> DeepSeekProvider:
    return DeepSeekProvider(
        DeepSeekConfig(api_key=SecretStr("unit-test-key")),
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


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

    result = asyncio.run(provider(handler).generate(request()))

    assert result.content == "Resposta segura."
    assert result.finish_reason == "stop"
    assert set(result.model_dump()) == {"content", "finish_reason"}


def test_timeout_uses_controlled_error_without_key_leakage() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("unit-test-key")

    with pytest.raises(LLMProviderTimeoutError) as captured:
        asyncio.run(provider(handler).generate(request()))

    assert "unit-test-key" not in str(captured.value)


def test_http_failure_uses_controlled_error_without_provider_diagnostics() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unit-test-key rejected")

    with pytest.raises(LLMProviderUnavailableError) as captured:
        asyncio.run(provider(handler).generate(request()))

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
        asyncio.run(provider(handler).generate(request()))


def test_neutral_contracts_are_strict_immutable_and_reject_blank_content() -> None:
    with pytest.raises(ValidationError, match="cannot be blank"):
        LLMMessage(role="user", content="  ")
    with pytest.raises(ValidationError):
        LLMGenerationRequest(messages=())

    message = LLMMessage(role="user", content="Preserve content")
    with pytest.raises(ValidationError):
        message.role = "system"  # type: ignore[misc]
