"""Async Tavily adapter that returns bounded provider-neutral public evidence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

from .config import TavilyConfig
from .errors import WebSearchResponseError, WebSearchTimeoutError, WebSearchUnavailableError
from .models import WebEvidence, WebSearchRequest, WebSearchResult, WebSearchStatus
from apps.agent_api.app.telemetry import RuntimeEventKind, emit_runtime_event
from time import perf_counter


class TavilyWebSearchProvider:
    """Controlled Tavily client; it neither persists nor interprets search results."""

    def __init__(self, config: TavilyConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._config = config
        self._transport = transport
        self._client = httpx.AsyncClient(timeout=self._config.timeout_seconds, transport=self._transport)
        self._request_count = 0
        self._closed = False

    async def aclose(self) -> None:
        """Close the application-scoped HTTP connection pool idempotently."""

        if self._closed:
            return
        self._closed = True
        await self._client.aclose()

    async def search(self, request: WebSearchRequest) -> WebSearchResult:
        request_started_at = perf_counter()
        if self._closed:
            raise WebSearchUnavailableError()
        client_reused = self._request_count > 0
        self._request_count += 1
        payload = {
            "api_key": self._config.api_key.get_secret_value(),
            "query": request.query,
            "max_results": request.max_results or self._config.max_results,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
        }
        if request.include_domains:
            payload["include_domains"] = list(request.include_domains)
        http_started_at = perf_counter()
        emit_runtime_event(
            RuntimeEventKind.PROVIDER_HTTP,
            name="tavily",
            value="STARTED",
            client_reused=client_reused,
        )
        parse_started_at: float | None = None
        try:
            response = await self._client.post(str(self._config.base_url), json=payload)
            response.raise_for_status()
            emit_runtime_event(
                RuntimeEventKind.PROVIDER_HTTP,
                name="tavily",
                value="RESPONSE_RECEIVED",
                elapsed_ms=int((perf_counter() - http_started_at) * 1000),
                client_reused=client_reused,
            )
            parse_started_at = perf_counter()
            emit_runtime_event(RuntimeEventKind.PROVIDER_PARSE, name="tavily", value="STARTED")
            body = response.json()
            result = self._extract_result(body)
            emit_runtime_event(
                RuntimeEventKind.PROVIDER_PARSE,
                name="tavily",
                value="COMPLETED",
                elapsed_ms=int((perf_counter() - parse_started_at) * 1000),
            )
        except httpx.TimeoutException as error:
            emit_runtime_event(RuntimeEventKind.PROVIDER_HTTP, name="tavily", value="CONTROLLED_ERROR", elapsed_ms=int((perf_counter() - http_started_at) * 1000), client_reused=client_reused)
            emit_runtime_event(RuntimeEventKind.PROVIDER_REQUEST, name="tavily", value="CONTROLLED_ERROR", elapsed_ms=int((perf_counter() - request_started_at) * 1000))
            raise WebSearchTimeoutError() from error
        except httpx.HTTPError as error:
            emit_runtime_event(RuntimeEventKind.PROVIDER_HTTP, name="tavily", value="CONTROLLED_ERROR", elapsed_ms=int((perf_counter() - http_started_at) * 1000), client_reused=client_reused)
            emit_runtime_event(RuntimeEventKind.PROVIDER_REQUEST, name="tavily", value="CONTROLLED_ERROR", elapsed_ms=int((perf_counter() - request_started_at) * 1000))
            raise WebSearchUnavailableError() from error
        except (TypeError, ValueError) as error:
            emit_runtime_event(RuntimeEventKind.PROVIDER_PARSE, name="tavily", value="CONTROLLED_ERROR", elapsed_ms=(int((perf_counter() - parse_started_at) * 1000) if parse_started_at is not None else 0))
            emit_runtime_event(RuntimeEventKind.PROVIDER_REQUEST, name="tavily", value="CONTROLLED_ERROR", elapsed_ms=int((perf_counter() - request_started_at) * 1000))
            raise WebSearchResponseError() from error
        except WebSearchResponseError:
            emit_runtime_event(RuntimeEventKind.PROVIDER_PARSE, name="tavily", value="CONTROLLED_ERROR", elapsed_ms=(int((perf_counter() - parse_started_at) * 1000) if parse_started_at is not None else 0))
            emit_runtime_event(RuntimeEventKind.PROVIDER_REQUEST, name="tavily", value="CONTROLLED_ERROR", elapsed_ms=int((perf_counter() - request_started_at) * 1000))
            raise
        emit_runtime_event(
            RuntimeEventKind.PROVIDER_REQUEST,
            name="tavily",
            value="COMPLETED",
            elapsed_ms=int((perf_counter() - request_started_at) * 1000),
        )
        return result

    @staticmethod
    def _extract_result(body: object) -> WebSearchResult:
        if not isinstance(body, Mapping):
            raise WebSearchResponseError()
        raw_results = body.get("results")
        if not isinstance(raw_results, list):
            raise WebSearchResponseError()
        evidence: list[WebEvidence] = []
        retrieved_at = datetime.now(UTC)
        for raw in raw_results[:5]:
            if not isinstance(raw, Mapping):
                raise WebSearchResponseError()
            url, title, content = raw.get("url"), raw.get("title"), raw.get("content")
            if not all(isinstance(value, str) and value.strip() for value in (url, title, content)):
                raise WebSearchResponseError()
            score = raw.get("score")
            if score is not None and (not isinstance(score, (int, float)) or isinstance(score, bool)):
                raise WebSearchResponseError()
            try:
                evidence.append(
                    WebEvidence(
                        url=url,
                        title=title,
                        content=content[:4000],
                        retrieved_at=retrieved_at,
                        relevance_score=float(score) if score is not None else None,
                    )
                )
            except ValueError as error:
                raise WebSearchResponseError() from error
        if not evidence:
            return WebSearchResult(status=WebSearchStatus.NO_RESULTS, reason="WEB_SEARCH_NO_RESULTS")
        return WebSearchResult(
            status=WebSearchStatus.SUCCESS,
            evidence=tuple(evidence),
            reason="WEB_SEARCH_EVIDENCE_AVAILABLE",
        )
