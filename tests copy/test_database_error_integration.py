"""Tests for safe database error handling at infrastructure boundaries."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from psycopg import IntegrityError, OperationalError, ProgrammingError
from psycopg_pool import PoolTimeout
from pydantic import SecretStr

from apps.agent_api.app.database import connection as connection_module
from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.errors import (
    SafeConnectionError,
    SafeIntegrityError,
    SafeQueryError,
)
from apps.agent_api.app.database.repositories.audit import AuditRepository
from apps.agent_api.app.database.repositories.operational import OperationalRepository
from apps.agent_api.app.database.repositories.rag import RAGRepository
from tests.repository_fakes import FakeConnection, FakeCursor


def database_config() -> DatabaseConfig:
    return DatabaseConfig(
        host="db.test",
        port=5432,
        database="test_db",
        user="test_user",
        password=SecretStr("test-only-secret"),
        sslmode="disable",
        connect_timeout_seconds=5,
        pool_min_size=1,
        pool_max_size=2,
        pool_timeout_seconds=5,
    )


def mocked_database() -> tuple[PostgresDatabase, MagicMock]:
    pool = MagicMock()
    pool.open = AsyncMock()
    pool.wait = AsyncMock()
    pool.close = AsyncMock()
    with patch.object(connection_module, "AsyncConnectionPool", return_value=pool):
        database = PostgresDatabase(database_config())
    return database, pool


def test_open_translates_pool_timeout_and_preserves_cause() -> None:
    database, pool = mocked_database()
    failure = PoolTimeout("driver detail")
    pool.wait.side_effect = failure

    with pytest.raises(SafeConnectionError) as captured:
        asyncio.run(database.open())

    assert captured.value.__cause__ is failure
    assert "driver detail" not in str(captured.value)
    pool.close.assert_awaited_once_with()


def test_connection_checkout_translates_operational_error() -> None:
    database, pool = mocked_database()
    pool_context = MagicMock()
    failure = OperationalError("connection detail")
    pool_context.__aenter__ = AsyncMock(side_effect=failure)
    pool_context.__aexit__ = AsyncMock(return_value=False)
    pool.connection.return_value = pool_context

    async def acquire() -> None:
        async with database.connection():
            pass

    with pytest.raises(SafeConnectionError) as captured:
        asyncio.run(acquire())

    assert captured.value.__cause__ is failure


def test_transaction_translates_driver_error_and_preserves_cause() -> None:
    database, pool = mocked_database()
    connection = MagicMock()
    transaction_context = MagicMock()
    failure = IntegrityError("constraint detail")
    transaction_context.__aenter__ = AsyncMock(side_effect=failure)
    transaction_context.__aexit__ = AsyncMock(return_value=False)
    connection.transaction.return_value = transaction_context
    pool_context = MagicMock()
    pool_context.__aenter__ = AsyncMock(return_value=connection)
    pool_context.__aexit__ = AsyncMock(return_value=False)
    pool.connection.return_value = pool_context

    async def transact() -> None:
        async with database.transaction():
            pass

    with pytest.raises(SafeIntegrityError) as captured:
        asyncio.run(transact())

    assert captured.value.__cause__ is failure


class FailingCursor(FakeCursor):
    async def execute(self, statement: object, parameters: object = None) -> None:
        raise ProgrammingError("SELECT protected_value FROM protected_table")


class FailingConnection(FakeConnection):
    def cursor(self, **kwargs: object) -> FailingCursor:
        self.cursor_calls += 1
        return FailingCursor(self)


@pytest.mark.parametrize(
    "repository_factory, operation",
    [
        (RAGRepository, lambda repository: repository.get_source_by_id(uuid4())),
        (OperationalRepository, lambda repository: repository.get_automation_run(1)),
        (AuditRepository, lambda repository: repository.get_security_event(1)),
    ],
)
def test_repositories_translate_driver_errors_without_sql_details(
    repository_factory: object,
    operation: object,
) -> None:
    repository = repository_factory(FailingConnection())  # type: ignore[operator]

    with pytest.raises(SafeQueryError) as captured:
        asyncio.run(operation(repository))  # type: ignore[operator]

    assert isinstance(captured.value.__cause__, ProgrammingError)
    assert "SELECT" not in str(captured.value)


def test_transaction_does_not_double_translate_safe_repository_error() -> None:
    connection = FailingConnection()
    transaction_context = MagicMock()
    transaction_context.__aenter__ = AsyncMock(return_value=MagicMock())
    transaction_context.__aexit__ = AsyncMock(return_value=False)
    connection.transaction = MagicMock(return_value=transaction_context)
    database, pool = mocked_database()
    pool_context = MagicMock()
    pool_context.__aenter__ = AsyncMock(return_value=connection)
    pool_context.__aexit__ = AsyncMock(return_value=False)
    pool.connection.return_value = pool_context

    async def query_inside_transaction() -> None:
        async with database.transaction() as yielded:
            await RAGRepository(yielded).get_source_by_id(uuid4())

    with pytest.raises(SafeQueryError) as captured:
        asyncio.run(query_inside_transaction())

    assert isinstance(captured.value.__cause__, ProgrammingError)
    assert captured.value.__cause__ is not captured.value
    assert "SELECT" not in str(captured.value)


def test_application_validation_error_remains_unchanged() -> None:
    repository = RAGRepository(FakeConnection())

    with pytest.raises(ValueError, match="candidate limit"):
        asyncio.run(repository.search_lexical_candidates("query", limit=0, knowledge_scope="INTERNAL"))
