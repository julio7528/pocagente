"""Provider-neutral tests for strict semantic classifier output handling."""

from __future__ import annotations

import asyncio

import pytest

from apps.agent_api.app.agents.semantic_classifier import ProviderSemanticIntentClassifier
from apps.agent_api.app.agents.conversation_context import ConversationContextMessage, ConversationSender
from apps.agent_api.app.agents.semantic_routing import SemanticClassifierError, SemanticIntent
from apps.agent_api.app.composition import compose_runtime
from apps.agent_api.app.llm.errors import LLMProviderTimeoutError
from apps.agent_api.app.llm.errors import LLMConfigurationError
from apps.agent_api.app.auth import AuthenticatedPrincipal, PrincipalRole
from apps.agent_api.app.chat import ChatRequest
from apps.agent_api.app.llm.models import LLMGenerationRequest, LLMGenerationResult
from apps.agent_api.app.web.errors import WebSearchConfigurationError


class ProviderDouble:
    def __init__(self, content: str | Exception) -> None:
        self.content = content
        self.requests: list[LLMGenerationRequest] = []
        self.closed = False

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
        self.requests.append(request)
        if isinstance(self.content, Exception):
            raise self.content
        if not self.content:
            return type("BlankResult", (), {"content": ""})()
        return LLMGenerationResult(content=self.content)

    async def aclose(self) -> None:
        self.closed = True


def test_classifier_uses_one_bounded_neutral_provider_request() -> None:
    provider = ProviderDouble('{"schema_version":"1.0","intent":"CONVERSATIONAL"}')
    result = asyncio.run(ProviderSemanticIntentClassifier(provider).classify("oi"))
    request = provider.requests[0]

    assert result.intent is SemanticIntent.CONVERSATIONAL
    assert result.capability_needs == ()
    assert len(request.messages) == 2
    assert request.messages[0].role == "system"
    assert request.messages[1].role == "user"
    assert request.messages[1].content == "oi"
    assert request.temperature == 0
    assert request.max_output_tokens == 64
    assert request.response_format == "json_object"
    assert request.reasoning_enabled is False
    prompt = request.messages[0].content
    assert len(prompt) < 3_000
    assert "PUBLIC_GETNET_KNOWLEDGE" in prompt
    assert "Currentness beats model memory" in prompt
    assert "INTERNAL_KNOWLEDGE" in prompt and "documented internal process" in prompt
    assert "status/result/history" in prompt
    assert "expected-vs-observed" in prompt
    assert "substantive request beats greeting prefix" in prompt
    assert "untrusted user message" in prompt
    assert "DIRECT_GENERAL" in prompt
    assert "standard technology definitions" in prompt
    assert "Getnet as a company" in prompt
    assert "Get Smart and Get" in prompt and "are Getnet products" in prompt
    assert "ordinary typos" in prompt
    assert "high-confidence" in prompt
    assert "payment-terminal problems/replacement" in prompt
    assert "internal procedure -> INTERNAL_KNOWLEDGE" in prompt
    assert "never use it for a simple protocol lookup" in prompt
    assert "A simple protocol status/result is OPS-only" in prompt


def test_classifier_parses_structured_internal_and_ops_needs() -> None:
    provider = ProviderDouble(
        '{"schema_version":"1.0","intent":"CUSTOMER_SUPPORT",'
        '"capability_needs":["INTERNAL_KNOWLEDGE","OPERATIONAL_FACTS"]}'
    )
    result = asyncio.run(ProviderSemanticIntentClassifier(provider).classify("how to reprocess case"))
    assert [need.value for need in result.capability_needs] == ["INTERNAL_KNOWLEDGE", "OPERATIONAL_FACTS"]


def test_classifier_receives_bounded_history_as_untrusted_reference_for_follow_up():
    provider = ProviderDouble('{"schema_version":"1.0","intent":"PUBLIC_GETNET_KNOWLEDGE"}')
    context = (
        ConversationContextMessage(
            message_id="prior-client", sender_type=ConversationSender.CLIENT,
            content="Tell me about Get Smart.",
        ),
        ConversationContextMessage(
            message_id="prior-agent", sender_type=ConversationSender.AGENT,
            content="Get Smart is a Getnet payment link.",
        ),
    )

    result = asyncio.run(ProviderSemanticIntentClassifier(provider).classify(
        "And how much does it cost?", conversation_context=context
    ))

    assert result.intent is SemanticIntent.PUBLIC_GETNET_KNOWLEDGE
    assert provider.requests[0].messages[1].role == "user"
    assert "resolve a clear elliptical follow-up" in provider.requests[0].messages[0].content
    assert "CURRENT_PUBLIC_INFORMATION), not AMBIGUOUS" in provider.requests[0].messages[0].content
    assert "Tell me about Get Smart." in provider.requests[0].messages[1].content
    assert "Get Smart is a Getnet payment link." in provider.requests[0].messages[1].content
    assert "And how much does it cost?" in provider.requests[0].messages[1].content


