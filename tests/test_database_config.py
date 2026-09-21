"""Focused tests for the validated PostgreSQL configuration model."""

import importlib

import pytest
from pydantic import SecretStr, ValidationError

from apps.agent_api.app.database import config as config_module
from apps.agent_api.app.database.config import DatabaseConfig, load_database_config


def valid_config(**overrides: object) -> DatabaseConfig:
    values: dict[str, object] = {"password": SecretStr("local-secret")}
    values.update(overrides)
    return DatabaseConfig(**values)


def test_valid_configuration_uses_approved_defaults() -> None:
    config = valid_config()

    assert config.host == "127.0.0.1"
    assert config.port == 5432
    assert config.database == "getnet_support"
    assert config.user == "getnet_app"
    assert config.sslmode == "disable"
    assert config.connect_timeout_seconds == 5
    assert config.pool_min_size == 1
    assert config.pool_max_size == 5
    assert config.pool_timeout_seconds == 5


@pytest.mark.parametrize("field_name", ["host", "database", "user"])
def test_blank_text_fields_are_rejected(field_name: str) -> None:
    with pytest.raises(ValidationError):
        valid_config(**{field_name: " "})


def test_missing_password_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DatabaseConfig()


def test_blank_password_is_rejected() -> None:
    with pytest.raises(ValidationError):
        valid_config(password=SecretStr(""))


def test_password_is_masked_in_model_output() -> None:
    config = valid_config(password=SecretStr("do-not-print"))

    assert "do-not-print" not in repr(config)
    assert "do-not-print" not in str(config)
    assert "**********" in repr(config)


@pytest.mark.parametrize("port", [1, 65535])
def test_valid_port_range_is_accepted(port: int) -> None:
    assert valid_config(port=port).port == port


@pytest.mark.parametrize("port", [0, 65536])
def test_invalid_port_is_rejected(port: int) -> None:
    with pytest.raises(ValidationError):
        valid_config(port=port)


@pytest.mark.parametrize("field_name", ["connect_timeout_seconds", "pool_timeout_seconds"])
def test_timeout_must_be_positive(field_name: str) -> None:
    with pytest.raises(ValidationError):
        valid_config(**{field_name: 0})


def test_pool_min_size_must_be_non_negative() -> None:
    with pytest.raises(ValidationError):
        valid_config(pool_min_size=-1)


def test_pool_max_size_must_be_at_least_one() -> None:
    with pytest.raises(ValidationError):
        valid_config(pool_max_size=0)


def test_pool_min_greater_than_max_is_rejected() -> None:
    with pytest.raises(ValidationError):
        valid_config(pool_min_size=6, pool_max_size=5)


@pytest.mark.parametrize(
    "sslmode",
    ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"],
)
def test_supported_ssl_modes_are_accepted(sslmode: str) -> None:
    assert valid_config(sslmode=sslmode).sslmode == sslmode


def test_invalid_ssl_mode_is_rejected() -> None:
    with pytest.raises(ValidationError):
        valid_config(sslmode="invalid")


def test_environment_loader_uses_controlled_environment_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = {
        "POSTGRES_HOST": "db.test",
        "POSTGRES_PORT": "6543",
        "POSTGRES_DB": "controlled_db",
        "POSTGRES_USER": "controlled_user",
        "POSTGRES_PASSWORD": "controlled-secret",
        "POSTGRES_SSLMODE": "require",
        "POSTGRES_CONNECT_TIMEOUT_SECONDS": "9",
        "POSTGRES_POOL_MIN_SIZE": "2",
        "POSTGRES_POOL_MAX_SIZE": "7",
        "POSTGRES_POOL_TIMEOUT_SECONDS": "11",
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    config = load_database_config()

    assert config.host == "db.test"
    assert config.port == 6543
    assert config.database == "controlled_db"
    assert config.user == "controlled_user"
    assert config.password.get_secret_value() == "controlled-secret"
    assert config.sslmode == "require"
    assert config.connect_timeout_seconds == 9
    assert config.pool_min_size == 2
    assert config.pool_max_size == 7
    assert config.pool_timeout_seconds == 11


def test_module_import_does_not_load_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_PASSWORD", "controlled-secret")

    reloaded_module = importlib.reload(config_module)

    assert not hasattr(reloaded_module, "DATABASE_CONFIG")
    assert not hasattr(reloaded_module, "DEFAULT_DATABASE_CONFIG")


def test_psycopg_kwargs_use_dbname_and_exclude_pool_settings() -> None:
    config = valid_config(password=SecretStr("handoff-secret"))

    kwargs = config.psycopg_connection_kwargs()

    assert kwargs["dbname"] == "getnet_support"
    assert "database" not in kwargs
    assert "pool_min_size" not in kwargs
    assert "pool_max_size" not in kwargs
    assert "pool_timeout_seconds" not in kwargs
    assert kwargs["password"] == "handoff-secret"


def test_psycopg_kwargs_expose_secret_only_at_explicit_handoff() -> None:
    config = valid_config(password=SecretStr("handoff-only-secret"))

    assert "handoff-only-secret" not in repr(config)
    assert "handoff-only-secret" not in str(config)
    assert config.psycopg_connection_kwargs()["password"] == "handoff-only-secret"
