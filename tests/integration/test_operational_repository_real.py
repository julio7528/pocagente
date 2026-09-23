"""Real transactional validation of the concrete OPS repository."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.models import (
    AutomationRunRecord,
    EstablishmentRecord,
    ExecutionFailureEvidence,
    ExecutionLogRecord,
    ProtocolStatusFacts,
    ServiceRequestRecord,
    OperationalAnalyticsQuery,
)
from apps.agent_api.app.database.repositories.operational import OperationalRepository
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL integration tests are opt-in",
)


class _RollbackScenario(Exception):
    pass


def test_real_operational_repository_lifecycle_and_rollback(
    real_database_config: DatabaseConfig,
) -> None:
    unique = uuid4().hex
    protocol = f"integration-ops-{unique}"
    started_at = datetime.now(UTC)
    received_at = started_at + timedelta(seconds=1)
    completed_at = received_at + timedelta(seconds=1)

    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            with pytest.raises(_RollbackScenario):
                async with database.transaction() as connection:
                    repository = OperationalRepository(connection)
                    run_id = await repository.create_automation_run(
                        {"robot": "R1", "started_at": started_at}
                    )
                    run = await repository.get_automation_run(run_id)
                    assert isinstance(run, AutomationRunRecord)
                    await repository.update_automation_run(
                        run_id,
                        {
                            "finished_at": completed_at,
                            "status": "ERROR",
                            "result_message": "Synthetic sanitized failure",
                        },
                    )
                    assert (await repository.get_automation_run(run_id)).status == "ERROR"

                    email_id = await repository.create_incoming_email(
                        {
                            "run_id": run_id,
                            "received_at": received_at,
                            "sender": "synthetic.sender@example.invalid",
                            "recipient": "synthetic.receiver@example.invalid",
                            "subject": "Synthetic integration request",
                            "attachment_count": 1,
                        }
                    )
                    await repository.update_incoming_email(
                        email_id,
                        {
                            "processed_at": completed_at,
                            "sender_status": "VALID",
                            "processing_status": "PROCESSED",
                        },
                    )

                    attachment_id = await repository.create_email_attachment(
                        {
                            "email_id": email_id,
                            "file_name": f"synthetic-{unique}.xlsx",
                            "received_at": received_at,
                        }
                    )
                    await repository.update_email_attachment(
                        attachment_id,
                        {
                            "file_type": "XLSX",
                            "validation_status": "VALID",
                            "validation_message": "Synthetic file validated",
                            "establishment_count": 1,
                            "processing_status": "PROCESSED",
                        },
                    )

                    request_id = await repository.create_service_request(
                        {
                            "protocol_number": protocol,
                            "email_id": email_id,
                            "r1_run_id": run_id,
                            "updated_at": completed_at,
                        }
                    )
                    await repository.update_service_request(
                        request_id,
                        {
                            "updated_at": completed_at,
                            "status": "FAILED",
                            "failure_reason": "Synthetic sanitized failure",
                        },
                    )
                    request = await repository.get_service_request_by_protocol(protocol)
                    assert isinstance(request, ServiceRequestRecord)
                    assert request.request_id == request_id
                    recent_requests = await repository.list_recent_service_requests(5)
                    assert any(item.protocol_number == protocol for item in recent_requests)

                    establishment_payload = {
                        "request_id": request_id,
                        "attachment_id": attachment_id,
                        "establishment_number": f"EC-{unique}",
                        "generated_file_name": f"synthetic-{unique}.csv",
                        "processing_status": "PENDING",
                        "updated_at": completed_at,
                    }
                    establishment_id = await repository.upsert_establishment(
                        establishment_payload
                    )
                    assert (
                        await repository.upsert_establishment(
                            {
                                **establishment_payload,
                                "processing_status": "WAITING_RESULT",
                            }
                        )
                        == establishment_id
                    )
                    await repository.update_establishment(
                        establishment_id,
                        {
                            "processing_status": "RESULT_AVAILABLE",
                            "upload_status": "SUCCESS",
                            "upload_at": completed_at,
                            "download_status": "AVAILABLE",
                            "result_message": "Synthetic result available",
                            "updated_at": completed_at,
                        },
                    )
                    establishments = await repository.list_establishments_for_request(
                        request_id
                    )
                    assert len(establishments) == 1
                    assert isinstance(establishments[0], EstablishmentRecord)

                    success_log_id = await repository.append_execution_log(
                        {
                            "run_id": run_id,
                            "logged_at": received_at,
                            "robot": "R1",
                            "event": "SYNTHETIC_STARTED",
                            "status": "SUCCESS",
                            "message": "Synthetic sanitized start",
                            "email_id": email_id,
                            "attachment_id": attachment_id,
                            "request_id": request_id,
                            "establishment_id": establishment_id,
                        }
                    )
                    failure_log_id = await repository.append_execution_log(
                        {
                            "run_id": run_id,
                            "logged_at": completed_at,
                            "robot": "R1",
                            "event": "SYNTHETIC_FAILED",
                            "status": "ERROR",
                            "message": "Synthetic sanitized failure evidence",
                            "email_id": email_id,
                            "attachment_id": attachment_id,
                            "request_id": request_id,
                            "establishment_id": establishment_id,
                        }
                    )
                    assert failure_log_id > success_log_id

                    run_timeline = await repository.list_execution_timeline_for_run(
                        run_id, 20
                    )
                    request_timeline = (
                        await repository.list_execution_timeline_for_request(
                            request_id, 20
                        )
                    )
                    assert len(run_timeline) == 2
                    assert len(request_timeline) == 2
                    assert all(isinstance(item, ExecutionLogRecord) for item in run_timeline)

                    protocol_facts = await repository.get_protocol_status_facts(protocol)
                    assert len(protocol_facts) == 1
                    assert isinstance(protocol_facts[0], ProtocolStatusFacts)
                    assert len(protocol_facts[0].establishments) == 1
                    assert len(protocol_facts[0].execution_timeline) == 2

                    failure_facts = await repository.get_execution_failure_facts(
                        protocol
                    )
                    filtered_failure_facts = (
                        await repository.get_execution_failure_facts(
                            protocol, run_id=run_id
                        )
                    )
                    assert len(failure_facts) == 1
                    assert len(filtered_failure_facts) == 1
                    assert isinstance(failure_facts[0], ExecutionFailureEvidence)
                    assert failure_facts[0].log_id == failure_log_id
                    assert failure_facts[0].last_successful_evidence is not None

                    r2_run_id = await repository.create_automation_run(
                        {"robot": "R2", "started_at": started_at + timedelta(milliseconds=500)}
                    )
                    await repository.update_automation_run(
                        r2_run_id,
                        {"finished_at": completed_at, "status": "SUCCESS", "result_message": "Synthetic R2 success"},
                    )
                    await repository.append_execution_log(
                        {
                            "run_id": r2_run_id,
                            "logged_at": received_at + timedelta(milliseconds=500),
                            "robot": "R2",
                            "event": "SYNTHETIC_R2_COMPLETED",
                            "status": "SUCCESS",
                            "message": "Synthetic R2 completion event",
                            "email_id": email_id,
                            "attachment_id": attachment_id,
                            "request_id": request_id,
                            "establishment_id": establishment_id,
                        }
                    )

                    exception_log_id = await repository.append_execution_log(
                        {
                            "run_id": run_id,
                            "logged_at": completed_at + timedelta(milliseconds=1),
                            "robot": "R1",
                            "event": "SYNTHETIC_EXCEPTION",
                            "status": "EXCEPTION",
                            "message": "Synthetic exception status",
                            "email_id": email_id,
                            "attachment_id": attachment_id,
                            "request_id": request_id,
                            "establishment_id": establishment_id,
                        }
                    )
                    assert exception_log_id > failure_log_id
                    exact_error = await repository.query_operational_analytics(
                        OperationalAnalyticsQuery(
                            grain="EVENT", metric="COUNT", time_basis="EVENT_OCCURRED",
                            start_at=completed_at, end_at=completed_at + timedelta(seconds=1),
                            status_filter="ERROR",
                        )
                    )
                    normalized_failures = await repository.query_operational_analytics(
                        OperationalAnalyticsQuery(
                            grain="EVENT", metric="COUNT", time_basis="EVENT_OCCURRED",
                            start_at=completed_at, end_at=completed_at + timedelta(seconds=1),
                            outcome_filter="FAILURE",
                        )
                    )
                    assert exact_error.total_count == 1
                    assert normalized_failures.total_count == 2
                    protocol_count = await repository.query_operational_analytics(
                        OperationalAnalyticsQuery(
                            grain="PROTOCOL", metric="COUNT", time_basis="PROTOCOL_OUTCOME_AT",
                            start_at=completed_at, end_at=completed_at + timedelta(seconds=1),
                            outcome_filter="FAILURE",
                        )
                    )
                    execution_count = await repository.query_operational_analytics(
                        OperationalAnalyticsQuery(
                            grain="EXECUTION", metric="COUNT", time_basis="EXECUTION_STARTED",
                            start_at=started_at, end_at=started_at + timedelta(seconds=1),
                        )
                    )
                    assert protocol_count.total_count == 1
                    assert execution_count.total_count == 2
                    raise _RollbackScenario()

            async with database.connection() as connection:
                repository = OperationalRepository(connection)
                assert await repository.get_service_request_by_protocol(protocol) is None
        finally:
            await database.close()

    run_async(validate())
