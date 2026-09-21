"""Unit tests for per-physical-connection pgvector configuration."""

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.agent_api.app.database import vector as vector_module


def test_registers_pgvector_once_and_leaves_connection_clean() -> None:
    connection = MagicMock()
    connection.rollback = AsyncMock()

    with patch.object(
        vector_module,
        "register_vector_async",
        new_callable=AsyncMock,
    ) as register_vector:
        asyncio.run(vector_module.configure_pgvector_connection(connection))

    register_vector.assert_awaited_once_with(connection)
    connection.rollback.assert_awaited_once_with()


def test_registration_failure_is_propagated_and_cleanup_is_attempted() -> None:
    connection = MagicMock()
    connection.rollback = AsyncMock()
    registration_failure = RuntimeError("pgvector registration failed")

    with patch.object(
        vector_module,
        "register_vector_async",
        new_callable=AsyncMock,
        side_effect=registration_failure,
    ) as register_vector:
        with pytest.raises(RuntimeError) as captured:
            asyncio.run(vector_module.configure_pgvector_connection(connection))

    assert captured.value is registration_failure
    register_vector.assert_awaited_once_with(connection)
    connection.rollback.assert_awaited_once_with()


def test_cleanup_failure_preserves_original_registration_failure() -> None:
    connection = MagicMock()
    connection.rollback = AsyncMock(side_effect=RuntimeError("cleanup failed"))
    registration_failure = RuntimeError("pgvector registration failed")

    with patch.object(
        vector_module,
        "register_vector_async",
        new_callable=AsyncMock,
        side_effect=registration_failure,
    ):
        with pytest.raises(RuntimeError) as captured:
            asyncio.run(vector_module.configure_pgvector_connection(connection))

    assert captured.value is registration_failure
    connection.rollback.assert_awaited_once_with()


def test_cleanup_failure_after_registration_fails_closed() -> None:
    connection = MagicMock()
    cleanup_failure = RuntimeError("cleanup failed")
    connection.rollback = AsyncMock(side_effect=cleanup_failure)

    with patch.object(
        vector_module,
        "register_vector_async",
        new_callable=AsyncMock,
    ):
        with pytest.raises(RuntimeError) as captured:
            asyncio.run(vector_module.configure_pgvector_connection(connection))

    assert captured.value is cleanup_failure


def test_registration_cancellation_attempts_cleanup_and_preserves_cancellation() -> None:
    connection = MagicMock()
    connection.rollback = AsyncMock()
    cancellation = asyncio.CancelledError()

    with patch.object(
        vector_module,
        "register_vector_async",
        new_callable=AsyncMock,
        side_effect=cancellation,
    ):
        with pytest.raises(asyncio.CancelledError) as captured:
            asyncio.run(vector_module.configure_pgvector_connection(connection))

    assert captured.value is cancellation
    connection.rollback.assert_awaited_once_with()


def test_registration_cancellation_is_not_masked_by_cleanup_failure() -> None:
    connection = MagicMock()
    connection.rollback = AsyncMock(side_effect=RuntimeError("cleanup failed"))
    cancellation = asyncio.CancelledError()

    with patch.object(
        vector_module,
        "register_vector_async",
        new_callable=AsyncMock,
        side_effect=cancellation,
    ):
        with pytest.raises(asyncio.CancelledError) as captured:
            asyncio.run(vector_module.configure_pgvector_connection(connection))

    assert captured.value is cancellation
    connection.rollback.assert_awaited_once_with()


def test_vector_module_creates_no_connection_or_pool() -> None:
    source = inspect.getsource(vector_module)

    assert "AsyncConnection(" not in source
    assert "AsyncConnectionPool" not in source
