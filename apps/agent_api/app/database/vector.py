"""Per-connection pgvector adapter configuration."""

from __future__ import annotations

from typing import Any

from pgvector.psycopg import register_vector_async
from psycopg import AsyncConnection


async def configure_pgvector_connection(connection: AsyncConnection[Any]) -> None:
    """Register pgvector adapters and leave a fresh connection transaction-clean."""

    try:
        await register_vector_async(connection)
    except BaseException:
        try:
            await connection.rollback()
        except BaseException:
            pass
        raise

    await connection.rollback()
