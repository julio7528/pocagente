"""Read-only, authorization-gated OPS tools over approved repository contracts."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from time import perf_counter
from time import perf_counter
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.agent_api.app.database.models import (
    AutomationRunRecord, EmailAttachmentRecord, EstablishmentRecord, ExecutionFailureEvidence,
    ExecutionLogRecord, IncomingEmailRecord, ProtocolCaseFacts, ProtocolStatusFacts,
    RecentExecutedProtocolRecord, ServiceRequestRecord,
)
from apps.agent_api.app.telemetry import RuntimeEventKind, emit_runtime_event


class OperationalFactsRepository(Protocol):
    """Narrow read methods already owned by ``OperationalRepository``."""

    async def get_protocol_status_facts(
        self, protocol_number: str
    ) -> Sequence[ProtocolStatusFacts]:
        """Return factual protocol status records."""

    async def get_execution_failure_facts(
        self, protocol_number: str, run_id: int | None = None
    ) -> Sequence[ExecutionFailureEvidence]:
        """Return factual execution-failure evidence."""

    async def list_recent_service_requests(self, limit: int) -> Sequence[ServiceRequestRecord]:
        """Return protocols ordered by authoritative request creation time."""

    async def list_recent_protocols_by_execution(self, limit: int) -> Sequence[RecentExecutedProtocolRecord]: ...

    async def get_service_request_by_protocol(self, protocol_number: str) -> ServiceRequestRecord | None: ...
    async def get_incoming_email(self, email_id: int) -> IncomingEmailRecord | None: ...
    async def list_email_attachments(self, email_id: int) -> Sequence[EmailAttachmentRecord]: ...
    async def list_automation_runs_for_request(self, request_id: int) -> Sequence[AutomationRunRecord]: ...
    async def list_establishments_for_request(self, request_id: int) -> Sequence[EstablishmentRecord]: ...
    async def list_execution_timeline_for_request(self, request_id: int, limit: int) -> Sequence[ExecutionLogRecord]: ...


class ProtocolCaseToolResult(BaseModel):
    """Controlled result for an authorized bounded protocol investigation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: OpsToolStatus
    facts: ProtocolCaseFacts | None = None
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def status_matches_facts(self) -> ProtocolCaseToolResult:
        if (self.status is OpsToolStatus.SUCCESS) != (self.facts is not None):
            raise ValueError("protocol case facts must match success status")
        return self


class OpsAccessContext(BaseModel):
    """Minimal authorization decision supplied by a future application boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    principal_id: str = Field(min_length=1)
    can_read_operational_facts: bool


class OpsToolStatus(StrEnum):
    """Controlled outcomes shared by the two read-only OPS tools."""

    SUCCESS = "SUCCESS"
    INVALID_INPUT = "INVALID_INPUT"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    REPOSITORY_ERROR = "REPOSITORY_ERROR"


class OpsEvidenceCategory(StrEnum):
    """Closed application-owned categories a support plan may request."""

    SERVICE_REQUEST = "SERVICE_REQUEST"
    ORIGIN_EMAIL = "ORIGIN_EMAIL"
    EMAIL_ATTACHMENTS = "EMAIL_ATTACHMENTS"
    AUTOMATION_RUNS = "AUTOMATION_RUNS"
    ESTABLISHMENTS = "ESTABLISHMENTS"
    EXECUTION_TIMELINE = "EXECUTION_TIMELINE"
    FAILURE_EVIDENCE = "FAILURE_EVIDENCE"


class ProtocolStatusToolResult(BaseModel):
    """Safe outcome of one protocol-status lookup."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: OpsToolStatus
    facts: ProtocolStatusFacts | None = None
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def facts_match_status(self) -> ProtocolStatusToolResult:
        if self.status is OpsToolStatus.SUCCESS and self.facts is None:
            raise ValueError("successful protocol lookup requires facts")
        if self.status is not OpsToolStatus.SUCCESS and self.facts is not None:
            raise ValueError("non-success protocol lookup cannot contain facts")
        return self


