"""Centralized read-side mapping from raw Psycopg dict_row results to typed models."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.agent_api.app.database.models import (
    AutomationRunRecord,
    EmailAttachmentRecord,
    EstablishmentRecord,
    ExecutionFailureEvidence,
    ExecutionLogRecord,
    IncomingEmailRecord,
    ProtocolStatusFacts,
    RecentExecutedProtocolRecord,
    RAGDocumentRecord,
    RAGSourceRecord,
    SecurityEventRecord,
    ServiceRequestRecord,
)
from apps.agent_api.app.rag.models import (
    PersistedChunk,
    RetrievalProvenance,
    SearchCandidate,
)


class _SearchCandidateRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: int
    document_id: UUID
    content: str
    chunk_order: int
    section: str | None = None
    content_type: str
    metadata: Mapping[str, object]
    created_at: datetime

    source_id: UUID
    source_name: str
    source_type: str
    origin: str
    source_reference: str
    domain: str | None = None
    priority: int
    document_key: str
    title: str
    document_type: str
    content_checksum: str | None = None
    last_ingested_at: datetime | None = None

    retrieval_channel: Literal["lexical", "semantic"]
    channel_rank: int = Field(ge=1)
    channel_score: float | None = None


def map_rag_source(row: Mapping[str, object]) -> RAGSourceRecord:
    """Map a raw rag.sources row to RAGSourceRecord."""
    return RAGSourceRecord(**row)


def map_rag_document(row: Mapping[str, object]) -> RAGDocumentRecord:
    """Map a raw rag.documents row to RAGDocumentRecord."""
    return RAGDocumentRecord(**row)


def map_search_candidate(row: Mapping[str, object]) -> SearchCandidate:
    """Map a flattened lexical or semantic retrieval candidate row to SearchCandidate."""
    validated = _SearchCandidateRow(**row)
    return SearchCandidate(
        chunk=PersistedChunk(
            chunk_id=validated.chunk_id,
            document_id=validated.document_id,
            content=validated.content,
            chunk_order=validated.chunk_order,
            section=validated.section,
            content_type=validated.content_type,
            metadata=validated.metadata,
            created_at=validated.created_at,
        ),
        provenance=RetrievalProvenance(
            source_id=validated.source_id,
            source_name=validated.source_name,
            source_type=validated.source_type,
            origin=validated.origin,
            source_reference=validated.source_reference,
            domain=validated.domain,
            priority=validated.priority,
            document_id=validated.document_id,
            document_key=validated.document_key,
            title=validated.title,
            document_type=validated.document_type,
            content_checksum=validated.content_checksum,
            last_ingested_at=validated.last_ingested_at,
        ),
        retrieval_channel=validated.retrieval_channel,
        channel_rank=validated.channel_rank,
        channel_score=validated.channel_score,
    )


def map_automation_run(row: Mapping[str, object]) -> AutomationRunRecord:
    """Map a raw ops.automation_runs row to AutomationRunRecord."""
    return AutomationRunRecord(**row)


def map_incoming_email(row: Mapping[str, object]) -> IncomingEmailRecord:
    """Map a raw ops.incoming_emails row to IncomingEmailRecord."""
    return IncomingEmailRecord(**row)


def map_email_attachment(row: Mapping[str, object]) -> EmailAttachmentRecord:
    """Map a raw ops.email_attachments row to EmailAttachmentRecord."""
    return EmailAttachmentRecord(**row)


def map_service_request(row: Mapping[str, object]) -> ServiceRequestRecord:
    """Map a raw ops.service_requests row to ServiceRequestRecord."""
    return ServiceRequestRecord(**row)


def map_recent_executed_protocol(row: Mapping[str, object]) -> RecentExecutedProtocolRecord:
    """Map a request plus the latest authoritative run start timestamp."""
    data = dict(row)
    last_execution_at = data.pop("last_execution_at")
    return RecentExecutedProtocolRecord(
        service_request=map_service_request(data),
        last_execution_at=last_execution_at,
    )


def map_establishment(row: Mapping[str, object]) -> EstablishmentRecord:
    """Map a raw ops.establishments row to EstablishmentRecord."""
    return EstablishmentRecord(**row)


def map_execution_log(row: Mapping[str, object]) -> ExecutionLogRecord:
    """Map a raw ops.execution_log row to ExecutionLogRecord."""
    return ExecutionLogRecord(**row)


def map_protocol_status_facts(row: Mapping[str, object]) -> ProtocolStatusFacts:
    """Map a raw protocol status row including nested JSONB aggregates to ProtocolStatusFacts."""
    data = dict(row)
    raw_establishments = data.pop("establishments", ())
    raw_timeline = data.pop("execution_timeline", ())

    if isinstance(raw_establishments, Sequence) and not isinstance(raw_establishments, (str, bytes)):
        establishments = tuple(
            map_establishment(item) if isinstance(item, Mapping) else item  # type: ignore[arg-type]
            for item in raw_establishments
        )
    else:
        establishments = raw_establishments

    if isinstance(raw_timeline, Sequence) and not isinstance(raw_timeline, (str, bytes)):
        execution_timeline = tuple(
            map_execution_log(item) if isinstance(item, Mapping) else item  # type: ignore[arg-type]
            for item in raw_timeline
        )
    else:
        execution_timeline = raw_timeline

    return ProtocolStatusFacts(
        **data,
        establishments=establishments,
        execution_timeline=execution_timeline,
    )


def map_execution_failure_evidence(row: Mapping[str, object]) -> ExecutionFailureEvidence:
    """Map a raw execution failure row with optional previous success JSONB to ExecutionFailureEvidence."""
    data = dict(row)
    raw_evidence = data.pop("last_successful_evidence", None)
    if raw_evidence is not None:
        if isinstance(raw_evidence, Mapping):
            last_successful = map_execution_log(raw_evidence)
        else:
            last_successful = raw_evidence  # let Pydantic fail validation
    else:
        last_successful = None

    return ExecutionFailureEvidence(
        **data,
        last_successful_evidence=last_successful,
    )


def map_security_event(row: Mapping[str, object]) -> SecurityEventRecord:
    """Map a raw audit.security_events row to SecurityEventRecord."""
    return SecurityEventRecord(**row)
