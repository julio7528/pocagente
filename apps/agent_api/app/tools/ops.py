"""Read-only, authorization-gated OPS tools over approved repository contracts."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from time import perf_counter
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.agent_api.app.database.models import ExecutionFailureEvidence, ProtocolStatusFacts, ServiceRequestRecord
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


class OperationalTools:
    """Expose approved OPS facts without SQL, connections, or diagnosis logic."""

    def __init__(self, repository: OperationalFactsRepository) -> None:
        self._repository = repository

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

    @staticmethod
    def _valid_protocol(protocol_number: object) -> bool:
        return isinstance(protocol_number, str) and bool(protocol_number.strip())

    @staticmethod
    def _valid_run_id(run_id: object) -> bool:
        return run_id is None or (isinstance(run_id, int) and not isinstance(run_id, bool) and run_id > 0)
