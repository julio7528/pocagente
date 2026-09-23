"""Secret-safe fixtures for opt-in local PostgreSQL integration tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from apps.agent_api.app.database.config import DatabaseConfig, load_database_config


_DATABASE_ENVIRONMENT_KEYS = frozenset(
    {
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_SSLMODE",
        "POSTGRES_CONNECT_TIMEOUT_SECONDS",
        "POSTGRES_POOL_MIN_SIZE",
        "POSTGRES_POOL_MAX_SIZE",
        "POSTGRES_POOL_TIMEOUT_SECONDS",
    }
)


def _load_database_environment(dotenv_path: Path) -> None:
    """Populate approved database variables from .env without logging values."""

    if not dotenv_path.is_file():
        pytest.fail("Local .env is required for real database integration tests")

    for raw_line in dotenv_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in _DATABASE_ENVIRONMENT_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


@pytest.fixture(scope="session")
def real_database_config() -> DatabaseConfig:
    """Load the approved runtime configuration path for local integration tests."""

    _load_database_environment(Path(__file__).resolve().parents[2] / ".env")
    config = load_database_config()
    assert config.database == "getnet_support"
    return config
