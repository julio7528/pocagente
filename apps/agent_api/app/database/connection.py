"""Central PostgreSQL connection and pool infrastructure."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.errors import translate_database_error
from apps.agent_api.app.database.vector import configure_pgvector_connection


class PostgresDatabase:
    """Own one explicitly managed asynchronous PostgreSQL connection pool."""

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config
        self._pool = AsyncConnectionPool(
            kwargs=config.psycopg_connection_kwargs(),
            min_size=config.pool_min_size,
            max_size=config.pool_max_size,
            timeout=config.pool_timeout_seconds,
            open=False,
            configure=configure_pgvector_connection,
        )

    async def open(self) -> None:
        """Open the pool and wait until its minimum capacity is ready."""

        try:
            await self._pool.open()
            await self._pool.wait()
        except Exception as error:
            try:
                await self._pool.close()
            except Exception:
                pass
            safe_error = translate_database_error(error)
            if safe_error is not None:
                if safe_error is error:
                    raise
                raise safe_error from error
            raise

    async def close(self) -> None:
        """Close the owned connection pool."""

        await self._pool.close()

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[AsyncConnection[Any]]:
        """Yield one connection through the pool's context manager."""

        try:
            async with self._pool.connection() as connection:
                yield connection
        except Exception as error:
            safe_error = translate_database_error(error)
            if safe_error is not None:
                if safe_error is error:
                    raise
                raise safe_error from error
            raise

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncConnection[Any]]:
        """Yield one pooled connection inside Psycopg's transaction context."""

        try:
            async with self._pool.connection() as connection:
                async with connection.transaction():
                    yield connection
        except Exception as error:
            safe_error = translate_database_error(error)
            if safe_error is not None:
                if safe_error is error:
                    raise
                raise safe_error from error
            raise
