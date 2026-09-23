"""DeepSeek implementation of the provider-neutral LLM generation contract."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from .config import DeepSeekConfig
from .errors import (
    LLMProviderResponseError,
    LLMProviderTimeoutError,
    LLMProviderUnavailableError,
)
from .models import LLMGenerationRequest, LLMGenerationResult


class DeepSeekProvider:
    """Minimal async DeepSeek adapter with no application or database knowledge."""

    def __init__(
        self,
        config: DeepSeekConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
        """Call DeepSeek and translate its response into the neutral result type."""

        payload: dict[str, object] = {
            "model": self._config.model,
            "messages": [message.model_dump() for message in request.messages],
        }
        if request.max_output_tokens is not None:
            payload["max_tokens"] = request.max_output_tokens
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.response_format is not None:
            payload["response_format"] = {"type": request.response_format}
        if request.reasoning_enabled is not None:
            payload["thinking"] = {"type": "enabled" if request.reasoning_enabled else "disabled"}

        headers = {
            "Authorization": f"Bearer {self._config.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(
                timeout=self._config.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    self._config.chat_completions_url,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
        except httpx.TimeoutException as error:
            raise LLMProviderTimeoutError() from error
        except httpx.HTTPError as error:
            raise LLMProviderUnavailableError() from error
        except (TypeError, ValueError) as error:
            raise LLMProviderResponseError() from error

        return self._extract_result(body)

    @staticmethod
    def _extract_result(body: object) -> LLMGenerationResult:
        """Extract only safe, provider-neutral completion fields from JSON."""

        if not isinstance(body, Mapping):
            raise LLMProviderResponseError()
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMProviderResponseError()
        first_choice = choices[0]
        if not isinstance(first_choice, Mapping):
            raise LLMProviderResponseError()
        message = first_choice.get("message")
        if not isinstance(message, Mapping):
            raise LLMProviderResponseError()
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LLMProviderResponseError()
        finish_reason = first_choice.get("finish_reason")
        if finish_reason is not None and not isinstance(finish_reason, str):
            raise LLMProviderResponseError()
        return LLMGenerationResult(content=content, finish_reason=finish_reason)
