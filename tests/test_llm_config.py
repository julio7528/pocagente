"""Focused configuration tests for Phase 9.2's DeepSeek boundary."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from apps.agent_api.app.llm.config import DeepSeekConfig, load_deepseek_config
from apps.agent_api.app.llm.deepseek import DeepSeekProvider
from apps.agent_api.app.llm.errors import LLMConfigurationError
from apps.agent_api.app.llm.factory import create_deepseek_provider


def test_deepseek_config_is_immutable_and_masks_its_api_key() -> None:
    config = DeepSeekConfig(api_key=SecretStr("unit-test-key"))

    assert "unit-test-key" not in repr(config)
    assert config.model == "deepseek-flash"
    assert config.chat_completions_url == "https://api.deepseek.com/chat/completions"
    with pytest.raises(ValidationError):
        config.model = "another-model"  # type: ignore[misc]


@pytest.mark.parametrize("key", ["", "   "])
def test_deepseek_config_rejects_blank_api_key(key: str) -> None:
    with pytest.raises(ValidationError, match="api key must not be empty"):
        DeepSeekConfig(api_key=SecretStr(key))


def test_load_deepseek_config_reads_only_approved_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "unit-test-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "configured-model")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.test/api")
    monkeypatch.setenv("DEEPSEEK_TIMEOUT_SECONDS", "12.5")

    config = load_deepseek_config()

    assert config.model == "configured-model"
    assert config.chat_completions_url == "https://example.test/api/chat/completions"
    assert config.timeout_seconds == 12.5


def test_missing_deepseek_key_returns_controlled_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(LLMConfigurationError) as captured:
        load_deepseek_config()

    assert captured.value.error_code == "llm_configuration_unavailable"
    assert "DEEPSEEK_API_KEY" not in str(captured.value)


def test_factory_composes_only_the_provider_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = DeepSeekConfig(api_key=SecretStr("unit-test-key"))
    monkeypatch.setattr("apps.agent_api.app.llm.factory.load_deepseek_config", lambda: expected)

    provider = create_deepseek_provider()

    assert isinstance(provider, DeepSeekProvider)
