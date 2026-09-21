"""Unit tests for the central PostgreSQL connection component."""

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from pydantic import SecretStr

from apps.agent_api.app.database import connection as connection_module
from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.vector import configure_pgvector_connection


def database_config() -> DatabaseConfig:
    return DatabaseConfig(
        host="db.test",
        port=6543,
        database="controlled_db",
        user="controlled_user",
        password=SecretStr("controlled-secret"),
        sslmode="require",
        connect_timeout_seconds=9,
        pool_min_size=2,
        pool_max_size=7,
        pool_timeout_seconds=11,
    )


def mocked_database() -> tuple[PostgresDatabase, DatabaseConfig, MagicMock, MagicMock]:
    config = database_config()
    pool = MagicMock()
    pool.open = AsyncMock()
    pool.wait = AsyncMock()
    pool.close = AsyncMock()
    pool_class = MagicMock(return_value=pool)

    with patch.object(connection_module, "AsyncConnectionPool", pool_class):
        database = PostgresDatabase(config)

    return database, config, pool, pool_class


def test_constructor_accepts_config_and_builds_one_closed_pool() -> None:
    database, config, pool, pool_class = mocked_database()

    assert isinstance(database, PostgresDatabase)
    assert database._config is config
    pool_class.assert_called_once_with(
        kwargs=config.psycopg_connection_kwargs(),
        min_size=2,
        max_size=7,
        timeout=11,
        open=False,
        configure=configure_pgvector_connection,
    )
    pool.open.assert_not_called()
    pool.wait.assert_not_called()


def test_pool_uses_structured_kwargs_without_a_connection_uri() -> None:
    _, config, _, pool_class = mocked_database()

    positional_args, keyword_args = pool_class.call_args

    assert positional_args == ()
    assert keyword_args["kwargs"] == config.psycopg_connection_kwargs()
    assert keyword_args["kwargs"]["dbname"] == "controlled_db"
    assert keyword_args["kwargs"]["password"] == "controlled-secret"
    assert "conninfo" not in keyword_args


def test_open_opens_pool_then_waits_for_readiness() -> None:
    database, _, pool, _ = mocked_database()

    asyncio.run(database.open())

    assert pool.method_calls == [call.open(), call.wait()]
    pool.open.assert_awaited_once_with()
    pool.wait.assert_awaited_once_with()
    pool.close.assert_not_awaited()


def test_readiness_failure_is_propagated_and_pool_is_closed() -> None:
    database, _, pool, _ = mocked_database()
    failure = RuntimeError("pool readiness failed")
    pool.wait.side_effect = failure

    with pytest.raises(RuntimeError) as captured:
        asyncio.run(database.open())

    assert captured.value is failure
    pool.open.assert_awaited_once_with()
    pool.wait.assert_awaited_once_with()
    pool.close.assert_awaited_once_with()


def test_cleanup_failure_does_not_replace_original_readiness_failure() -> None:
    database, _, pool, _ = mocked_database()
    readiness_failure = RuntimeError("pool readiness failed")
    pool.wait.side_effect = readiness_failure
    pool.close.side_effect = RuntimeError("cleanup failed")

    with pytest.raises(RuntimeError) as captured:
        asyncio.run(database.open())

    assert captured.value is readiness_failure


def test_close_delegates_to_pool() -> None:
    database, _, pool, _ = mocked_database()

    asyncio.run(database.close())

    pool.close.assert_awaited_once_with()


def test_connection_uses_pool_context_and_yields_connection() -> None:
    database, _, pool, _ = mocked_database()
    acquired_connection = MagicMock()
    pool_context = MagicMock()
    pool_context.__aenter__ = AsyncMock(return_value=acquired_connection)
    pool_context.__aexit__ = AsyncMock(return_value=False)
    pool.connection.return_value = pool_context

    async def use_connection() -> None:
        async with database.connection() as connection:
            assert connection is acquired_connection

    asyncio.run(use_connection())

    pool.connection.assert_called_once_with()
    pool_context.__aenter__.assert_awaited_once_with()
    pool_context.__aexit__.assert_awaited_once_with(None, None, None)


def test_connection_does_not_execute_sql_automatically() -> None:
    database, _, pool, _ = mocked_database()
    acquired_connection = MagicMock()
    acquired_connection.execute = AsyncMock()
    pool_context = MagicMock()
    pool_context.__aenter__ = AsyncMock(return_value=acquired_connection)
    pool_context.__aexit__ = AsyncMock(return_value=False)
    pool.connection.return_value = pool_context

    async def acquire_only() -> None:
        async with database.connection():
            pass

    asyncio.run(acquire_only())

    acquired_connection.execute.assert_not_awaited()


def test_component_delegates_pgvector_configuration_to_vector_module() -> None:
    source = inspect.getsource(connection_module)

    assert "register_vector_async" not in source
    assert connection_module.configure_pgvector_connection is configure_pgvector_connection


def test_connection_checkout_does_not_repeat_pgvector_registration() -> None:
    config = database_config()
    pool = MagicMock()
    pool.open = AsyncMock()
    pool.wait = AsyncMock()
    pool.close = AsyncMock()
    pool_context = MagicMock()
    pool_context.__aenter__ = AsyncMock(return_value=MagicMock())
    pool_context.__aexit__ = AsyncMock(return_value=False)
    pool.connection.return_value = pool_context
    pool_class = MagicMock(return_value=pool)

    with (
        patch.object(connection_module, "AsyncConnectionPool", pool_class),
        patch.object(
            connection_module,
            "configure_pgvector_connection",
            new_callable=AsyncMock,
        ) as configure_callback,
    ):
        database = PostgresDatabase(config)

        async def acquire_only() -> None:
            async with database.connection():
                pass

        asyncio.run(acquire_only())

    assert pool_class.call_args.kwargs["configure"] is configure_callback
    configure_callback.assert_not_awaited()


def test_module_import_creates_no_global_database_or_pool() -> None:
    global_instances = [
        value
        for value in vars(connection_module).values()
        if isinstance(value, (PostgresDatabase, connection_module.AsyncConnectionPool))
    ]

    assert global_instances == []
