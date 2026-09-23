"""Read-only proof that real integration scenarios leave no persistent data."""

from __future__ import annotations

import os

import pytest

from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL integration tests are opt-in",
)


def test_no_synthetic_integration_records_remain(
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
                        SELECT
                            (SELECT count(*) FROM rag.sources
                              WHERE reference LIKE 'integration/rag/%'
                                 OR reference LIKE 'integration/integrity/%'),
                            (SELECT count(*) FROM ops.service_requests
                              WHERE protocol_number LIKE 'integration-ops-%'),
                            (SELECT count(*) FROM audit.security_events
                              WHERE request_reference LIKE 'integration-audit-%')
                        """
                    )
                    assert await cursor.fetchone() == (0, 0, 0)
        finally:
            await database.close()

    run_async(validate())
