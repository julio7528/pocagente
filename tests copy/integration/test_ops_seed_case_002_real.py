"""Opt-in real validation of the persistent JSON-driven Case 002 failure seed."""

from __future__ import annotations

import os

import pytest

from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.repositories.operational import OperationalRepository
from database.seed.ops.loader import get_scenario, load_scenarios
from database.seed.ops.runner import run_scenarios
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_VERIFY_OPS_SEED_CASE_002") != "1",
    reason="persistent OPS Case 002 verification is opt-in",
)

CASE_002 = get_scenario("caso_002_erro_download_r2", load_scenarios())


async def _counts(connection: object, request_id: int, r1_run_id: int, r2_run_id: int) -> tuple[int, int, int, int, int, int]:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT
                (SELECT count(*) FROM ops.automation_runs WHERE run_id IN (%s, %s)),
                (SELECT count(*) FROM ops.incoming_emails WHERE run_id = %s),
                (SELECT count(*) FROM ops.email_attachments AS ea JOIN ops.incoming_emails AS ie ON ie.email_id = ea.email_id WHERE ie.run_id = %s),
                (SELECT count(*) FROM ops.service_requests WHERE request_id = %s),
                (SELECT count(*) FROM ops.establishments WHERE request_id = %s),
                (SELECT count(*) FROM ops.execution_log WHERE run_id IN (%s, %s))
            """,
            (r1_run_id, r2_run_id, r1_run_id, r1_run_id, request_id, request_id, r1_run_id, r2_run_id),
        )
        row = await cursor.fetchone()
    assert row is not None
    return tuple(int(value) for value in row)


def test_case_002_persisted_failure_state_and_factual_evidence(
    real_database_config: DatabaseConfig,
) -> None:
    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            async with database.connection() as connection:
                repository = OperationalRepository(connection)
                request = await repository.get_service_request_by_protocol("POC-OPS-0002")
                assert request is not None
                assert request.status == "FAILED"
                assert request.failure_reason == CASE_002.request.failure_reason
                assert request.completed_at is None and request.return_email_at is None
                establishments = await repository.list_establishments_for_request(request.request_id)
                assert len(establishments) == 1
                establishment = establishments[0]
                assert establishment.establishment_number == "2234567890"
                assert establishment.upload_status == "SUCCESS"
                assert establishment.download_status == "ERROR"
                assert establishment.processing_status == "ERROR"
                assert establishment.download_at is None and establishment.return_email_at is None
                facts = await repository.get_protocol_status_facts("POC-OPS-0002")
                assert len(facts) == 1 and facts[0].status == "FAILED"
                assert len(facts[0].establishments) == 1
                timeline = await repository.list_execution_timeline_for_request(request.request_id, 20)
                r2_run_id = next(item.run_id for item in timeline if item.robot == "R2")
                r1_timeline = await repository.list_execution_timeline_for_run(request.r1_run_id, 20)
                r2_timeline = await repository.list_execution_timeline_for_run(r2_run_id, 20)
                assert len(r1_timeline) == 10 and len(r2_timeline) == 5
                assert [item.status for item in reversed(r2_timeline)][-2:] == ["ERROR", "ERROR"]
                evidence = await repository.get_execution_failure_facts("POC-OPS-0002", run_id=r2_run_id)
                assert len(evidence) == 2
                assert {item.event for item in evidence} == {"DOWNLOAD_ARQUIVO_FALHOU", "PROCESSAMENTO_R2_FALHOU"}
                assert all(item.request_status == "FAILED" and item.run_status == "ERROR" for item in evidence)
                assert await _counts(connection, request.request_id, request.r1_run_id, r2_run_id) == (2, 1, 1, 1, 1, 15)
        finally:
            await database.close()

    run_async(validate())


def test_case_002_default_scenario_set_is_idempotent(
    real_database_config: DatabaseConfig,
) -> None:
    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            async with database.connection() as connection:
                repository = OperationalRepository(connection)
                request = await repository.get_service_request_by_protocol("POC-OPS-0002")
                assert request is not None
                r2_run_id = next(item.run_id for item in await repository.list_execution_timeline_for_request(request.request_id, 20) if item.robot == "R2")
                before = await _counts(connection, request.request_id, request.r1_run_id, r2_run_id)
        finally:
            await database.close()

        results = await run_scenarios(real_database_config, load_scenarios())
        assert all(result.created is False for result in results)

        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            async with database.connection() as connection:
                assert await _counts(connection, request.request_id, request.r1_run_id, r2_run_id) == before
        finally:
            await database.close()

    run_async(validate())
