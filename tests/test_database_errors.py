"""Focused tests for secret-safe database driver error translation."""

from __future__ import annotations

import asyncio

import pytest
from psycopg import (
    DataError,
    IntegrityError,
    InterfaceError,
    InternalError,
    NotSupportedError,
    OperationalError,
    ProgrammingError,
)
from psycopg_pool import PoolClosed, PoolTimeout
from pydantic import ValidationError

from apps.agent_api.app.database.errors import (
    SafeConnectionError,
    SafeDatabaseError,
    SafeIntegrityError,
    SafeQueryError,
    translate_database_error,
)


@pytest.mark.parametrize(
    ("driver_error", "expected_type", "retryable"),
    [
        (PoolTimeout("pool wait timed out"), SafeConnectionError, True),
        (PoolClosed("pool is closed"), SafeConnectionError, False),
        (OperationalError("connection timed out"), SafeConnectionError, False),
        (IntegrityError("constraint details"), SafeIntegrityError, False),
        (ProgrammingError("SELECT sensitive_column"), SafeQueryError, False),
        (DataError("bad data"), SafeQueryError, False),
        (InternalError("server detail"), SafeQueryError, False),
        (NotSupportedError("unsupported"), SafeQueryError, False),
        (InterfaceError("interface error"), SafeDatabaseError, False),
    ],
)
def test_known_driver_errors_map_to_stable_safe_errors(
    driver_error: Exception,
    expected_type: type[SafeDatabaseError],
    retryable: bool,
) -> None:
    translated = translate_database_error(driver_error)

    assert isinstance(translated, expected_type)
    assert translated.retryable is retryable
    assert str(translated) != str(driver_error)


def test_safe_error_message_does_not_include_driver_diagnostics() -> None:
    driver_error = ProgrammingError(
        "postgresql://local-user:not-a-real-password@host/db SELECT private_value"
    )

    translated = translate_database_error(driver_error)

    assert translated is not None
    assert "not-a-real-password" not in str(translated)
    assert "SELECT" not in str(translated)


@pytest.mark.parametrize(
    "application_error",
    [
        ValueError("application validation"),
        TypeError("application type"),
        RuntimeError("application failure"),
    ],
)
def test_application_errors_are_not_translated(application_error: Exception) -> None:
    assert translate_database_error(application_error) is None


def test_pydantic_validation_error_is_not_translated() -> None:
    with pytest.raises(ValidationError) as captured:
        raise ValidationError.from_exception_data(
            "ExampleModel", [{"type": "missing", "loc": ("field",), "input": {}}]
        )

    assert translate_database_error(captured.value) is None


@pytest.mark.parametrize(
    "base_error",
    [asyncio.CancelledError(), KeyboardInterrupt(), SystemExit()],
)
def test_base_exception_subclasses_are_not_accepted_for_translation(
    base_error: BaseException,
) -> None:
    assert translate_database_error(base_error) is None  # type: ignore[arg-type]
