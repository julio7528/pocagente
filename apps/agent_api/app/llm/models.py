"""Typed provider-neutral contracts used by future application capabilities."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LLMMessage(BaseModel):
    """One provider-neutral conversational input message."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("LLM message content cannot be blank")
        return value


class LLMGenerationRequest(BaseModel):
    """Provider-neutral generation request with no provider-specific payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    messages: tuple[LLMMessage, ...] = Field(min_length=1)
    max_output_tokens: int | None = Field(default=None, ge=1)
    temperature: float | None = Field(default=None, ge=0, le=2)


class LLMGenerationResult(BaseModel):
    """Provider-neutral successful generation result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content: str = Field(min_length=1)
    finish_reason: str | None = None

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("LLM generation content cannot be blank")
        return value


class LLMProvider(Protocol):
    """Async provider-neutral interface future agents may depend upon."""

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
        """Generate a provider-neutral result or raise a controlled provider error."""
