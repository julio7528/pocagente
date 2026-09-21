"""Async Tavily adapter that returns bounded provider-neutral public evidence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

from .config import TavilyConfig
from .errors import WebSearchResponseError, WebSearchTimeoutError, WebSearchUnavailableError
from .models import WebEvidence, WebSearchRequest, WebSearchResult, WebSearchStatus


class TavilyWebSearchProvider:
    """Controlled Tavily client; it neither persists nor interprets search results."""

    def __init__(self, config: TavilyConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._config = config
        self._transport = transport

    async def search(self, request: WebSearchRequest) -> WebSearchResult:
        payload = {
            "api_key": self._config.api_key.get_secret_value(),
            "query": request.query,
            "max_results": request.max_results,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
        }
        try:
            async with httpx.AsyncClient(timeout=self._config.timeout_seconds, transport=self._transport) as client:
                response = await client.post(str(self._config.base_url), json=payload)
                response.raise_for_status()
                body = response.json()
        except httpx.TimeoutException as error:
            raise WebSearchTimeoutError() from error
        except httpx.HTTPError as error:
            raise WebSearchUnavailableError() from error
        except (TypeError, ValueError) as error:
            raise WebSearchResponseError() from error
        return self._extract_result(body)

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
