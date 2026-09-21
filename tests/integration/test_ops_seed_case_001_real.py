"""Opt-in read/write validation for the persistent local OPS Case 001 seed."""

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
    os.getenv("GETNET_VERIFY_OPS_SEED_CASE_001") != "1",
    reason="persistent OPS seed verification is opt-in",
)

CASE_001_SUCESSO = get_scenario("caso_001_sucesso", load_scenarios())


async def _case_counts(connection: object, request_id: int, r1_run_id: int, r2_run_id: int) -> tuple[int, int, int, int, int, int]:
    async with connection.cursor() as cursor:
        await cursor.execute(
            """
            SELECT
                (SELECT count(*) FROM ops.automation_runs WHERE run_id IN (%s, %s)),
                (SELECT count(*) FROM ops.incoming_emails WHERE run_id = %s),
                (SELECT count(*) FROM ops.email_attachments AS ea
                   JOIN ops.incoming_emails AS ie ON ie.email_id = ea.email_id
                 WHERE ie.run_id = %s),
                (SELECT count(*) FROM ops.service_requests WHERE request_id = %s),
                (SELECT count(*) FROM ops.establishments WHERE request_id = %s),
                (SELECT count(*) FROM ops.execution_log WHERE run_id IN (%s, %s))
            """,
            (r1_run_id, r2_run_id, r1_run_id, r1_run_id, request_id, request_id, r1_run_id, r2_run_id),
        )
        row = await cursor.fetchone()
    assert row is not None
    return tuple(int(value) for value in row)


def test_case_001_is_persisted_with_the_approved_final_ops_state(
    real_database_config: DatabaseConfig,
) -> None:
    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            async with database.connection() as connection:
                repository = OperationalRepository(connection)
                request = await repository.get_service_request_by_protocol("POC-OPS-0001")
                assert request is not None
                assert request.status == "COMPLETED"
                assert request.failure_reason is None
                assert request.result == CASE_001_SUCESSO.request.result
                assert request.completed_at == CASE_001_SUCESSO.request.completed_at
                assert request.return_email_at == CASE_001_SUCESSO.request.return_email_at

                protocol_facts = await repository.get_protocol_status_facts("POC-OPS-0001")
                assert len(protocol_facts) == 1
                assert protocol_facts[0].request_id == request.request_id
                assert protocol_facts[0].status == "COMPLETED"
                assert len(protocol_facts[0].establishments) == 1
                assert len(protocol_facts[0].execution_timeline) == 12

                establishments = await repository.list_establishments_for_request(request.request_id)
                assert len(establishments) == 1
                establishment = establishments[0]
                assert establishment.establishment_number == "1234567890"
                assert establishment.generated_file_name == "cancelamento_estabelecimento_1234567890.txt"
                assert establishment.processing_status == "COMPLETED"
                assert establishment.upload_status == "SUCCESS"
                assert establishment.download_status == "DOWNLOADED"
                assert establishment.download_at == CASE_001_SUCESSO.establishment.download_at
                assert establishment.return_email_at == CASE_001_SUCESSO.establishment.return_email_at

                async with connection.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT ie.run_id, ie.received_at, ie.processed_at, ie.sender,
                               ie.recipient, ie.subject, ie.attachment_count,
                               ie.sender_status, ie.processing_status, ie.rejection_reason,
                               ea.file_name, ea.file_type, ea.validation_status,
                               ea.validation_message, ea.establishment_count,
                               ea.processing_status
                        FROM ops.incoming_emails AS ie
                        JOIN ops.email_attachments AS ea ON ea.email_id = ie.email_id
                        WHERE ie.email_id = %s
                        """,
                        (request.email_id,),
                    )
                    email_and_attachment = await cursor.fetchone()
                assert email_and_attachment == (
                    request.r1_run_id,
                    CASE_001_SUCESSO.email.received_at,
                    CASE_001_SUCESSO.email.processed_at,
                    CASE_001_SUCESSO.email.sender,
                    CASE_001_SUCESSO.email.recipient,
                    CASE_001_SUCESSO.email.subject,
                    1,
                    "VALID",
                    "PROCESSED",
                    None,
                    "solicitacao_cancelamento_maria.xlsx",
                    "XLSX",
                    "VALID",
                    "Arquivo validado para processamento.",
                    1,
                    "PROCESSED",
                )

                request_timeline = await repository.list_execution_timeline_for_request(request.request_id, 20)
                r2_run_ids = {item.run_id for item in request_timeline if item.robot == "R2"}
                assert len(r2_run_ids) == 1
                r2_run_id = r2_run_ids.pop()
                r1_timeline = await repository.list_execution_timeline_for_run(request.r1_run_id, 20)
                r2_timeline = await repository.list_execution_timeline_for_run(r2_run_id, 20)
                assert [item.event for item in reversed(r1_timeline)] == [event.event for event in CASE_001_SUCESSO.r1.events]
                assert [item.event for item in reversed(r2_timeline)] == [event.event for event in CASE_001_SUCESSO.r2.events]
                assert all(item.status == "SUCCESS" for item in (*r1_timeline, *r2_timeline))
                assert await _case_counts(connection, request.request_id, request.r1_run_id, r2_run_id) == (2, 1, 1, 1, 1, 16)
        finally:
            await database.close()

    run_async(validate())


def test_case_001_runner_is_idempotent_without_overwriting_existing_rows(
    real_database_config: DatabaseConfig,
) -> None:
    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            async with database.connection() as connection:
                repository = OperationalRepository(connection)
                request = await repository.get_service_request_by_protocol("POC-OPS-0001")
                assert request is not None
                r2_run_id = next(
                    item.run_id
                    for item in await repository.list_execution_timeline_for_request(request.request_id, 20)
                    if item.robot == "R2"
                )
                before = await _case_counts(connection, request.request_id, request.r1_run_id, r2_run_id)
        finally:
            await database.close()

        results = await run_scenarios(real_database_config, (CASE_001_SUCESSO,))
        assert len(results) == 1
        assert results[0].created is False
        assert results[0].request_id == request.request_id

        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            async with database.connection() as connection:
                assert await _case_counts(connection, request.request_id, request.r1_run_id, r2_run_id) == before
        finally:
            await database.close()

    run_async(validate())
