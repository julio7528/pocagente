"""Validated runtime configuration for the initial DeepSeek provider."""

from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr, ValidationError, field_validator

from .errors import LLMConfigurationError


class DeepSeekConfig(BaseModel):
    """Immutable DeepSeek configuration loaded only from approved variables."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    api_key: SecretStr
    model: str = Field(default="deepseek-flash", min_length=1)
    base_url: HttpUrl = "https://api.deepseek.com"
    timeout_seconds: float = Field(default=30.0, gt=0, le=120)

    @field_validator("api_key")
    @classmethod
    def api_key_must_not_be_blank(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("api key must not be empty")
        return value

    @property
    def chat_completions_url(self) -> str:
        """Return the fixed DeepSeek-compatible chat-completions endpoint."""

        return f"{str(self.base_url).rstrip('/')}/chat/completions"


def load_deepseek_config() -> DeepSeekConfig:
    """Load only the approved DeepSeek variables without exposing their values."""

    try:
        return DeepSeekConfig(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            timeout_seconds=os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "30"),
        )
    except ValidationError as error:
        raise LLMConfigurationError() from error
