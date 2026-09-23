"""Async repository contracts for the three approved database domains."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Final, Literal, Protocol, TypeAlias
from uuid import UUID

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
from apps.agent_api.app.rag.models import SearchCandidate
from apps.agent_api.app.rag.scope import KnowledgeScope

RepositoryRecord: TypeAlias = Mapping[str, object]
IngestionOperation: TypeAlias = Literal["INGEST", "REINGEST", "SKIPPED_UNCHANGED"]
IngestionStatus: TypeAlias = Literal["SUCCESS", "ERROR", "SKIPPED"]
ReviewStatus: TypeAlias = Literal["UNREVIEWED", "REVIEWED"]

RAG_OWNED_TABLES: Final = (
    "rag.sources",
    "rag.documents",
    "rag.chunks",
    "rag.ingestion_runs",
)
OPS_OWNED_TABLES: Final = (
    "ops.automation_runs",
    "ops.incoming_emails",
    "ops.email_attachments",
    "ops.service_requests",
    "ops.establishments",
    "ops.execution_log",
)
AUDIT_OWNED_TABLES: Final = ("audit.security_events",)


class RAGRepositoryContract(Protocol):
    """Persistence and retrieval boundary for the four RAG tables."""

    async def get_source_by_id(self, source_id: UUID) -> RAGSourceRecord | None: ...

    async def get_source_by_reference(
        self,
        origin: str,
        reference: str,
    ) -> RAGSourceRecord | None: ...

    async def register_source(self, source: RepositoryRecord) -> RAGSourceRecord: ...

    async def get_document_by_id(
        self,
        document_id: UUID,
    ) -> RAGDocumentRecord | None: ...

    async def get_document_by_key(
        self,
        source_id: UUID,
        document_key: str,
    ) -> RAGDocumentRecord | None: ...

    async def document_checksum_changed(
        self,
        document_id: UUID,
        content_checksum: str,
    ) -> bool: ...

    async def save_document(self, document: RepositoryRecord) -> RAGDocumentRecord: ...

    async def replace_document_chunks(
        self,
        document_id: UUID,
        chunks: Sequence[RepositoryRecord],
    ) -> None: ...

    async def start_ingestion_run(
        self,
        source_id: UUID,
        document_id: UUID | None,
        operation: IngestionOperation,
    ) -> int: ...

    async def finish_ingestion_run(
        self,
        ingestion_run_id: int,
        *,
        status: IngestionStatus,
        finished_at: datetime,
        chunks_created: int,
        result_message: str | None,
    ) -> None: ...

    async def search_lexical_candidates(
        self,
        query: str,
        limit: int,
        knowledge_scope: KnowledgeScope,
    ) -> Sequence[SearchCandidate]: ...

    async def search_semantic_candidates(
        self,
        embedding: Sequence[float],
        limit: int,
        knowledge_scope: KnowledgeScope,
    ) -> Sequence[SearchCandidate]: ...


class OperationalRepositoryContract(Protocol):
    """Persistence and factual query boundary for the six OPS tables."""

    async def create_automation_run(self, run: RepositoryRecord) -> int: ...

    async def update_automation_run(
        self,
        run_id: int,
        changes: RepositoryRecord,
    ) -> None: ...

    async def get_automation_run(self, run_id: int) -> AutomationRunRecord | None: ...

    async def create_incoming_email(self, email: RepositoryRecord) -> int: ...

    async def update_incoming_email(
        self,
        email_id: int,
        changes: RepositoryRecord,
    ) -> None: ...

    async def create_email_attachment(self, attachment: RepositoryRecord) -> int: ...

    async def update_email_attachment(
        self,
        attachment_id: int,
        changes: RepositoryRecord,
    ) -> None: ...

    async def create_service_request(self, request: RepositoryRecord) -> int: ...

    async def update_service_request(
        self,
        request_id: int,
        changes: RepositoryRecord,
    ) -> None: ...

    async def get_service_request_by_protocol(
        self,
        protocol_number: str,
    ) -> ServiceRequestRecord | None: ...

    async def list_recent_service_requests(self, limit: int) -> Sequence[ServiceRequestRecord]: ...

    async def upsert_establishment(self, establishment: RepositoryRecord) -> int: ...

    async def update_establishment(
        self,
        establishment_id: int,
        changes: RepositoryRecord,
    ) -> None: ...

    async def list_establishments_for_request(
        self,
        request_id: int,
    ) -> Sequence[EstablishmentRecord]: ...

    async def append_execution_log(self, event: RepositoryRecord) -> int: ...

    async def list_execution_timeline_for_run(
        self,
        run_id: int,
        limit: int,
    ) -> Sequence[ExecutionLogRecord]: ...

    async def list_execution_timeline_for_request(
        self,
        request_id: int,
        limit: int,
    ) -> Sequence[ExecutionLogRecord]: ...

    async def get_protocol_status_facts(
        self,
        protocol_number: str,
    ) -> Sequence[ProtocolStatusFacts]: ...

    async def get_execution_failure_facts(
        self,
        protocol_number: str,
        run_id: int | None = None,
    ) -> Sequence[ExecutionFailureEvidence]: ...


class AuditRepositoryContract(Protocol):
    """Sanitized security-event persistence and review boundary."""

    async def write_sanitized_security_event(self, event: RepositoryRecord) -> int: ...

    async def get_security_event(
        self,
        event_id: int,
    ) -> SecurityEventRecord | None: ...

    async def list_security_events_by_request_reference(
        self,
        request_reference: str,
        limit: int,
    ) -> Sequence[SecurityEventRecord]: ...

    async def list_unreviewed_security_events(
        self,
        limit: int,
    ) -> Sequence[SecurityEventRecord]: ...

    async def update_security_event_review(
        self,
        event_id: int,
        *,
        review_status: ReviewStatus,
        reviewed_at: datetime | None,
        review_note: str | None,
    ) -> None: ...
