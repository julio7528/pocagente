"""Explicitly enabled real DeepSeek smoke test for the neutral provider boundary."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from apps.agent_api.app.llm.config import load_deepseek_config
from apps.agent_api.app.llm.deepseek import DeepSeekProvider
from apps.agent_api.app.llm.models import LLMGenerationRequest, LLMMessage
from tests.integration.deepseek_env import load_deepseek_environment


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DEEPSEEK_INTEGRATION") != "1",
    reason="set GETNET_RUN_DEEPSEEK_INTEGRATION=1 and DEEPSEEK_API_KEY to run DeepSeek smoke test",
)


@pytest.fixture(scope="module", autouse=True)
def load_local_deepseek_environment() -> None:
    """Load approved local provider settings only after opt-in selection."""

    load_deepseek_environment(Path(__file__).resolve().parents[2] / ".env")


def test_real_deepseek_provider_returns_neutral_result() -> None:
    provider = DeepSeekProvider(load_deepseek_config())

    result = asyncio.run(
        provider.generate(
            LLMGenerationRequest(
                messages=(
                    LLMMessage(
                        role="user",
                        content="Responda apenas com uma saudacao curta em portugues.",
                    ),
                ),
                max_output_tokens=32,
                temperature=0,
            )
        )
    )

    assert result.content.strip()
    assert set(result.model_dump()) == {"content", "finish_reason"}
