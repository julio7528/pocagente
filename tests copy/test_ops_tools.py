"""Focused Phase 9.4 unit tests for controlled read-only OPS tools."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from apps.agent_api.app.database.models import ExecutionFailureEvidence, ProtocolStatusFacts
from apps.agent_api.app.tools.ops import (
    ExecutionFailureToolResult,
    OpsAccessContext,
    OpsToolStatus,
    OperationalTools,
    ProtocolStatusToolResult,
)


class FakeOperationalRepository:
    def __init__(
        self,
        *,
        protocol_facts: tuple[ProtocolStatusFacts, ...] = (),
        failure_evidence: tuple[ExecutionFailureEvidence, ...] = (),
        failure: Exception | None = None,
    ) -> None:
        self.protocol_facts = protocol_facts
        self.failure_evidence = failure_evidence
        self.failure = failure
        self.protocol_calls: list[str] = []
        self.failure_calls: list[tuple[str, int | None]] = []

    async def get_protocol_status_facts(self, protocol_number: str) -> tuple[ProtocolStatusFacts, ...]:
        self.protocol_calls.append(protocol_number)
        if self.failure is not None:
            raise self.failure
        return self.protocol_facts

    async def get_execution_failure_facts(
        self, protocol_number: str, run_id: int | None = None
    ) -> tuple[ExecutionFailureEvidence, ...]:
        self.failure_calls.append((protocol_number, run_id))
        if self.failure is not None:
            raise self.failure
        return self.failure_evidence


AUTHORIZED = OpsAccessContext(principal_id="test-support-operator", can_read_operational_facts=True)
DENIED = OpsAccessContext(principal_id="test-untrusted-user", can_read_operational_facts=False)
NOW = datetime(2026, 9, 1, tzinfo=UTC)


def protocol_facts() -> ProtocolStatusFacts:
    return ProtocolStatusFacts(
        request_id=10,
        protocol_number="POC-OPS-0002",
        email_id=20,
        r1_run_id=30,
        created_at=NOW,
        updated_at=NOW,
        status="FAILED",
    )


def failure_evidence() -> ExecutionFailureEvidence:
    return ExecutionFailureEvidence(
        request_id=10,
        protocol_number="POC-OPS-0002",
        request_status="FAILED",
        failure_reason="Falha observada no download.",
        run_id=31,
        robot="R2",
        started_at=NOW,
        finished_at=NOW,
        run_status="ERROR",
        log_id=40,
        logged_at=NOW,
        event="DOWNLOAD_ARQUIVO_FALHOU",
        event_status="ERROR",
        event_message="Falha observada no download.",
    )


def test_lookup_protocol_status_returns_typed_observed_facts() -> None:
    repository = FakeOperationalRepository(protocol_facts=(protocol_facts(),))
    result = asyncio.run(OperationalTools(repository).lookup_protocol_status("POC-OPS-0002", AUTHORIZED))

    assert result.status is OpsToolStatus.SUCCESS
    assert result.facts == protocol_facts()
    assert result.reason == "OBSERVED_PROTOCOL_FACTS"
    assert repository.protocol_calls == ["POC-OPS-0002"]
    assert "diagnosis" not in ProtocolStatusToolResult.model_fields
    assert "root_cause" not in ProtocolStatusToolResult.model_fields


def test_lookup_invalid_or_unauthorized_never_calls_repository() -> None:
    repository = FakeOperationalRepository()
    tool = OperationalTools(repository)

    invalid = asyncio.run(tool.lookup_protocol_status("  ", AUTHORIZED))
    denied = asyncio.run(tool.lookup_protocol_status("POC-OPS-0002", DENIED))

    assert invalid.status is OpsToolStatus.INVALID_INPUT
    assert denied.status is OpsToolStatus.UNAUTHORIZED
    assert repository.protocol_calls == []


def test_lookup_not_found_and_repository_error_are_distinct_and_sanitized() -> None:
    not_found = asyncio.run(
        OperationalTools(FakeOperationalRepository()).lookup_protocol_status("MISSING", AUTHORIZED)
    )
    error = asyncio.run(
        OperationalTools(
            FakeOperationalRepository(failure=RuntimeError("SELECT secret FROM ops.private_table"))
        ).lookup_protocol_status("POC-OPS-0002", AUTHORIZED)
    )

    assert not_found.status is OpsToolStatus.NOT_FOUND
    assert error.status is OpsToolStatus.REPOSITORY_ERROR
    assert "SELECT" not in error.reason
    assert "private_table" not in error.reason
    assert "secret" not in error.model_dump_json().lower()


def test_failure_inspection_returns_typed_evidence_with_optional_run_filter() -> None:
    repository = FakeOperationalRepository(failure_evidence=(failure_evidence(),))
    result = asyncio.run(
        OperationalTools(repository).inspect_execution_failure(
            "POC-OPS-0002", AUTHORIZED, run_id=31
        )
    )

    assert result.status is OpsToolStatus.SUCCESS
    assert result.evidence == (failure_evidence(),)
    assert repository.failure_calls == [("POC-OPS-0002", 31)]
    assert "diagnosis" not in ExecutionFailureToolResult.model_fields
    assert "root_cause" not in ExecutionFailureToolResult.model_fields


def test_failure_invalid_or_unauthorized_never_calls_repository() -> None:
    repository = FakeOperationalRepository()
    tool = OperationalTools(repository)

    invalid_protocol = asyncio.run(tool.inspect_execution_failure("", AUTHORIZED))
    invalid_run = asyncio.run(tool.inspect_execution_failure("POC-OPS-0002", AUTHORIZED, run_id=0))
    denied = asyncio.run(tool.inspect_execution_failure("POC-OPS-0002", DENIED))

    assert invalid_protocol.status is OpsToolStatus.INVALID_INPUT
    assert invalid_run.status is OpsToolStatus.INVALID_INPUT
    assert denied.status is OpsToolStatus.UNAUTHORIZED
    assert repository.failure_calls == []


def test_failure_not_found_and_repository_error_are_distinct_and_sanitized() -> None:
    not_found = asyncio.run(
        OperationalTools(FakeOperationalRepository()).inspect_execution_failure("MISSING", AUTHORIZED)
    )
    error = asyncio.run(
        OperationalTools(
            FakeOperationalRepository(failure=RuntimeError("postgres://unsafe-token@host/ops"))
        ).inspect_execution_failure("POC-OPS-0002", AUTHORIZED)
    )

    assert not_found.status is OpsToolStatus.NOT_FOUND
    assert error.status is OpsToolStatus.REPOSITORY_ERROR
    assert "postgres" not in error.model_dump_json().lower()
    assert "unsafe-token" not in error.model_dump_json().lower()


def test_tool_contracts_accept_only_narrow_business_arguments() -> None:
    assert OperationalTools.lookup_protocol_status.__annotations__ == {
        "protocol_number": "str",
        "authorization": "OpsAccessContext",
        "return": "ProtocolStatusToolResult",
    }
    assert OperationalTools.inspect_execution_failure.__annotations__["run_id"] == "int | None"
    assert "sql" not in OperationalTools.lookup_protocol_status.__annotations__
    assert "table" not in OperationalTools.inspect_execution_failure.__annotations__
