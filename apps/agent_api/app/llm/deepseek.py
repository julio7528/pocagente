"""DeepSeek implementation of the provider-neutral LLM generation contract."""

from __future__ import annotations

from collections.abc import Mapping
from time import perf_counter
from typing import Any

import httpx

from .config import DeepSeekConfig
from .errors import (
    LLMProviderResponseError,
    LLMProviderTimeoutError,
    LLMProviderUnavailableError,
)
from .models import LLMGenerationRequest, LLMGenerationResult
from apps.agent_api.app.telemetry import RuntimeEventKind, emit_runtime_event


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
        self._client = httpx.AsyncClient(
            timeout=self._config.timeout_seconds,
            transport=self._transport,
        )
        self._request_count = 0
        self._closed = False

    async def aclose(self) -> None:
        """Close the application-scoped connection pool; safe to call repeatedly."""

        if self._closed:
            return
        self._closed = True
        await self._client.aclose()

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
        """Call DeepSeek and translate its response into the neutral result type."""

        request_started_at = perf_counter()
        if self._closed:
            raise LLMProviderUnavailableError()
        client_reused = self._request_count > 0
        self._request_count += 1

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

        http_started_at = perf_counter()
        emit_runtime_event(
            RuntimeEventKind.PROVIDER_HTTP,
            name="deepseek",
            value="STARTED",
            client_reused=client_reused,
            input_characters=sum(len(message.content) for message in request.messages),
        )
        parse_started_at: float | None = None
        try:
            response = await self._client.post(
                self._config.chat_completions_url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            emit_runtime_event(
                RuntimeEventKind.PROVIDER_HTTP,
                name="deepseek",
                value="RESPONSE_RECEIVED",
                elapsed_ms=int((perf_counter() - http_started_at) * 1000),
                client_reused=client_reused,
            )
            parse_started_at = perf_counter()
            emit_runtime_event(
                RuntimeEventKind.PROVIDER_PARSE,
                name="deepseek",
                value="STARTED",
            )
            try:
                body = response.json()
                result = self._extract_result(body)
            except LLMProviderResponseError:
                emit_runtime_event(
                    RuntimeEventKind.PROVIDER_PARSE,
                    name="deepseek",
                    value="CONTROLLED_ERROR",
                    elapsed_ms=int((perf_counter() - parse_started_at) * 1000),
                )
                raise
            emit_runtime_event(
                RuntimeEventKind.PROVIDER_PARSE,
                name="deepseek",
                value="COMPLETED",
                elapsed_ms=int((perf_counter() - parse_started_at) * 1000),
            )
        except httpx.TimeoutException as error:
            emit_runtime_event(RuntimeEventKind.PROVIDER_HTTP, name="deepseek", value="CONTROLLED_ERROR", elapsed_ms=int((perf_counter() - http_started_at) * 1000), client_reused=client_reused)
            emit_runtime_event(RuntimeEventKind.PROVIDER_REQUEST, name="deepseek", value="CONTROLLED_ERROR", elapsed_ms=int((perf_counter() - request_started_at) * 1000))
            raise LLMProviderTimeoutError() from error
        except httpx.HTTPError as error:
            emit_runtime_event(RuntimeEventKind.PROVIDER_HTTP, name="deepseek", value="CONTROLLED_ERROR", elapsed_ms=int((perf_counter() - http_started_at) * 1000), client_reused=client_reused)
            emit_runtime_event(RuntimeEventKind.PROVIDER_REQUEST, name="deepseek", value="CONTROLLED_ERROR", elapsed_ms=int((perf_counter() - request_started_at) * 1000))
            raise LLMProviderUnavailableError() from error
        except LLMProviderResponseError:
            emit_runtime_event(RuntimeEventKind.PROVIDER_REQUEST, name="deepseek", value="CONTROLLED_ERROR", elapsed_ms=int((perf_counter() - request_started_at) * 1000))
            raise
        except (TypeError, ValueError) as error:
            emit_runtime_event(
                RuntimeEventKind.PROVIDER_PARSE,
                name="deepseek",
                value="CONTROLLED_ERROR",
                elapsed_ms=(int((perf_counter() - parse_started_at) * 1000) if parse_started_at is not None else 0),
            )
            emit_runtime_event(RuntimeEventKind.PROVIDER_REQUEST, name="deepseek", value="CONTROLLED_ERROR", elapsed_ms=int((perf_counter() - request_started_at) * 1000))
            raise LLMProviderResponseError() from error

        emit_runtime_event(
            RuntimeEventKind.PROVIDER_REQUEST,
            name="deepseek",
            value="COMPLETED",
            elapsed_ms=int((perf_counter() - request_started_at) * 1000),
        )
        return result

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
