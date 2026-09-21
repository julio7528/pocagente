"""Read-only, authorization-gated OPS tools over approved repository contracts."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.agent_api.app.database.models import ExecutionFailureEvidence, ProtocolStatusFacts


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
            return ProtocolStatusToolResult(
                status=OpsToolStatus.UNAUTHORIZED,
                reason="OPERATIONAL_ACCESS_DENIED",
            )
        try:
            facts = tuple(await self._repository.get_protocol_status_facts(protocol_number))
        except Exception:
            return ProtocolStatusToolResult(
                status=OpsToolStatus.REPOSITORY_ERROR,
                reason="OPERATIONAL_FACTS_UNAVAILABLE",
            )
        if not facts:
            return ProtocolStatusToolResult(
                status=OpsToolStatus.NOT_FOUND,
                reason="PROTOCOL_NOT_FOUND",
            )
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
            return ExecutionFailureToolResult(
                status=OpsToolStatus.UNAUTHORIZED,
                reason="OPERATIONAL_ACCESS_DENIED",
            )
        try:
            evidence = tuple(
                await self._repository.get_execution_failure_facts(protocol_number, run_id=run_id)
            )
        except Exception:
            return ExecutionFailureToolResult(
                status=OpsToolStatus.REPOSITORY_ERROR,
                reason="EXECUTION_FAILURE_EVIDENCE_UNAVAILABLE",
            )
        if not evidence:
            return ExecutionFailureToolResult(
                status=OpsToolStatus.NOT_FOUND,
                reason="EXECUTION_FAILURE_EVIDENCE_NOT_FOUND",
            )
        return ExecutionFailureToolResult(
            status=OpsToolStatus.SUCCESS,
            evidence=evidence,
            reason="OBSERVED_EXECUTION_FAILURE_EVIDENCE",
        )

    @staticmethod
    def _valid_protocol(protocol_number: object) -> bool:
        return isinstance(protocol_number, str) and bool(protocol_number.strip())

    @staticmethod
    def _valid_run_id(run_id: object) -> bool:
        return run_id is None or (isinstance(run_id, int) and not isinstance(run_id, bool) and run_id > 0)
