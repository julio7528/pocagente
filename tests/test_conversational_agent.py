"""Focused tests for provider-formulated, capability-free conversation."""

from __future__ import annotations

import asyncio

from apps.agent_api.app.agents.conversational import ConversationalAgent
from apps.agent_api.app.llm.errors import LLMProviderError
from apps.agent_api.app.llm.models import LLMGenerationRequest, LLMGenerationResult


class RecordingProvider:
    def __init__(self, content: str = "Oi! Tudo bem? Como posso ajudar?") -> None:
        self.content = content
        self.requests: list[LLMGenerationRequest] = []

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
        self.requests.append(request)
        return LLMGenerationResult(content=self.content)


def test_conversation_uses_shared_provider_without_json_or_capability_authority() -> None:
    provider = RecordingProvider()
    result = asyncio.run(ConversationalAgent(provider).respond("oiiii"))

    assert result.answer == "Oi! Tudo bem? Como posso ajudar?"
    assert result.reason == "LLM_FORMULATED_RESPONSE"
    request = provider.requests[0]
    assert request.response_format is None
    assert request.max_output_tokens == 160
    assert "not use tools" in request.messages[0].content
    assert request.messages[1].content == "oiiii"


def test_conversation_trims_bounded_provider_output() -> None:
    result = asyncio.run(ConversationalAgent(RecordingProvider("  Olá!  ")).respond("oi"))
    assert result.answer == "Olá!"


def test_conversation_uses_fallback_when_provider_exceeds_output_bound() -> None:
    result = asyncio.run(ConversationalAgent(RecordingProvider("x" * 301)).respond("o que você faz?"))
    assert result.reason == "BOUNDED_CONVERSATIONAL_RESPONSE"


def test_conversation_uses_fallback_when_provider_stops_on_a_function_word() -> None:
    result = asyncio.run(ConversationalAgent(RecordingProvider("Posso ajudar com produtos Getnet e")).respond("oi"))
    assert result.reason == "BOUNDED_CONVERSATIONAL_RESPONSE"


def test_conversation_keeps_generated_complete_sentence_and_discards_cutoff_fragment() -> None:
    result = asyncio.run(ConversationalAgent(RecordingProvider("Olá! Se precisar, verifico o")).respond("oi"))
    assert result.reason == "LLM_FORMULATED_RESPONSE"
    assert result.answer == "Olá!"


def test_conversation_uses_deterministic_fallback_when_provider_fails() -> None:
    class FailingProvider:
        async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
            del request
            raise LLMProviderError()

    result = asyncio.run(ConversationalAgent(FailingProvider()).respond("boa noite"))
    assert result.reason == "BOUNDED_CONVERSATIONAL_RESPONSE"
    assert "Getnet" in result.answer


def test_conversation_retries_once_after_provider_failure() -> None:
    class RecoveringProvider:
        def __init__(self) -> None:
            self.calls = 0

        async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
            del request
            self.calls += 1
            if self.calls == 1:
                raise LLMProviderError()
            return LLMGenerationResult(content="Posso ajudar com Getnet. O que você precisa?")

    provider = RecoveringProvider()
    result = asyncio.run(ConversationalAgent(provider).respond("o que você consegue fazer?"))
    assert result.reason == "LLM_FORMULATED_RESPONSE"
    assert result.answer == "Posso ajudar com Getnet. O que você precisa?"
    assert provider.calls == 2