class ExecutionFailureToolResult(BaseModel):
    """Safe outcome of one execution-failure inspection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: OpsToolStatus
    evidence: tuple[ExecutionFailureEvidence, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def evidence_matches_status(self) -> ExecutionFailureToolResult:
        if self.status is OpsToolStatus.SUCCESS and not self.evidence:
            raise ValueError("successful failure inspection requires evidence")
        if self.status is not OpsToolStatus.SUCCESS and self.evidence:
            raise ValueError("non-success failure inspection cannot contain evidence")
        return self


class RecentProtocolsToolResult(BaseModel):
    """Safe outcome of an authorized bounded recent-protocol query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: OpsToolStatus
    records: tuple[ServiceRequestRecord, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def records_match_status(self) -> RecentProtocolsToolResult:
        if self.status is OpsToolStatus.SUCCESS and not self.records:
            raise ValueError("successful recent-protocol lookup requires records")
        if self.status is not OpsToolStatus.SUCCESS and self.records:
            raise ValueError("non-success recent-protocol lookup cannot contain records")
        return self


class RecentExecutedProtocolsToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: OpsToolStatus
    records: tuple[RecentExecutedProtocolRecord, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def records_match_status(self) -> RecentExecutedProtocolsToolResult:
        if self.status is OpsToolStatus.SUCCESS and not self.records:
            raise ValueError("successful execution discovery requires records")
        if self.status is not OpsToolStatus.SUCCESS and self.records:
            raise ValueError("non-success execution discovery cannot contain records")
        return self


class OperationalTools:
    """Expose approved OPS facts without SQL, connections, or diagnosis logic."""

    def __init__(self, repository: OperationalFactsRepository) -> None:
        self._repository = repository

    async def investigate_protocol(
        self,
        protocol_number: str,
        evidence_needs: Sequence[OpsEvidenceCategory],
        authorization: OpsAccessContext,
    ) -> ProtocolCaseToolResult:
        """Resolve validated evidence categories through fixed read-only repository methods."""
        if not self._valid_protocol(protocol_number):
            return ProtocolCaseToolResult(status=OpsToolStatus.INVALID_INPUT, reason="INVALID_PROTOCOL_NUMBER")
        if not authorization.can_read_operational_facts:
            emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="investigate_protocol", value="DENIED")
            return ProtocolCaseToolResult(status=OpsToolStatus.UNAUTHORIZED, reason="OPERATIONAL_ACCESS_DENIED")

        emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="investigate_protocol", value="STARTED", protocol_number=protocol_number)
        requested = set(evidence_needs)
        requested.add(OpsEvidenceCategory.SERVICE_REQUEST)

        async def read(name: str, call):
            started = perf_counter()
            emit_runtime_event(RuntimeEventKind.REPOSITORY, name=name, value="STARTED", protocol_number=protocol_number)
            result = await call
            count = len(result) if isinstance(result, (tuple, list)) else int(result is not None)
            emit_runtime_event(
                RuntimeEventKind.REPOSITORY, name=name, value="COMPLETED", count=count,
                elapsed_ms=int((perf_counter() - started) * 1000), protocol_number=protocol_number,
            )
            return result
        try:
            request = await read(
                "get_service_request_by_protocol",
                self._repository.get_service_request_by_protocol(protocol_number),
            )
            if request is None:
                emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="investigate_protocol", value="NOT_FOUND")
                return ProtocolCaseToolResult(status=OpsToolStatus.NOT_FOUND, reason="PROTOCOL_NOT_FOUND")

            incoming_email = None
            attachments: tuple[EmailAttachmentRecord, ...] = ()
            runs: tuple[AutomationRunRecord, ...] = ()
            establishments: tuple[EstablishmentRecord, ...] = ()
            timeline: tuple[ExecutionLogRecord, ...] = ()
            failures: tuple[ExecutionFailureEvidence, ...] = ()

            if OpsEvidenceCategory.ORIGIN_EMAIL in requested or OpsEvidenceCategory.EMAIL_ATTACHMENTS in requested:
                incoming_email = await read("get_incoming_email", self._repository.get_incoming_email(request.email_id))
            if OpsEvidenceCategory.EMAIL_ATTACHMENTS in requested:
                attachments = tuple(await read("list_email_attachments", self._repository.list_email_attachments(request.email_id)))
            if OpsEvidenceCategory.AUTOMATION_RUNS in requested:
                runs = tuple(await read("list_automation_runs_for_request", self._repository.list_automation_runs_for_request(request.request_id)))
            if OpsEvidenceCategory.ESTABLISHMENTS in requested:
                establishments = tuple(await read("list_establishments_for_request", self._repository.list_establishments_for_request(request.request_id)))
            if OpsEvidenceCategory.EXECUTION_TIMELINE in requested:
                timeline = tuple(await read("list_execution_timeline_for_request", self._repository.list_execution_timeline_for_request(request.request_id, 100)))
            if OpsEvidenceCategory.FAILURE_EVIDENCE in requested:
                failures = tuple(await read("get_execution_failure_facts", self._repository.get_execution_failure_facts(protocol_number)))
        except Exception:
            emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="investigate_protocol", value="CONTROLLED_ERROR")
            return ProtocolCaseToolResult(status=OpsToolStatus.REPOSITORY_ERROR, reason="PROTOCOL_CASE_FACTS_UNAVAILABLE")

        facts = ProtocolCaseFacts(
            service_request=request,
            incoming_email=incoming_email,
            attachments=attachments,
            automation_runs=runs,
            establishments=establishments,
            execution_timeline=timeline,
            failure_evidence=failures,
        )
        emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="investigate_protocol", value="SUCCESS", count=len(timeline), protocol_number=protocol_number)
        return ProtocolCaseToolResult(status=OpsToolStatus.SUCCESS, facts=facts, reason="OBSERVED_PROTOCOL_CASE_FACTS")

    async def lookup_protocol_status(
        self,
        protocol_number: str,
        authorization: OpsAccessContext,
    ) -> ProtocolStatusToolResult:
        """Return observed facts for one authorized protocol, never a diagnosis."""

        if not self._valid_protocol(protocol_number):
            return ProtocolStatusToolResult(
                status=OpsToolStatus.INVALID_INPUT,
                reason="INVALID_PROTOCOL_NUMBER",
            )
        if not authorization.can_read_operational_facts:
            emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="lookup_protocol_status", value="DENIED")
            return ProtocolStatusToolResult(
                status=OpsToolStatus.UNAUTHORIZED,
                reason="OPERATIONAL_ACCESS_DENIED",
            )
        emit_runtime_event(
            RuntimeEventKind.OPS_TOOL,
            name="lookup_protocol_status",
            value="STARTED",
            protocol_number=protocol_number,
        )
        started_at = perf_counter()
        try:
            facts = tuple(await self._repository.get_protocol_status_facts(protocol_number))
        except Exception:
            emit_runtime_event(
                RuntimeEventKind.REPOSITORY,
                name="get_protocol_status_facts",
                value="CONTROLLED_ERROR",
                elapsed_ms=int((perf_counter() - started_at) * 1000),
            )
            emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="lookup_protocol_status", value="CONTROLLED_ERROR")
            return ProtocolStatusToolResult(
                status=OpsToolStatus.REPOSITORY_ERROR,
                reason="OPERATIONAL_FACTS_UNAVAILABLE",
            )
        emit_runtime_event(
            RuntimeEventKind.REPOSITORY,
            name="get_protocol_status_facts",
            value="COMPLETED",
            count=len(facts),
            elapsed_ms=int((perf_counter() - started_at) * 1000),
            protocol_number=protocol_number,
        )
        if not facts:
            emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="lookup_protocol_status", value="NOT_FOUND")
            return ProtocolStatusToolResult(
                status=OpsToolStatus.NOT_FOUND,
                reason="PROTOCOL_NOT_FOUND",
            )
        emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="lookup_protocol_status", value="SUCCESS", count=1)
        return ProtocolStatusToolResult(
            status=OpsToolStatus.SUCCESS,
            facts=facts[0],
            reason="OBSERVED_PROTOCOL_FACTS",
        )

    async def inspect_execution_failure(
        self,
        protocol_number: str,
        authorization: OpsAccessContext,
        *,
        run_id: int | None = None,
    ) -> ExecutionFailureToolResult:
        """Return authorized observed failure evidence, never root-cause inference."""

        if not self._valid_protocol(protocol_number) or not self._valid_run_id(run_id):
            return ExecutionFailureToolResult(
                status=OpsToolStatus.INVALID_INPUT,
                reason="INVALID_FAILURE_INSPECTION_INPUT",
            )
        if not authorization.can_read_operational_facts:
            emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="inspect_execution_failure", value="DENIED")
            return ExecutionFailureToolResult(
                status=OpsToolStatus.UNAUTHORIZED,
                reason="OPERATIONAL_ACCESS_DENIED",
            )
        emit_runtime_event(
            RuntimeEventKind.OPS_TOOL,
            name="inspect_execution_failure",
            value="STARTED",
            protocol_number=protocol_number,
        )
        started_at = perf_counter()
        try:
            evidence = tuple(
                await self._repository.get_execution_failure_facts(protocol_number, run_id=run_id)
            )
        except Exception:
            emit_runtime_event(
                RuntimeEventKind.REPOSITORY,
                name="get_execution_failure_facts",
                value="CONTROLLED_ERROR",
                elapsed_ms=int((perf_counter() - started_at) * 1000),
                protocol_number=protocol_number,
            )
            emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="inspect_execution_failure", value="CONTROLLED_ERROR")
            return ExecutionFailureToolResult(
                status=OpsToolStatus.REPOSITORY_ERROR,
                reason="EXECUTION_FAILURE_EVIDENCE_UNAVAILABLE",
            )
        emit_runtime_event(
            RuntimeEventKind.REPOSITORY,
            name="get_execution_failure_facts",
            value="COMPLETED",
            count=len(evidence),
            elapsed_ms=int((perf_counter() - started_at) * 1000),
            protocol_number=protocol_number,
        )
        if not evidence:
            emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="inspect_execution_failure", value="NOT_FOUND")
            return ExecutionFailureToolResult(
                status=OpsToolStatus.NOT_FOUND,
                reason="EXECUTION_FAILURE_EVIDENCE_NOT_FOUND",
            )
        emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="inspect_execution_failure", value="SUCCESS", count=len(evidence))
        return ExecutionFailureToolResult(
            status=OpsToolStatus.SUCCESS,
            evidence=evidence,
            reason="OBSERVED_EXECUTION_FAILURE_EVIDENCE",
        )

    async def list_recent_protocols(
        self,
        limit: int,
        authorization: OpsAccessContext,
    ) -> RecentProtocolsToolResult:
        """Return recent protocol records using the approved creation-time ordering."""

        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 5:
            return RecentProtocolsToolResult(status=OpsToolStatus.INVALID_INPUT, reason="INVALID_RECENT_LIMIT")
        if not authorization.can_read_operational_facts:
            emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="list_recent_protocols", value="DENIED")
            return RecentProtocolsToolResult(status=OpsToolStatus.UNAUTHORIZED, reason="OPERATIONAL_ACCESS_DENIED")
        emit_runtime_event(
            RuntimeEventKind.OPS_TOOL,
            name="list_recent_protocols",
            value="STARTED",
            limit=limit,
        )
        started_at = perf_counter()
        try:
            records = tuple(await self._repository.list_recent_service_requests(limit))
        except Exception:
            emit_runtime_event(
                RuntimeEventKind.REPOSITORY,
                name="list_recent_service_requests",
                value="CONTROLLED_ERROR",
                elapsed_ms=int((perf_counter() - started_at) * 1000),
            )
            emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="list_recent_protocols", value="CONTROLLED_ERROR")
            return RecentProtocolsToolResult(status=OpsToolStatus.REPOSITORY_ERROR, reason="RECENT_PROTOCOLS_UNAVAILABLE")
        emit_runtime_event(
            RuntimeEventKind.REPOSITORY,
            name="list_recent_service_requests",
            value="COMPLETED",
            count=len(records),
            elapsed_ms=int((perf_counter() - started_at) * 1000),
            limit=limit,
        )
        if not records:
            emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="list_recent_protocols", value="NOT_FOUND", count=0)
            return RecentProtocolsToolResult(status=OpsToolStatus.NOT_FOUND, reason="NO_PROTOCOLS_FOUND")
        emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="list_recent_protocols", value="SUCCESS", count=len(records))
        return RecentProtocolsToolResult(
            status=OpsToolStatus.SUCCESS,
            records=records,
            reason="OBSERVED_RECENT_PROTOCOLS",
        )

    async def list_recent_protocols_by_execution(
        self, limit: int, authorization: OpsAccessContext
    ) -> RecentExecutedProtocolsToolResult:
        """Return recent requests ordered by real automation-run start times."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 5:
            return RecentExecutedProtocolsToolResult(status=OpsToolStatus.INVALID_INPUT, reason="INVALID_RECENT_LIMIT")
        if not authorization.can_read_operational_facts:
            emit_runtime_event(RuntimeEventKind.OPS_TOOL, name="list_recent_protocols_by_execution", value="DENIED")
            return RecentExecutedProtocolsToolResult(status=OpsToolStatus.UNAUTHORIZED, reason="OPERATIONAL_ACCESS_DENIED")
        started = perf_counter()
        try:
            records = tuple(await self._repository.list_recent_protocols_by_execution(limit))
        except Exception:
            emit_runtime_event(RuntimeEventKind.REPOSITORY, name="list_recent_protocols_by_execution", value="CONTROLLED_ERROR", elapsed_ms=int((perf_counter() - started) * 1000))
            return RecentExecutedProtocolsToolResult(status=OpsToolStatus.REPOSITORY_ERROR, reason="EXECUTION_RECENCY_UNAVAILABLE")
        emit_runtime_event(RuntimeEventKind.REPOSITORY, name="list_recent_protocols_by_execution", value="COMPLETED", count=len(records), elapsed_ms=int((perf_counter() - started) * 1000), limit=limit)
        if not records:
            return RecentExecutedProtocolsToolResult(status=OpsToolStatus.NOT_FOUND, reason="NO_EXECUTED_PROTOCOLS_FOUND")
        return RecentExecutedProtocolsToolResult(status=OpsToolStatus.SUCCESS, records=records, reason="OBSERVED_EXECUTION_RECENCY")

    @staticmethod
    def _valid_protocol(protocol_number: object) -> bool:
        return isinstance(protocol_number, str) and bool(protocol_number.strip())

    @staticmethod
    def _valid_run_id(run_id: object) -> bool:
        return run_id is None or (isinstance(run_id, int) and not isinstance(run_id, bool) and run_id > 0)
