"""Real integrity-error translation and rollback smoke validation."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from psycopg import IntegrityError

from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.errors import SafeIntegrityError
from apps.agent_api.app.database.repositories.rag import RAGRepository
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL integration tests are opt-in",
)


def test_real_integrity_error_is_safe_and_transaction_rolls_back(
    real_database_config: DatabaseConfig,
) -> None:
    unique = uuid4().hex
    reference = f"integration/integrity/{unique}"
    payload = {
        "name": "Synthetic integrity validation source",
        "source_type": "INTERNAL_DOCUMENT",
        "origin": "INTERNAL",
        "reference": reference,
        "status": "ACTIVE",
        "priority": 0,
        "updated_at": datetime.now(UTC),
    }

    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            with pytest.raises(SafeIntegrityError) as captured:
                async with database.transaction() as connection:
                    repository = RAGRepository(connection)
                    await repository.register_source(payload)
                    await repository.register_source(payload)

            safe_error = captured.value
            assert isinstance(safe_error.__cause__, IntegrityError)
            assert safe_error.__cause__ is not safe_error
            assert reference not in str(safe_error)
            assert "INSERT" not in str(safe_error)

            async with database.connection() as connection:
                repository = RAGRepository(connection)
                assert (
                    await repository.get_source_by_reference("INTERNAL", reference)
                    is None
                )
                async with connection.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    assert (await cursor.fetchone())[0] == 1
        finally:
            await database.close()

    run_async(validate())
