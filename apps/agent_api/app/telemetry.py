"""Optional, secret-safe runtime events for local developer observability."""

from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar, Token
from enum import StrEnum
from typing import Iterator, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RuntimeEventKind(StrEnum):
    SECURITY = "SECURITY"
    SECURITY_SEMANTIC = "SECURITY_SEMANTIC"
    SECURITY_OUTPUT = "SECURITY_OUTPUT"
    CLASSIFIER = "CLASSIFIER"
    INTENT = "INTENT"
    ROUTER = "ROUTER"
    CAPABILITY_NEED = "CAPABILITY_NEED"
    KNOWLEDGE_SCOPE = "KNOWLEDGE_SCOPE"
    KNOWLEDGE_QUERY = "KNOWLEDGE_QUERY"
    WEB_POLICY = "WEB_POLICY"
    CAPABILITY = "CAPABILITY"
    OPS_AUTHORIZATION = "OPS_AUTHORIZATION"
    OPS_PLAN = "OPS_PLAN"
    OPS_TOOL = "OPS_TOOL"
    REPOSITORY = "REPOSITORY"
    RAG = "RAG"
    GROUNDING = "GROUNDING"
    WEB_SEARCH = "WEB_SEARCH"
    LLM = "LLM"
    PROVIDER_HTTP = "PROVIDER_HTTP"
    PROVIDER_PARSE = "PROVIDER_PARSE"
    PROVIDER_REQUEST = "PROVIDER_REQUEST"
    HUMAN = "HUMAN"
    SECURITY_AUDIT = "SECURITY_AUDIT"
    ORCHESTRATION = "ORCHESTRATION"


class RuntimeTelemetryEvent(BaseModel):
    """Closed fields only: no message, prompt, SQL, provider payload, or error text."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: RuntimeEventKind
    value: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, max_length=64)
    count: int | None = Field(default=None, ge=0)
    elapsed_ms: int | None = Field(default=None, ge=0)
    protocol_number: str | None = None
    limit: int | None = Field(default=None, ge=1, le=5)
    client_reused: bool | None = None
    input_characters: int | None = Field(default=None, ge=0)

    @field_validator("value")
    @classmethod
    def safe_value(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", value):
            raise ValueError("runtime event value must be a safe code")
        if value is not None and re.search(
            r"SECRET|PASSWORD|TOKEN|PROMPT|SQL|APIKEY|API_KEY|CONNECTION|REASONING|BEARER",
            value,
        ):
            raise ValueError("runtime event value contains a forbidden data category")
        return value

    @field_validator("name")
    @classmethod
    def safe_name(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", value):
            raise ValueError("runtime event name must be an identifier")
        if value is not None and re.search(
            r"SECRET|PASSWORD|TOKEN|PROMPT|SQL|APIKEY|API_KEY|CONNECTION|REASONING|BEARER",
            value,
            re.IGNORECASE,
        ):
            raise ValueError("runtime event name contains a forbidden data category")
        return value

    @field_validator("protocol_number")
    @classmethod
    def safe_protocol_number(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"POC-OPS-[0-9]{4}", value):
            raise ValueError("runtime event protocol selector is invalid")
        return value


class RuntimeTelemetrySink(Protocol):
    """A passive sink; exceptions from it are intentionally ignored."""

    def emit(self, event: RuntimeTelemetryEvent) -> None: ...


_CURRENT_SINK: ContextVar[RuntimeTelemetrySink | None] = ContextVar(
    "getnet_runtime_telemetry_sink", default=None
)


@contextmanager
def runtime_telemetry(sink: RuntimeTelemetrySink | None) -> Iterator[None]:
    """Install an observer for only the current async request and restore it safely."""

    token: Token[RuntimeTelemetrySink | None] = _CURRENT_SINK.set(sink)
    try:
        yield
    finally:
        _CURRENT_SINK.reset(token)


def emit_runtime_event(
    kind: RuntimeEventKind,
    *,
    value: str | None = None,
    name: str | None = None,
    count: int | None = None,
    elapsed_ms: int | None = None,
    protocol_number: str | None = None,
    limit: int | None = None,
    client_reused: bool | None = None,
    input_characters: int | None = None,
) -> None:
    """Emit a validated allowlisted event without affecting application behavior."""

    sink = _CURRENT_SINK.get()
    if sink is None:
        return
    try:
        event = RuntimeTelemetryEvent(
            kind=kind,
            value=value,
            name=name,
            count=count,
            elapsed_ms=elapsed_ms,
            protocol_number=protocol_number,
            limit=limit,
            client_reused=client_reused,
            input_characters=input_characters,
        )
        sink.emit(event)
    except Exception:
        # Observability must never change a business or security outcome.
        return
