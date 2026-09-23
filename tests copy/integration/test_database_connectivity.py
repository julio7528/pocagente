"""Real, read-only PostgreSQL infrastructure validation."""

from __future__ import annotations

import os

import numpy as np
import pytest
from pgvector import Vector

from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL integration tests are opt-in",
)


def test_real_postgresql_pool_connection_and_pgvector(
    real_database_config: DatabaseConfig,
) -> None:
    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            async with database.connection() as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT current_database(),
                               current_setting('server_version_num')::integer,
                               (SELECT extversion
                                  FROM pg_extension
                                 WHERE extname = 'vector')
                        """
                    )
                    database_name, server_version_num, vector_version = (
                        await cursor.fetchone()
                    )

                    assert database_name == "getnet_support"
                    assert server_version_num // 10000 == 17
                    assert vector_version == "0.8.6"

                    expected = np.array([0.125, 0.25, 0.5], dtype=np.float32)
                    await cursor.execute("SELECT %s::vector(3)", (expected,))
                    round_trip = (await cursor.fetchone())[0]
                    assert isinstance(round_trip, Vector)
                    np.testing.assert_allclose(round_trip.to_numpy(), expected)
        finally:
            await database.close()

    run_async(validate())
