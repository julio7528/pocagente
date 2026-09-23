"""Controlled local Tavily configuration loading for explicitly enabled tests."""

from __future__ import annotations

import os
from collections.abc import MutableMapping
from pathlib import Path


TAVILY_ENVIRONMENT_KEYS = frozenset({"TAVILY_API_KEY", "TAVILY_BASE_URL", "TAVILY_TIMEOUT_SECONDS"})


def load_tavily_environment(dotenv_path: Path, *, environment: MutableMapping[str, str] | None = None) -> None:
    """Load only approved Tavily settings from a local .env without logging values."""

    if not dotenv_path.is_file():
        raise RuntimeError("Local .env is required for the enabled Tavily integration test")
    target = os.environ if environment is None else environment
    for raw_line in dotenv_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in TAVILY_ENVIRONMENT_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        target[key] = value
