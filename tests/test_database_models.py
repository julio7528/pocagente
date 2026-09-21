"""Tests for typed database read models."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from apps.agent_api.app.database.models import (
    AutomationRunRecord,
    EstablishmentRecord,
    ExecutionFailureEvidence,
    ExecutionLogRecord,
    ProtocolStatusFacts,
    RAGDocumentRecord,
    RAGSourceRecord,
    SecurityEventRecord,
    ServiceRequestRecord,
)


def test_rag_source_record_validation() -> None:
    now = datetime.now(timezone.utc)
    source_id = uuid4()
    record = RAGSourceRecord(
        source_id=source_id,
        name="Getnet Portal",
        source_type="INTERNAL_DOCUMENT",
        origin="INTERNAL",
        reference="DOC-001",
        domain="finance",
        status="ACTIVE",
        priority=1,
        created_at=now,
        updated_at=now,
    )
    assert record.source_id == source_id
    assert record.priority == 1
    assert record.domain == "finance"

    # Extra fields rejected
    with pytest.raises(ValidationError):
        RAGSourceRecord(
            source_id=source_id,
            name="Getnet Portal",
            source_type="INTERNAL_DOCUMENT",
            origin="INTERNAL",
            reference="DOC-001",
            domain=None,
            status="ACTIVE",
            priority=1,
            created_at=now,
            updated_at=now,
            unexpected_field="disallowed",
        )

    # Missing required field rejected
    with pytest.raises(ValidationError):
        RAGSourceRecord(
            source_id=source_id,
            # name missing
            source_type="INTERNAL_DOCUMENT",
            origin="INTERNAL",
            reference="DOC-001",
            status="ACTIVE",
            priority=1,
            created_at=now,
            updated_at=now,
        )


def test_rag_document_record_validation() -> None:
    now = datetime.now(timezone.utc)
    doc_id = uuid4()
    src_id = uuid4()
    record = RAGDocumentRecord(
        document_id=doc_id,
        source_id=src_id,
        document_key="doc-key-1",
        title="Document Title",
        document_type="PDD",
        content_checksum="a" * 64,
        status="ACTIVE",
        last_ingested_at=now,
        created_at=now,
        updated_at=now,
    )
    assert record.document_id == doc_id
    assert record.content_checksum == "a" * 64

    # Nullable fields default to None
    minimal = RAGDocumentRecord(
        document_id=doc_id,
        source_id=src_id,
        document_key="doc-key-1",
        title="Document Title",
        document_type="PDD",
        status="PENDING",
        created_at=now,
        updated_at=now,
    )
    assert minimal.content_checksum is None
    assert minimal.last_ingested_at is None


def test_automation_run_record_validation() -> None:
    now = datetime.now(timezone.utc)
    run = AutomationRunRecord(
        run_id=10,
        robot="R1",
        started_at=now,
        finished_at=None,
        status="RUNNING",
        result_message=None,
        created_at=now,
    )
    assert run.run_id == 10
    assert run.finished_at is None

    with pytest.raises(ValidationError):
        AutomationRunRecord(
            run_id="not_an_int",
            robot="R1",
            started_at=now,
            status="RUNNING",
            created_at=now,
        )


def test_service_request_record_validation() -> None:
    now = datetime.now(timezone.utc)
    req = ServiceRequestRecord(
        request_id=1,
        protocol_number="PROT-2026-001",
        email_id=2,
        r1_run_id=3,
        created_at=now,
        updated_at=now,
        status="CREATED",
    )
    assert req.protocol_number == "PROT-2026-001"
    assert req.completed_at is None
    assert req.failure_reason is None


def test_establishment_record_validation() -> None:
    now = datetime.now(timezone.utc)
    est = EstablishmentRecord(
        establishment_id=100,
        request_id=1,
        attachment_id=5,
        establishment_number="00012345",
        generated_file_name="arq_00012345.txt",
        processing_status="PENDING",
        upload_status="PENDING",
        download_status="NOT_AVAILABLE",
        updated_at=now,
    )
    assert est.establishment_number == "00012345"
    assert est.upload_at is None


def test_execution_log_record_validation() -> None:
    now = datetime.now(timezone.utc)
    log = ExecutionLogRecord(
        log_id=50,
        run_id=10,
        logged_at=now,
        robot="R1",
        event="FILE_UPLOADED",
        status="SUCCESS",
        message="File processed successfully",
        created_at=now,
    )
    assert log.log_id == 50
    assert log.email_id is None
    assert log.request_id is None


def test_protocol_status_facts_nested_typing() -> None:
    now = datetime.now(timezone.utc)
    est = EstablishmentRecord(
        establishment_id=100,
        request_id=1,
        attachment_id=5,
        establishment_number="00012345",
        generated_file_name="arq_00012345.txt",
        processing_status="PENDING",
        upload_status="PENDING",
        download_status="NOT_AVAILABLE",
        updated_at=now,
    )
    log = ExecutionLogRecord(
        log_id=50,
        run_id=10,
        logged_at=now,
        robot="R1",
        event="FILE_UPLOADED",
        status="SUCCESS",
        message="File processed successfully",
        created_at=now,
    )
    facts = ProtocolStatusFacts(
        request_id=1,
        protocol_number="PROT-2026-001",
        email_id=2,
        r1_run_id=3,
        created_at=now,
        updated_at=now,
        status="PROCESSING",
        establishments=(est,),
        execution_timeline=(log,),
    )
    assert len(facts.establishments) == 1
    assert facts.establishments[0].establishment_number == "00012345"
    assert len(facts.execution_timeline) == 1
    assert facts.execution_timeline[0].event == "FILE_UPLOADED"

    # Reject malformed nested object
    with pytest.raises(ValidationError):
        ProtocolStatusFacts(
            request_id=1,
            protocol_number="PROT-2026-001",
            email_id=2,
            r1_run_id=3,
            created_at=now,
            updated_at=now,
            status="PROCESSING",
            establishments=({"bad": "object"},),  # type: ignore[arg-type]
        )


def test_execution_failure_evidence_validation() -> None:
    now = datetime.now(timezone.utc)
    prev_log = ExecutionLogRecord(
        log_id=49,
        run_id=9,
        logged_at=now,
        robot="R1",
        event="LOGIN",
        status="SUCCESS",
        message="Logged in",
        created_at=now,
    )
    evidence = ExecutionFailureEvidence(
        request_id=1,
        protocol_number="PROT-2026-001",
        request_status="FAILED",
        failure_reason="Timeout during upload",
        run_id=10,
        robot="R1",
        started_at=now,
        run_status="ERROR",
        log_id=50,
        logged_at=now,
        event="UPLOAD_FAILED",
        event_status="ERROR",
        event_message="Connection timed out",
        last_successful_evidence=prev_log,
    )
    assert evidence.last_successful_evidence is not None
    assert evidence.last_successful_evidence.log_id == 49

    # Without previous success
    evidence_no_prev = ExecutionFailureEvidence(
        request_id=1,
        protocol_number="PROT-2026-001",
        request_status="FAILED",
        run_id=10,
        robot="R1",
        started_at=now,
        run_status="ERROR",
        log_id=50,
        logged_at=now,
        event="UPLOAD_FAILED",
        event_status="ERROR",
        event_message="Connection timed out",
        last_successful_evidence=None,
    )
    assert evidence_no_prev.last_successful_evidence is None


def test_security_event_record_validation() -> None:
    now = datetime.now(timezone.utc)
    event = SecurityEventRecord(
        event_id=1,
        occurred_at=now,
        event_type="PROMPT_INJECTION",
        source_component="guardrail",
        user_identifier="user_123",
        request_reference="REQ-001",
        resource_category=None,
        sanitized_content="attempted bypass",
        action_taken="BLOCK",
        result="SUCCESS",
        review_status="UNREVIEWED",
        reviewed_at=None,
        review_note=None,
        created_at=now,
    )
    assert event.event_id == 1
    assert event.action_taken == "BLOCK"
    assert event.review_status == "UNREVIEWED"

    # Extra fields rejected
    with pytest.raises(ValidationError):
        SecurityEventRecord(
            event_id=1,
            occurred_at=now,
            event_type="PROMPT_INJECTION",
            source_component="guardrail",
            action_taken="BLOCK",
            result="SUCCESS",
            review_status="UNREVIEWED",
            created_at=now,
            secret="disallowed",
        )


def test_models_are_frozen() -> None:
    now = datetime.now(timezone.utc)
    run = AutomationRunRecord(
        run_id=10,
        robot="R1",
        started_at=now,
        status="RUNNING",
        created_at=now,
    )
    with pytest.raises(ValidationError):
        run.status = "SUCCESS"  # type: ignore[misc]
