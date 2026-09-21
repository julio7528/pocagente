"""Opt-in real PostgreSQL validation for the Phase 9.4 read-only OPS tools."""

from __future__ import annotations

import os

import pytest

from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.models import ExecutionFailureEvidence, ProtocolStatusFacts
from apps.agent_api.app.database.repositories.operational import OperationalRepository
from apps.agent_api.app.tools.ops import OpsAccessContext, OpsToolStatus, OperationalTools
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL integration tests are opt-in",
)


AUTHORIZED = OpsAccessContext(principal_id="integration-support-operator", can_read_operational_facts=True)


def test_ops_tools_use_real_repository_facts_without_mutation(
    real_database_config: DatabaseConfig,
) -> None:
    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            async with database.connection() as connection:
                tools = OperationalTools(OperationalRepository(connection))

                lookup = await tools.lookup_protocol_status("POC-OPS-0002", AUTHORIZED)
                assert lookup.status is OpsToolStatus.SUCCESS
                assert isinstance(lookup.facts, ProtocolStatusFacts)
                assert lookup.facts.protocol_number == "POC-OPS-0002"
                assert lookup.facts.status == "FAILED"

                failure = await tools.inspect_execution_failure("POC-OPS-0002", AUTHORIZED)
                assert failure.status is OpsToolStatus.SUCCESS
                assert failure.evidence
                assert all(isinstance(item, ExecutionFailureEvidence) for item in failure.evidence)
                assert all(item.protocol_number == "POC-OPS-0002" for item in failure.evidence)

                filtered = await tools.inspect_execution_failure(
                    "POC-OPS-0002", AUTHORIZED, run_id=failure.evidence[0].run_id
                )
                assert filtered.status is OpsToolStatus.SUCCESS
                assert all(item.run_id == failure.evidence[0].run_id for item in filtered.evidence)

                missing_lookup = await tools.lookup_protocol_status("POC-OPS-NOT-FOUND-9-4", AUTHORIZED)
                missing_failure = await tools.inspect_execution_failure(
                    "POC-OPS-NOT-FOUND-9-4", AUTHORIZED
                )
                assert missing_lookup.status is OpsToolStatus.NOT_FOUND
                assert missing_failure.status is OpsToolStatus.NOT_FOUND
        finally:
            await database.close()

    run_async(validate())
