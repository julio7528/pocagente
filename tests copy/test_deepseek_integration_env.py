"""Unit tests for the opt-in DeepSeek integration environment loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.agent_api.app.llm.config import load_deepseek_config
from apps.agent_api.app.llm.errors import LLMConfigurationError
from tests.integration.deepseek_env import load_deepseek_environment


def test_loader_reads_only_approved_deepseek_variables(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        """
DEEPSEEK_API_KEY='fake-test-key'
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_BASE_URL=https://example.test/api
DEEPSEEK_TIMEOUT_SECONDS=12
POSTGRES_PASSWORD=must-not-load
UNRELATED_VALUE=must-not-load
""".strip(),
        encoding="utf-8",
    )
    environment: dict[str, str] = {}

    load_deepseek_environment(dotenv_path, environment=environment)

    assert environment == {
        "DEEPSEEK_API_KEY": "fake-test-key",
        "DEEPSEEK_MODEL": "deepseek-flash",
        "DEEPSEEK_BASE_URL": "https://example.test/api",
        "DEEPSEEK_TIMEOUT_SECONDS": "12",
    }


def test_loader_rejects_missing_dotenv_without_secret_details(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError) as captured:
        load_deepseek_environment(tmp_path / ".env", environment={})

    assert "key" not in str(captured.value).lower()


def test_blank_loaded_key_fails_through_controlled_configuration_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("DEEPSEEK_API_KEY=   ", encoding="utf-8")
    environment: dict[str, str] = {}

    load_deepseek_environment(dotenv_path, environment=environment)
    monkeypatch.setenv("DEEPSEEK_API_KEY", environment["DEEPSEEK_API_KEY"])

    with pytest.raises(LLMConfigurationError) as captured:
        load_deepseek_config()

    assert "fake" not in str(captured.value).lower()
    assert "DEEPSEEK_API_KEY" not in str(captured.value)
