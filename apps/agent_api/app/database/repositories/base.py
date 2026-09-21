"""Shared connection-bound repository foundation."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from psycopg import AsyncConnection

from apps.agent_api.app.database.errors import translate_database_error


class BaseRepository:
    """Bind a persistence adapter to an externally managed connection."""

    def __init__(self, connection: AsyncConnection[Any]) -> None:
        self._connection = connection

    @asynccontextmanager
    async def _cursor(self, **kwargs: Any) -> AsyncIterator[Any]:
        """Yield a cursor while translating recognised driver failures safely."""

        try:
            async with self._connection.cursor(**kwargs) as cursor:
                yield cursor
        except Exception as error:
            safe_error = translate_database_error(error)
            if safe_error is not None:
                raise safe_error from error
            raise
