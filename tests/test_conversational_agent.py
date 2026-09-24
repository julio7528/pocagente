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


def test_ambiguous_response_prompt_orients_naturally_and_defaults_language_neutrally() -> None:
    provider = RecordingProvider("Pode me dar um pouco mais de contexto?")
    asyncio.run(ConversationalAgent(provider).clarify("ronaldo"))
    assert provider.requests[0].reasoning_enabled is False
    instruction = provider.requests[0].messages[0].content
    assert "genuinely unclear" in instruction
    assert "Brazilian Portuguese" in instruction
    assert "When it fits naturally" in instruction


def test_direct_general_returns_typed_answer_without_tool_authority() -> None:
    provider = RecordingProvider('{"status":"ANSWERED","answer":"1 + 1 = 2."}')
    result = asyncio.run(ConversationalAgent(provider).answer_general("quanto é 1 + 1?"))
    assert result.status == "ANSWERED"
    assert result.answer == "1 + 1 = 2."
    request = provider.requests[0]
    assert request.response_format == "json_object"
    assert request.reasoning_enabled is False
    assert "no tools" in request.messages[0].content
    assert "after an off-domain answer" in request.messages[0].content
    assert "Response-style cue:" in request.messages[0].content
    assert len(request.messages) == 2


def test_direct_general_hands_currentness_off_without_fabricated_answer() -> None:
    provider = RecordingProvider('{"status":"REQUIRES_CURRENT_EVIDENCE","answer":null}')
    result = asyncio.run(ConversationalAgent(provider).answer_general("quem é presidente atualmente?"))
    assert result.status == "REQUIRES_CURRENT_EVIDENCE"
    assert result.answer is None


def test_direct_general_reasks_llm_when_domain_orientation_is_missing() -> None:
    class ScriptedProvider:
        def __init__(self):
            self.requests = []
            self.answers = iter((
                '{"status":"ANSWERED","answer":"2"}',
                '{"status":"ANSWERED","answer":"A resposta é 2. Se quiser, posso ajudar com temas da Getnet."}',
            ))

        async def generate(self, request):
            self.requests.append(request)
            return LLMGenerationResult(content=next(self.answers))

    provider = ScriptedProvider()
    result = asyncio.run(ConversationalAgent(provider).answer_general("1+1?"))
    assert result.answer == "A resposta é 2. Se quiser, posso ajudar com temas da Getnet."
    assert len(provider.requests) == 2
    assert "mandatory" in provider.requests[1].messages[0].content


def test_direct_general_provider_failure_is_typed() -> None:
    class FailingProvider:
        async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
            raise LLMProviderError()

    result = asyncio.run(ConversationalAgent(FailingProvider()).answer_general("quanto é 1 + 1?"))
    assert result.status == "PROVIDER_ERROR"
    assert result.answer is None


def test_recovery_response_receives_typed_safe_metadata_and_untrusted_question() -> None:
    provider = RecordingProvider("Entendi que você quer trocar um terminal Getnet com defeito, mas não encontrei evidências suficientes. Pode confirmar se é isso?")
    result = asyncio.run(ConversationalAgent(provider).recover(
        "quero trocar maquinha Getnet",
        route="KNOWLEDGE",
        failure_kind="INSUFFICIENT_EVIDENCE",
        interpretation="troca de terminal Getnet com defeito",
    ))
    assert result.reason == "LLM_FORMULATED_RESPONSE"
    assert "confirmar" in result.answer
    request = provider.requests[0]
    assert request.max_output_tokens == 128 and request.reasoning_enabled is False
    assert "INSUFFICIENT_EVIDENCE" in request.messages[1].content
    assert "troca de terminal Getnet com defeito" in request.messages[1].content
    assert "quero trocar maquinha Getnet" in request.messages[1].content
    assert "SQL" not in request.messages[1].content


def test_recovery_uses_safe_typed_fallback_when_generation_fails() -> None:
    class FailingProvider:
        async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
            del request
            raise LLMProviderError()

    result = asyncio.run(ConversationalAgent(FailingProvider()).recover(
        "Ronaldo", route="AMBIGUOUS", failure_kind="CLARIFICATION_REQUIRED"
    ))
    assert result.reason == "BOUNDED_CONVERSATIONAL_RESPONSE"
    assert "mais um detalhe" in result.answer


def test_ambiguous_response_retries_provider_once_before_fallback() -> None:
    class RecoveringProvider:
        def __init__(self) -> None:
            self.calls = 0

        async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
            del request
            self.calls += 1
            if self.calls == 1:
                raise LLMProviderError()
            return LLMGenerationResult(content="Sobre qual assunto você gostaria de saber?")

    provider = RecoveringProvider()
    result = asyncio.run(ConversationalAgent(provider).clarify("ronaldo"))
    assert result.reason == "LLM_FORMULATED_RESPONSE"
    assert result.answer == "Sobre qual assunto você gostaria de saber?"
    assert provider.calls == 2


def test_ambiguous_provider_failures_use_bounded_varied_safe_fallbacks() -> None:
    class FailingProvider:
        async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
            del request
            raise LLMProviderError()

    agent = ConversationalAgent(FailingProvider())
    results = [asyncio.run(agent.clarify("ronaldo")) for _ in range(5)]
    assert all(result.reason == "BOUNDED_CONVERSATIONAL_RESPONSE" for result in results)
    assert len({result.answer for result in results}) == 3
    assert all(1 <= len(result.answer) <= 300 for result in results)


def test_direct_general_cycles_non_template_style_cues() -> None:
    provider = RecordingProvider('{\"status\":\"ANSWERED\",\"answer\":\"2. Se quiser, posso falar sobre Getnet.\"}')
    agent = ConversationalAgent(provider)
    for _ in range(3):
        asyncio.run(agent.answer_general("1+1?"))
    prompts = [request.messages[0].content for request in provider.requests]
    assert len(set(prompts)) == 3
    assert all("Response-style cue:" in prompt for prompt in prompts)
    assert all("Pergunta:" not in prompt for prompt in prompts)
