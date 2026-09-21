"""Unit tests for the explicit central PostgreSQL transaction boundary."""

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import SecretStr

from apps.agent_api.app.database import connection as connection_module
from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.repositories.audit import AuditRepository
from apps.agent_api.app.database.repositories.operational import OperationalRepository
from apps.agent_api.app.database.repositories.rag import RAGRepository
from tests.repository_fakes import FakeConnection


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


def mocked_database() -> tuple[PostgresDatabase, MagicMock, MagicMock, MagicMock]:
    pool = MagicMock()
    pool_context = MagicMock()
    acquired_connection = MagicMock()
    transaction_context = MagicMock()
    pool_context.__aenter__ = AsyncMock(return_value=acquired_connection)
    pool_context.__aexit__ = AsyncMock(return_value=False)
    transaction_context.__aenter__ = AsyncMock(return_value=MagicMock())
    transaction_context.__aexit__ = AsyncMock(return_value=False)
    acquired_connection.transaction.return_value = transaction_context
    acquired_connection.commit = AsyncMock()
    acquired_connection.rollback = AsyncMock()
    pool.connection.return_value = pool_context

    with patch.object(connection_module, "AsyncConnectionPool", return_value=pool):
        database = PostgresDatabase(database_config())

    return database, pool, pool_context, acquired_connection


def test_transaction_acquires_one_connection_and_yields_it() -> None:
    database, pool, pool_context, connection = mocked_database()

    async def use_transaction() -> None:
        async with database.transaction() as yielded:
            assert yielded is connection

    asyncio.run(use_transaction())

    pool.connection.assert_called_once_with()
    pool_context.__aenter__.assert_awaited_once_with()
    connection.transaction.assert_called_once_with()
    connection.transaction.return_value.__aenter__.assert_awaited_once_with()
    connection.transaction.return_value.__aexit__.assert_awaited_once_with(None, None, None)
    pool_context.__aexit__.assert_awaited_once_with(None, None, None)
    connection.commit.assert_not_awaited()
    connection.rollback.assert_not_awaited()


def test_transaction_propagates_body_exception_and_exits_all_contexts() -> None:
    database, pool, pool_context, connection = mocked_database()
    failure = RuntimeError("repository failure")

    async def fail_inside_transaction() -> None:
        async with database.transaction():
            raise failure

    with pytest.raises(RuntimeError) as captured:
        asyncio.run(fail_inside_transaction())

    assert captured.value is failure
    pool.connection.assert_called_once_with()
    transaction_exit = connection.transaction.return_value.__aexit__.await_args.args
    pool_exit = pool_context.__aexit__.await_args.args
    assert transaction_exit[0] is RuntimeError and transaction_exit[1] is failure
    assert pool_exit[0] is RuntimeError and pool_exit[1] is failure
    connection.commit.assert_not_awaited()
    connection.rollback.assert_not_awaited()


def test_transaction_initialization_failure_propagates_and_returns_pool_connection() -> None:
    database, pool, pool_context, connection = mocked_database()
    failure = RuntimeError("transaction initialization failed")
    connection.transaction.side_effect = failure

    async def initialize_transaction() -> None:
        async with database.transaction():
            raise AssertionError("transaction body must not execute")

    with pytest.raises(RuntimeError) as captured:
        asyncio.run(initialize_transaction())

    assert captured.value is failure
    pool.connection.assert_called_once_with()
    pool_exit = pool_context.__aexit__.await_args.args
    assert pool_exit[0] is RuntimeError and pool_exit[1] is failure


def test_transaction_module_import_still_creates_no_database_instance() -> None:
    instances = [
        value
        for value in vars(connection_module).values()
        if isinstance(value, (PostgresDatabase, connection_module.AsyncConnectionPool))
    ]

    assert instances == []


def test_transaction_composes_multiple_repositories_on_one_connection() -> None:
    database, pool, pool_context, connection = mocked_database()

    async def compose_repositories() -> None:
        async with database.transaction() as yielded:
            rag = RAGRepository(yielded)
            operational = OperationalRepository(yielded)
            audit = AuditRepository(yielded)

            assert rag._connection is connection
            assert operational._connection is connection
            assert audit._connection is connection

    asyncio.run(compose_repositories())

    pool.connection.assert_called_once_with()
    pool_context.__aenter__.assert_awaited_once_with()
    connection.transaction.assert_called_once_with()
    connection.commit.assert_not_awaited()
    connection.rollback.assert_not_awaited()


def test_repositories_can_operate_inside_one_transaction_without_owning_it() -> None:
    connection = FakeConnection(None, None, None)
    transaction_context = MagicMock()
    transaction_context.__aenter__ = AsyncMock(return_value=MagicMock())
    transaction_context.__aexit__ = AsyncMock(return_value=False)
    connection.transaction = MagicMock(return_value=transaction_context)
    pool = MagicMock()
    pool_context = MagicMock()
    pool_context.__aenter__ = AsyncMock(return_value=connection)
    pool_context.__aexit__ = AsyncMock(return_value=False)
    pool.connection.return_value = pool_context

    with patch.object(connection_module, "AsyncConnectionPool", return_value=pool):
        database = PostgresDatabase(database_config())

    async def use_repositories() -> None:
        async with database.transaction() as yielded:
            assert await RAGRepository(yielded).get_source_by_id(uuid4()) is None
            assert await OperationalRepository(yielded).get_automation_run(1) is None
            assert await AuditRepository(yielded).get_security_event(1) is None

    asyncio.run(use_repositories())

    assert len(connection.statements) == 3
    pool.connection.assert_called_once_with()
    connection.transaction.assert_called_once_with()
    connection.commit.assert_not_awaited()
    connection.rollback.assert_not_awaited()


def test_transaction_component_adds_no_custom_nesting_or_ambient_framework() -> None:
    source = inspect.getsource(connection_module)

    for forbidden in (
        "savepoint",
        "contextvars",
        "UnitOfWork",
        "RepositoryManager",
        "RepositoryContainer",
        "DatabaseSession",
    ):
        assert forbidden not in source
