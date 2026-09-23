"""Bounded deterministic response for social and orientation turns."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConversationalResult(BaseModel):
    """Narrow result with no evidence, citations, or capability payloads."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: str = Field(min_length=1, max_length=300)
    reason: Literal["BOUNDED_CONVERSATIONAL_RESPONSE"]


def bounded_conversational_response() -> ConversationalResult:
    """Return a fixed public-safe orientation message without provider calls."""

    return ConversationalResult(
        answer=(
            "Olá! Posso ajudar com produtos e serviços Getnet, dúvidas de suporte, "
            "processos documentados e informações gerais. Como posso ajudar?"
        ),
        reason="BOUNDED_CONVERSATIONAL_RESPONSE",
    )
