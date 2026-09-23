"""Typed Pydantic read models for database query results across RAG, OPS, and AUDIT."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RAGSourceRecord(BaseModel):
    """Factual read model for rag.sources rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: UUID
    name: str
    source_type: str
    origin: str
    reference: str
    domain: str | None = None
    status: str
    priority: int
    created_at: datetime
    updated_at: datetime


class RAGDocumentRecord(BaseModel):
    """Factual read model for rag.documents rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: UUID
    source_id: UUID
    document_key: str
    title: str
    document_type: str
    content_checksum: str | None = None
    status: str
    last_ingested_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AutomationRunRecord(BaseModel):
    """Factual read model for ops.automation_runs rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: int
    robot: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    result_message: str | None = None
    created_at: datetime


class IncomingEmailRecord(BaseModel):
    """Typed read model for an OPS incoming email and its R1 provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    email_id: int
    run_id: int
    received_at: datetime
    processed_at: datetime | None = None
    sender: str
    recipient: str
    subject: str | None = None
    attachment_count: int
    sender_status: str
    processing_status: str
    rejection_reason: str | None = None
    created_at: datetime


class EmailAttachmentRecord(BaseModel):
    """Typed read model for an OPS email attachment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attachment_id: int
    email_id: int
    file_name: str
    file_type: str | None = None
    received_at: datetime
    validation_status: str
    validation_message: str | None = None
    establishment_count: int | None = None
    processing_status: str
    created_at: datetime


class ServiceRequestRecord(BaseModel):
    """Factual read model for ops.service_requests rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: int
    protocol_number: str
    email_id: int
    r1_run_id: int
    created_at: datetime
    updated_at: datetime
    status: str
    result: str | None = None
    failure_reason: str | None = None
    completed_at: datetime | None = None
    return_email_at: datetime | None = None


class RecentExecutedProtocolRecord(BaseModel):
    """A request paired with the actual latest automation-run start timestamp."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    service_request: ServiceRequestRecord
    last_execution_at: datetime


class EstablishmentRecord(BaseModel):
    """Factual read model for ops.establishments rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    establishment_id: int
    request_id: int
    attachment_id: int
    establishment_number: str
    generated_file_name: str
    processing_status: str
    upload_status: str
    upload_at: datetime | None = None
    download_status: str
    download_at: datetime | None = None
    return_email_at: datetime | None = None
    result_message: str | None = None
    updated_at: datetime


class ExecutionLogRecord(BaseModel):
    """Factual read model for ops.execution_log rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    log_id: int
    run_id: int
    logged_at: datetime
    robot: str
    event: str
    status: str
    message: str
    email_id: int | None = None
    attachment_id: int | None = None
    request_id: int | None = None
    establishment_id: int | None = None
    created_at: datetime


class ProtocolStatusFacts(BaseModel):
    """Structured factual representation of a protocol's request, establishments, and timeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: int
    protocol_number: str
    email_id: int
    r1_run_id: int
    created_at: datetime
    updated_at: datetime
    status: str
    result: str | None = None
    failure_reason: str | None = None
    completed_at: datetime | None = None
    return_email_at: datetime | None = None
    establishments: tuple[EstablishmentRecord, ...] = ()
    execution_timeline: tuple[ExecutionLogRecord, ...] = ()


class ExecutionFailureEvidence(BaseModel):
    """Factual evidence of an execution failure and optional previous success."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: int
    protocol_number: str
    request_status: str
    failure_reason: str | None = None
    run_id: int
    robot: str
    started_at: datetime
    finished_at: datetime | None = None
    run_status: str
    run_result_message: str | None = None
    log_id: int
    logged_at: datetime
    event: str
    event_status: str
    event_message: str
    email_id: int | None = None
    attachment_id: int | None = None
    establishment_id: int | None = None
    last_successful_evidence: ExecutionLogRecord | None = None


class ProtocolCaseFacts(BaseModel):
    """Facts correlated for one protocol; absent fields were not requested or unavailable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    service_request: ServiceRequestRecord
    incoming_email: IncomingEmailRecord | None = None
    attachments: tuple[EmailAttachmentRecord, ...] = ()
    automation_runs: tuple[AutomationRunRecord, ...] = ()
    establishments: tuple[EstablishmentRecord, ...] = ()
    execution_timeline: tuple[ExecutionLogRecord, ...] = ()
    failure_evidence: tuple[ExecutionFailureEvidence, ...] = ()


class SecurityEventRecord(BaseModel):
    """Factual read model for audit.security_events rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: int
    occurred_at: datetime
    event_type: str
    source_component: str
    user_identifier: str | None = None
    request_reference: str | None = None
    resource_category: str | None = None
    sanitized_content: str | None = None
    action_taken: str
    result: str
    review_status: str
    reviewed_at: datetime | None = None
    review_note: str | None = None
    created_at: datetime
