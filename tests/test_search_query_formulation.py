from __future__ import annotations

import asyncio

import pytest

from apps.agent_api.app.agents.search_query_formulation import (
    SearchQueryDecision,
    SemanticSearchQueryFormulator,
)
from apps.agent_api.app.llm.models import LLMGenerationRequest, LLMGenerationResult


class Provider:
    def __init__(self, content: str):
        self.content = content
        self.requests: list[LLMGenerationRequest] = []

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
        self.requests.append(request)
        return LLMGenerationResult(content=self.content)


@pytest.mark.parametrize(
    ("question", "normalized"),
    [
        ("quero trocar uma maquinha com defeito da getnet", "troca de maquininha Getnet com defeito suporte"),
        ("minha maquinina Getnet parou de funcionar", "maquininha Getnet com defeito"),
        ("como troco uma maquineta getnet com problema?", "troca de terminal Getnet com problema"),
    ],
)
def test_public_query_formulator_is_bounded_and_has_no_answer_authority(question: str, normalized: str) -> None:
    provider = Provider('{"status":"NORMALIZED","query":"' + normalized + '"}')
    result = asyncio.run(SemanticSearchQueryFormulator(provider).formulate(question))
    assert result == normalized
    request = provider.requests[0]
    assert request.max_output_tokens == 96
    assert request.response_format == "json_object" and request.reasoning_enabled is False
    assert len(request.messages) == 2
    assert request.messages[1].content == question
    assert "Do not add facts" in request.messages[0].content
    assert "do not answer" in request.messages[0].content


@pytest.mark.parametrize(
    "content",
    [
        '{"status":"UNCERTAIN","query":null}',
        '{"status":"NORMALIZED","query":""}',
        '{"status":"NORMALIZED","query":"SELECT * FROM ops.service_requests"}',
        '{"status":"NORMALIZED","query":"query","route":"OPS"}',
        "not-json",
    ],
)
def test_query_formulation_rejects_uncertain_or_unauthorized_payload(content: str) -> None:
    assert SearchQueryDecision.validate_content(content).status == "UNCERTAIN"


def test_formulator_falls_back_to_original_query_on_provider_error() -> None:
    class FailingProvider:
        async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
            del request
            raise RuntimeError("provider details must not escape")

    assert asyncio.run(SemanticSearchQueryFormulator(FailingProvider()).formulate("maquinha Getnet")) is None
