"""Typed provider-neutral contracts for controlled live public evidence."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WebSearchStatus(StrEnum):
    SUCCESS = "SUCCESS"
    NO_RESULTS = "NO_RESULTS"


class WebSearchRequest(BaseModel):
    """Narrow query contract; callers cannot choose HTTP behavior or URLs."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=1000)
    max_results: int | None = Field(default=None, ge=1, le=5)
    include_domains: tuple[str, ...] = Field(default=(), max_length=20)

    @field_validator("include_domains")
    @classmethod
    def domains_are_hosts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}", domain) for domain in value):
            raise ValueError("include_domains must contain hostnames")
        return value


class WebEvidence(BaseModel):
    """One bounded, untrusted live public result; never persistent RAG provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    url: str = Field(min_length=1, max_length=2048)
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=4000)
    provider: str = Field(default="TAVILY", min_length=1)
    retrieved_at: datetime
    relevance_score: float | None = Field(default=None, ge=0, le=1)

    @field_validator("url")
    @classmethod
    def public_http_url(cls, value: str) -> str:
        if not value.startswith(("https://", "http://")):
            raise ValueError("web evidence URL must be HTTP or HTTPS")
        return value


class WebSearchResult(BaseModel):
    """Provider-neutral result with no transport headers, key, or raw response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: WebSearchStatus
    evidence: tuple[WebEvidence, ...] = ()
    reason: str = Field(min_length=1)

    @field_validator("evidence")
    @classmethod
    def status_matches_evidence(cls, value: tuple[WebEvidence, ...], info):
        status = info.data.get("status")
        if status is WebSearchStatus.SUCCESS and not value:
            raise ValueError("successful web results require evidence")
        if status is WebSearchStatus.NO_RESULTS and value:
            raise ValueError("no-results web response cannot contain evidence")
        return value


class WebSearchProvider(Protocol):
    """Application-facing live public search boundary."""

    async def search(self, request: WebSearchRequest) -> WebSearchResult:
        """Return bounded public evidence or raise a controlled web-search error."""
