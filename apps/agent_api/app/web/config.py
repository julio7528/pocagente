"""Validated Tavily configuration loaded from only approved environment variables."""

from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr, ValidationError, field_validator

from .errors import WebSearchConfigurationError


class TavilyConfig(BaseModel):
    """Immutable API configuration; SecretStr keeps the credential out of repr/dumps."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    api_key: SecretStr
    base_url: HttpUrl = "https://api.tavily.com/search"
    timeout_seconds: float = Field(default=20.0, gt=0, le=60)
    max_results: int = Field(default=1, ge=1, le=5)

    @field_validator("api_key")
    @classmethod
    def api_key_must_not_be_blank(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("api key must not be empty")
        return value


def load_tavily_config() -> TavilyConfig:
    """Load only approved Tavily settings and translate invalid values safely."""

    try:
        return TavilyConfig(
            api_key=os.environ.get("TAVILY_API_KEY"),
            base_url=os.getenv("TAVILY_BASE_URL", "https://api.tavily.com/search"),
            timeout_seconds=os.getenv("TAVILY_TIMEOUT_SECONDS", "20"),
            max_results=os.getenv("WEB_SEARCH_MAX_RESULTS", "1"),
        )
    except ValidationError as error:
        raise WebSearchConfigurationError() from error
