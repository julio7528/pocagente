"""Generic repository-backed materialization of validated OPS seed lifecycles."""

from __future__ import annotations

from apps.agent_api.app.database.repositories.operational import OperationalRepository
from database.seed.ops.models import OpsSeedResult, OpsSeedScenario, SeedEvent


def _references(event: SeedEvent, identities: dict[str, int]) -> dict[str, int | None]:
    return {
        f"{name}_id": identities[name] if name in event.references else None
        for name in identities
    }


async def _append_event(
    repository: OperationalRepository,
    event: SeedEvent,
    *,
    run_id: int,
    robot: str,
    identities: dict[str, int],
) -> None:
    await repository.append_execution_log(
        {
            "run_id": run_id,
            "logged_at": event.timestamp,
            "robot": robot,
            "event": event.event,
            "status": event.status,
            "message": event.message,
            **_references(event, identities),
        }
    )


async def execute_ops_scenario(
    repository: OperationalRepository,
    scenario: OpsSeedScenario,
) -> OpsSeedResult:
    """Persist one supported R1/R2 lifecycle without scenario-ID branches."""

    existing = await repository.get_service_request_by_protocol(scenario.protocol_number)
    if existing is not None:
        return OpsSeedResult(
            scenario_id=scenario.scenario_id,
            protocol_number=scenario.protocol_number,
            created=False,
            request_id=existing.request_id,
        )

    r1_run_id = await repository.create_automation_run(
        {"robot": "R1", "started_at": scenario.r1.started_at}
    )
    email_id = await repository.create_incoming_email(
        {
            "run_id": r1_run_id,
            "received_at": scenario.email.received_at,
            "sender": scenario.email.sender,
            "recipient": scenario.email.recipient,
            "subject": scenario.email.subject,
            "attachment_count": scenario.email.attachment_count,
        }
    )
    identities = {"email": email_id, "attachment": 0, "request": 0, "establishment": 0}
    for event in scenario.r1.events[:2]:
        await _append_event(repository, event, run_id=r1_run_id, robot="R1", identities=identities)

    attachment_id = await repository.create_email_attachment(
        {
            "email_id": email_id,
            "file_name": scenario.attachment.file_name,
            "file_type": scenario.attachment.file_type,
            "received_at": scenario.attachment.received_at,
        }
    )
    identities["attachment"] = attachment_id
    await _append_event(repository, scenario.r1.events[2], run_id=r1_run_id, robot="R1", identities=identities)
    await repository.update_email_attachment(
        attachment_id,
        {
            "validation_status": scenario.attachment.validation_status,
            "validation_message": scenario.attachment.validation_message,
            "establishment_count": scenario.attachment.establishment_count,
            "processing_status": scenario.attachment.processing_status,
        },
    )
    await repository.update_incoming_email(
        email_id,
        {
            "processed_at": scenario.email.processed_at,
            "sender_status": scenario.email.sender_status,
            "processing_status": scenario.email.processing_status,
        },
    )
    await _append_event(repository, scenario.r1.events[3], run_id=r1_run_id, robot="R1", identities=identities)

    request_id = await repository.create_service_request(
        {
            "protocol_number": scenario.protocol_number,
            "email_id": email_id,
            "r1_run_id": r1_run_id,
            "updated_at": scenario.request.initial_updated_at,
        }
    )
    identities["request"] = request_id
    await _append_event(repository, scenario.r1.events[4], run_id=r1_run_id, robot="R1", identities=identities)
    establishment_id = await repository.upsert_establishment(
        {
            "request_id": request_id,
            "attachment_id": attachment_id,
            "establishment_number": scenario.establishment.establishment_number,
            "generated_file_name": scenario.establishment.generated_file_name,
            "processing_status": "PENDING",
            "updated_at": scenario.r1.events[5].timestamp,
        }
    )
    identities["establishment"] = establishment_id
    for event in scenario.r1.events[5:7]:
        await _append_event(repository, event, run_id=r1_run_id, robot="R1", identities=identities)
    await repository.update_establishment(
        establishment_id,
        {
            "processing_status": scenario.establishment.r1_processing_status,
            "upload_status": scenario.establishment.r1_upload_status,
            "upload_at": scenario.establishment.r1_upload_at,
            "download_status": scenario.establishment.r1_download_status,
            "updated_at": scenario.establishment.r1_state_at,
        },
    )
    await _append_event(repository, scenario.r1.events[7], run_id=r1_run_id, robot="R1", identities=identities)
    r1_request_changes = {
        "updated_at": scenario.request.r1_updated_at,
        "status": scenario.request.r1_status,
    }
    if scenario.request.r1_status == "FAILED":
        r1_request_changes["failure_reason"] = scenario.request.failure_reason
    await repository.update_service_request(request_id, r1_request_changes)
    for event in scenario.r1.events[8:]:
        await _append_event(repository, event, run_id=r1_run_id, robot="R1", identities=identities)
    await repository.update_automation_run(
        r1_run_id,
        {"finished_at": scenario.r1.finished_at, "status": scenario.r1.status, "result_message": scenario.r1.result_message},
    )

    if scenario.r2 is None:
        await repository.update_establishment(
            establishment_id,
            {
                "processing_status": scenario.establishment.final_processing_status,
                "upload_status": scenario.establishment.final_upload_status,
                "download_status": scenario.establishment.final_download_status,
                "download_at": scenario.establishment.download_at,
                "return_email_at": scenario.establishment.return_email_at,
                "result_message": scenario.establishment.result_message,
                "updated_at": scenario.establishment.final_at,
            },
        )
        await repository.update_service_request(
            request_id,
            {
                "updated_at": scenario.request.final_updated_at,
                "status": scenario.request.final_status,
                "result": scenario.request.result,
                "failure_reason": scenario.request.failure_reason,
                "completed_at": scenario.request.completed_at,
                "return_email_at": scenario.request.return_email_at,
            },
        )
        return OpsSeedResult(
            scenario_id=scenario.scenario_id,
            protocol_number=scenario.protocol_number,
            created=True,
            r1_run_id=r1_run_id,
            email_id=email_id,
            attachment_id=attachment_id,
            request_id=request_id,
            establishment_id=establishment_id,
        )

    r2_run_id = await repository.create_automation_run(
        {"robot": "R2", "started_at": scenario.r2.started_at}
    )
    for event in scenario.r2.events[:2]:
        await _append_event(repository, event, run_id=r2_run_id, robot="R2", identities=identities)
    await repository.update_establishment(
        establishment_id,
        {
            "processing_status": scenario.establishment.available_processing_status,
            "download_status": scenario.establishment.available_download_status,
            "updated_at": scenario.establishment.available_at,
        },
    )
    await _append_event(repository, scenario.r2.events[2], run_id=r2_run_id, robot="R2", identities=identities)
    await repository.update_establishment(
        establishment_id,
        {
            "processing_status": scenario.establishment.final_processing_status,
            "upload_status": scenario.establishment.final_upload_status,
            "download_status": scenario.establishment.final_download_status,
            "download_at": scenario.establishment.download_at,
            "return_email_at": scenario.establishment.return_email_at,
            "result_message": scenario.establishment.result_message,
            "updated_at": scenario.establishment.final_at,
        },
    )
    await repository.update_service_request(
        request_id,
        {
            "updated_at": scenario.request.final_updated_at,
            "status": scenario.request.final_status,
            "result": scenario.request.result,
            "failure_reason": scenario.request.failure_reason,
            "completed_at": scenario.request.completed_at,
            "return_email_at": scenario.request.return_email_at,
        },
    )
    for event in scenario.r2.events[3:]:
        await _append_event(repository, event, run_id=r2_run_id, robot="R2", identities=identities)
    await repository.update_automation_run(
        r2_run_id,
        {"finished_at": scenario.r2.finished_at, "status": scenario.r2.status, "result_message": scenario.r2.result_message},
    )
    return OpsSeedResult(
        scenario_id=scenario.scenario_id,
        protocol_number=scenario.protocol_number,
        created=True,
        r1_run_id=r1_run_id,
        r2_run_id=r2_run_id,
        email_id=email_id,
        attachment_id=attachment_id,
        request_id=request_id,
        establishment_id=establishment_id,
    )
