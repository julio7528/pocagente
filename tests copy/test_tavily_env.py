"""Unit checks for the allowlisted Tavily opt-in integration loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.tavily_env import load_tavily_environment


def test_loader_reads_only_allowlisted_tavily_values_and_unquotes(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text('TAVILY_API_KEY="fake-key"\nTAVILY_TIMEOUT_SECONDS=9\nOTHER_SECRET=blocked\n', encoding="utf-8")
    target: dict[str, str] = {}
    load_tavily_environment(dotenv, environment=target)
    assert target == {"TAVILY_API_KEY": "fake-key", "TAVILY_TIMEOUT_SECONDS": "9"}


def test_loader_requires_file_without_exposing_expected_key_name(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError) as captured:
        load_tavily_environment(tmp_path / ".env", environment={})
    assert "TAVILY_API_KEY" not in str(captured.value)
