"""Tests for the connection-bound repository foundation."""

import inspect
from unittest.mock import AsyncMock, MagicMock

from apps.agent_api.app.database.repositories import base as base_module
from apps.agent_api.app.database.repositories.base import BaseRepository


def test_repository_reuses_exact_injected_connection_without_side_effects() -> None:
    connection = MagicMock()
    connection.execute = AsyncMock()
    connection.commit = AsyncMock()
    connection.rollback = AsyncMock()

    repository = BaseRepository(connection)

    assert repository._connection is connection
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_repository_foundation_has_no_pool_or_connection_creation() -> None:
    source = inspect.getsource(base_module)

    assert "AsyncConnectionPool" not in source
    assert "PostgresDatabase" not in source
    assert "psycopg.connect" not in source
    assert "AsyncConnection(" not in source


def test_repository_module_import_creates_no_global_repository() -> None:
    repositories = [
        value for value in vars(base_module).values() if isinstance(value, BaseRepository)
    ]

    assert repositories == []