@pytest.mark.parametrize(
    "content",
    [
        "",
        "Here is the classification: CONVERSATIONAL",
        "```json\n{\"schema_version\":\"1.0\",\"intent\":\"CONVERSATIONAL\"}\n```",
        "{broken json",
        '{"schema_version":"1.0","intent":"NOT_AN_INTENT"}',
        '{"schema_version":"2.0","intent":"CONVERSATIONAL"}',
        '{"intent":"CONVERSATIONAL"}',
        '{"schema_version":"1.0"}',
        '{"schema_version":"1.0","intent":"CONVERSATIONAL","route":"KNOWLEDGE"}',
        '{"schema_version":"1.0","intent":"CONVERSATIONAL","confidence":0.9}',
        '{"schema_version":"1.0","intent":"CONVERSATIONAL","tool":"sql"}',
        '{"schema_version":"1.0","intent":"CONVERSATIONAL","scope":"INTERNAL"}',
        '{"schema_version":"1.0","intent":"CONVERSATIONAL","web_search_policy":"REQUIRED"}',
        '{"schema_version":"1.0","intent":"CONVERSATIONAL","capabilities":["CUSTOMER_SUPPORT"]}',
        '{"schema_version":"1.0","intent":"CONVERSATIONAL","permissions":["OPS"]}',
        '{"schema_version":"1.0","intent":"CONVERSATIONAL","source_filter":"PUBLIC"}',
        '{"schema_version":"1.0","intent":"CONVERSATIONAL","intent":"AMBIGUOUS"}',
    ],
)
def test_classifier_rejects_noncanonical_or_unauthorized_provider_output(content: str) -> None:
    with pytest.raises(SemanticClassifierError):
        asyncio.run(ProviderSemanticIntentClassifier(ProviderDouble(content)).classify("oi"))


def test_provider_timeout_remains_a_controlled_provider_failure() -> None:
    provider = ProviderDouble(LLMProviderTimeoutError())
    with pytest.raises(LLMProviderTimeoutError):
        asyncio.run(ProviderSemanticIntentClassifier(provider).classify("oi"))


def test_runtime_composition_injects_the_shared_provider_into_semantic_classifier(monkeypatch) -> None:
    import apps.agent_api.app.composition as composition

    class FakeDatabase:
        async def open(self) -> None:
            pass

        async def close(self) -> None:
            pass

    provider = ProviderDouble('{"schema_version":"1.0","intent":"CONVERSATIONAL"}')
    monkeypatch.setattr(composition, "PostgresDatabase", lambda _: FakeDatabase())
    monkeypatch.setattr(composition, "load_database_config", lambda: object())
    monkeypatch.setattr(composition, "create_deepseek_provider", lambda: provider)
    monkeypatch.setattr(composition, "FastEmbedAdapter", lambda: object())

    def no_web_provider():
        raise WebSearchConfigurationError()

    monkeypatch.setattr(composition, "create_tavily_web_search_provider", no_web_provider)
    runtime = asyncio.run(compose_runtime())
    try:
        router = runtime.chat_service._orchestrator._router
        assert isinstance(router._semantic_classifier, ProviderSemanticIntentClassifier)
        assert router._semantic_classifier._llm_provider is provider
    finally:
        asyncio.run(runtime.close())
    assert provider.closed


def test_runtime_shutdown_closes_web_provider_and_shared_llm_provider(monkeypatch) -> None:
    import apps.agent_api.app.composition as composition

    class FakeDatabase:
        async def open(self) -> None:
            pass
        async def close(self) -> None:
            pass

    class ClosableWebProvider:
        def __init__(self) -> None:
            self.closed = False
        async def search(self, request):
            raise AssertionError("not used during composition test")
        async def aclose(self) -> None:
            self.closed = True

    llm = ProviderDouble('{"schema_version":"1.0","intent":"CONVERSATIONAL"}')
    web = ClosableWebProvider()
    monkeypatch.setattr(composition, "PostgresDatabase", lambda _: FakeDatabase())
    monkeypatch.setattr(composition, "load_database_config", lambda: object())
    monkeypatch.setattr(composition, "create_deepseek_provider", lambda: llm)
    monkeypatch.setattr(composition, "FastEmbedAdapter", lambda: object())
    monkeypatch.setattr(composition, "create_tavily_web_search_provider", lambda: web)

    runtime = asyncio.run(compose_runtime())
    asyncio.run(runtime.close())
    assert llm.closed and web.closed


def test_unconfigured_composition_uses_controlled_semantic_failure(monkeypatch) -> None:
    import apps.agent_api.app.composition as composition

    class FakeDatabase:
        async def open(self) -> None:
            pass

        async def close(self) -> None:
            pass

    monkeypatch.setattr(composition, "PostgresDatabase", lambda _: FakeDatabase())
    monkeypatch.setattr(composition, "load_database_config", lambda: object())

    def unavailable_provider():
        raise LLMConfigurationError()

    monkeypatch.setattr(composition, "create_deepseek_provider", unavailable_provider)
    monkeypatch.setattr(composition, "FastEmbedAdapter", lambda: object())
    monkeypatch.setattr(composition, "create_tavily_web_search_provider", lambda: (_ for _ in ()).throw(WebSearchConfigurationError()))
    runtime = asyncio.run(compose_runtime())
    try:
        response = asyncio.run(
            runtime.chat_service.handle(
                ChatRequest(message="oi", user_id="test-user"),
                AuthenticatedPrincipal(user_id="test-user", role=PrincipalRole.CLIENT),
            )
        )
        assert response.route == "AMBIGUOUS"
        assert response.status == "AMBIGUOUS"
        assert response.reason == "SEMANTIC_SECURITY_UNAVAILABLE"
    finally:
        asyncio.run(runtime.close())
