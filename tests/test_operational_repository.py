"""Unit tests for the connection-bound OperationalRepository."""

import asyncio
import inspect
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from apps.agent_api.app.database.models import (
    AutomationRunRecord,
    EstablishmentRecord,
    ExecutionFailureEvidence,
    ExecutionLogRecord,
    ProtocolStatusFacts,
    ServiceRequestRecord,
    OperationalAnalyticsQuery,
)
from apps.agent_api.app.database.repositories import operational as operational_module
from apps.agent_api.app.database.repositories.operational import OperationalRepository
from tests.repository_fakes import FakeConnection, normalized_sql


def test_operational_analytics_uses_parameterized_db_side_grouping():
    connection = FakeConnection([
        {"outcome": "SUCCESS", "count": 4},
        {"outcome": "FAILURE", "count": 2},
    ])
    repository = OperationalRepository(connection)
    query = OperationalAnalyticsQuery(
        grain="EXECUTION", metric="SUMMARY",
        start_at=datetime(2026, 9, 14, tzinfo=UTC),
        end_at=datetime(2026, 9, 21, tzinfo=UTC),
        time_basis="EXECUTION_STARTED", robot_filter="R2",
        group_by=("OUTCOME",), limit=5,
    )
    result = asyncio.run(repository.query_operational_analytics(query))
    statement = normalized_sql(connection.statements[0])
    assert "FROM ops.automation_runs" in statement
    assert "GROUP BY outcome" in statement
    assert "COUNT(*)::bigint" in statement
    assert "2026-09-14" not in statement
    assert connection.statements[0].parameters == (
        datetime(2026, 9, 14, tzinfo=UTC), datetime(2026, 9, 21, tzinfo=UTC), "R2",
    )
    assert result.exists and result.total_count == 6
    assert [group.count for group in result.groups] == [4, 2]


def test_event_exact_status_filter_does_not_expand_to_normalized_failure():
    connection = FakeConnection([{"count": 3}])
    repository = OperationalRepository(connection)
    query = OperationalAnalyticsQuery(
        grain="EVENT", metric="COUNT", time_basis="EVENT_OCCURRED",
        status_filter="ERROR",
    )
    asyncio.run(repository.query_operational_analytics(query))
    statement = normalized_sql(connection.statements[0])
    assert "status = %s" in statement
    assert "status IN ('ERROR', 'EXCEPTION')" in statement  # normalization remains output-only
    assert connection.statements[0].parameters == ("ERROR",)


def test_protocol_analytics_orders_by_actual_first_run_timestamp():
    connection = FakeConnection([
        {
            "protocol_number": "POC-OPS-0004", "run_id": None, "robot": None,
            "status": "COMPLETED", "outcome": "SUCCESS",
            "occurred_at": datetime(2025, 8, 1, tzinfo=UTC),
            "finished_at": None, "event": None, "matched_count": 7,
        }
    ])
    repository = OperationalRepository(connection)
    query = OperationalAnalyticsQuery(
        grain="PROTOCOL", metric="FIRST", time_basis="FIRST_EXECUTION",
        ordering="EARLIEST", limit=1,
    )
    result = asyncio.run(repository.query_operational_analytics(query))
    statement = normalized_sql(connection.statements[0])
    assert "MIN(ar.started_at) AS first_execution_at" in statement
    assert "service_requests" in statement
    assert "created_at DESC" not in statement
    assert result.rows[0].protocol_number == "POC-OPS-0004"
    assert result.total_count == 7


def _run_row(run_id: int) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "run_id": run_id,
        "robot": "R1",
        "started_at": now,
        "finished_at": now,
        "status": "SUCCESS",
        "result_message": "ok",
        "created_at": now,
    }


def _request_row(request_id: int, protocol_number: str = "PROTO-1") -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "request_id": request_id,
        "protocol_number": protocol_number,
        "email_id": 10,
        "r1_run_id": 7,
        "created_at": now,
        "updated_at": now,
        "status": "PROCESSING",
        "result": None,
        "failure_reason": None,
        "completed_at": None,
        "return_email_at": None,
    }


def _establishment_row(establishment_id: int, request_id: int = 20) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "establishment_id": establishment_id,
        "request_id": request_id,
        "attachment_id": 12,
        "establishment_number": "000123",
        "generated_file_name": f"PROTO-1_{establishment_id}.csv",
        "processing_status": "PENDING",
        "upload_status": "PENDING",
        "upload_at": None,
        "download_status": "NOT_AVAILABLE",
        "download_at": None,
        "return_email_at": None,
        "result_message": None,
        "updated_at": now,
    }


def _log_row(log_id: int, run_id: int = 7) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "log_id": log_id,
        "run_id": run_id,
        "logged_at": now,
        "robot": "R1",
        "event": "UPLOAD_FINISHED",
        "status": "SUCCESS",
        "message": "sanitized",
        "email_id": None,
        "attachment_id": None,
        "request_id": 20,
        "establishment_id": None,
        "created_at": now,
    }


def _protocol_status_row(protocol_number: str = "PROTO-1") -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "request_id": 20,
        "protocol_number": protocol_number,
        "email_id": 10,
        "r1_run_id": 7,
        "created_at": now,
        "updated_at": now,
        "status": "PROCESSING",
        "result": None,
        "failure_reason": None,
        "completed_at": None,
        "return_email_at": None,
        "establishments": [_establishment_row(30, 20)],
        "execution_timeline": [_log_row(40, 7)],
    }


def _failure_evidence_row(log_id: int = 42, protocol_number: str = "PROTO-1") -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "request_id": 20,
        "protocol_number": protocol_number,
        "request_status": "FAILED",
        "failure_reason": "Upload error",
        "run_id": 7,
        "robot": "R1",
        "started_at": now,
        "finished_at": now,
        "run_status": "ERROR",
        "run_result_message": "Failed",
        "log_id": log_id,
        "logged_at": now,
        "event": "UPLOAD_ERROR",
        "event_status": "ERROR",
        "event_message": "Error uploading",
        "email_id": None,
        "attachment_id": None,
        "establishment_id": None,
        "last_successful_evidence": _log_row(41, 7),
    }


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_operational_repository_retains_connection_without_side_effects() -> None:
    connection = MagicMock()

    repository = OperationalRepository(connection)

    assert repository._connection is connection
    connection.cursor.assert_not_called()
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_not_called()


def test_operational_repository_foundation_is_ops_only() -> None:
    source = inspect.getsource(operational_module)
    for forbidden in (
        "AsyncConnectionPool",
        "PostgresDatabase(",
        "AsyncConnection(",
        "rag.",
        "audit.",
        ".commit(",
        ".rollback(",
    ):
        assert forbidden not in source


@pytest.mark.anyio
async def test_automation_run_create_get_and_update_are_parameterized() -> None:
    finished_at = datetime.now(UTC)
    row = _run_row(7)
    connection = FakeConnection({"run_id": 7}, None, row)
    repository = OperationalRepository(connection)

    assert await repository.create_automation_run({"robot": "R1"}) == 7
    await repository.update_automation_run(
        7,
        {"finished_at": finished_at, "status": "SUCCESS", "result_message": "ok"},
    )
    result = await repository.get_automation_run(7)
    assert isinstance(result, AutomationRunRecord)
    assert result.run_id == 7

    create, update, get = connection.statements
    create_sql = normalized_sql(create).replace('"', "")
    update_sql = normalized_sql(update).replace('"', "")
    assert "INSERT INTO ops.automation_runs" in create_sql
    assert "RETURNING run_id" in create_sql
    assert create.parameters == ("R1",)
    assert "UPDATE ops.automation_runs SET" in update_sql
    assert update.parameters == (finished_at, "SUCCESS", "ok", 7)
    assert "FROM ops.automation_runs WHERE run_id = %s" in normalized_sql(get)
    assert get.parameters == (7,)


@pytest.mark.anyio
async def test_protocol_correlation_reads_email_attachments_and_runs_with_bound_ids() -> None:
    now = datetime.now(UTC)
    email = {
        "email_id": 10, "run_id": 7, "received_at": now, "processed_at": None,
        "sender": "sender@example.test", "recipient": "ops@example.test", "subject": "Request",
        "attachment_count": 1, "sender_status": "VALID", "processing_status": "PROCESSED",
        "rejection_reason": None, "created_at": now,
    }
    attachment = {
        "attachment_id": 12, "email_id": 10, "file_name": "request.csv", "file_type": "text/csv",
        "received_at": now, "validation_status": "VALID", "validation_message": None,
        "establishment_count": 1, "processing_status": "PROCESSED", "created_at": now,
    }
    run = _run_row(7)
    connection = FakeConnection(email, [attachment], [run])
    repository = OperationalRepository(connection)

    assert (await repository.get_incoming_email(10)).sender == "sender@example.test"
    assert (await repository.list_email_attachments(10))[0].file_name == "request.csv"
    assert (await repository.list_automation_runs_for_request(20))[0].run_id == 7
    assert [statement.parameters for statement in connection.statements] == [(10,), (10,), (20,) * 5]
    sql_text = normalized_sql(connection.statements[2]).lower()
    assert "r1_run_id as run_id" in sql_text and "ops.execution_log" in sql_text
    assert "ops.establishments" in sql_text and "ops.email_attachments" in sql_text
    assert all("%s" in normalized_sql(statement) for statement in connection.statements)


@pytest.mark.anyio
async def test_recent_protocols_by_execution_uses_domain_run_timestamps() -> None:
    row = _request_row(20)
    row["last_execution_at"] = datetime.now(UTC)
    connection = FakeConnection([row])
    repository = OperationalRepository(connection)
    result = await repository.list_recent_protocols_by_execution(1)

    assert result[0].service_request.request_id == 20
    assert result[0].last_execution_at == row["last_execution_at"]
    statement = connection.statements[0]
    sql_text = normalized_sql(statement).lower()
    assert "max(ar.started_at)" in sql_text
    assert "ar.created_at" not in sql_text.split("order by", 1)[1]
    assert statement.parameters == (1,)


@pytest.mark.anyio
async def test_automation_run_rejects_identity_or_unknown_mutation() -> None:
    connection = FakeConnection()
    repository = OperationalRepository(connection)

    with pytest.raises(ValueError, match="Unsupported fields"):
        await repository.create_automation_run({"robot": "R1", "run_id": 3})
    with pytest.raises(ValueError, match="Unsupported fields"):
        await repository.update_automation_run(3, {"robot": "R2"})

    assert connection.statements == []


@pytest.mark.anyio
async def test_incoming_email_create_and_update_use_physical_columns_only() -> None:
    received_at = datetime.now(UTC)
    processed_at = datetime.now(UTC)
    connection = FakeConnection({"email_id": 10}, None)
    repository = OperationalRepository(connection)
    payload = {
        "run_id": 7,
        "received_at": received_at,
        "sender": "sender@example.com",
        "recipient": "robot@example.com",
        "subject": "Request",
    }

    assert await repository.create_incoming_email(payload) == 10
    await repository.update_incoming_email(
        10,
        {
            "processed_at": processed_at,
            "sender_status": "VALID",
            "processing_status": "PROCESSED",
        },
    )

    create, update = connection.statements
    assert "ops.incoming_emails" in normalized_sql(create).replace('"', "")
    assert create.parameters == tuple(payload.values())
    assert update.parameters == (processed_at, "VALID", "PROCESSED", 10)
    combined = (create.sql + update.sql).lower()
    assert "body" not in combined and "cc" not in combined


@pytest.mark.anyio
async def test_incoming_email_rejects_body_cc_and_identity_mutation() -> None:
    connection = FakeConnection()
    repository = OperationalRepository(connection)

    for prohibited in ("body", "cc", "email_id", "created_at"):
        with pytest.raises(ValueError, match="Unsupported fields"):
            await repository.create_incoming_email(
                {
                    "run_id": 1,
                    "received_at": datetime.now(UTC),
                    "sender": "a@b",
                    "recipient": "c@d",
                    prohibited: "not allowed",
                }
            )

    assert connection.statements == []


@pytest.mark.anyio
async def test_attachment_create_and_update_are_parameterized() -> None:
    received_at = datetime.now(UTC)
    connection = FakeConnection({"attachment_id": 12}, None)
    repository = OperationalRepository(connection)
    payload = {
        "email_id": 10,
        "file_name": "input.xlsx",
        "received_at": received_at,
    }

    assert await repository.create_email_attachment(payload) == 12
    await repository.update_email_attachment(
        12,
        {
            "validation_status": "VALID",
            "establishment_count": 3,
            "processing_status": "PROCESSED",
        },
    )

    create, update = connection.statements
    assert "ops.email_attachments" in normalized_sql(create).replace('"', "")
    assert create.parameters == (10, "input.xlsx", received_at)
    assert update.parameters == ("VALID", 3, "PROCESSED", 12)


@pytest.mark.anyio
async def test_attachment_rejects_paths_storage_and_identity_changes() -> None:
    connection = FakeConnection()
    repository = OperationalRepository(connection)

    for prohibited in ("path", "storage_path", "attachment_id", "created_at"):
        with pytest.raises(ValueError, match="Unsupported fields"):
            await repository.create_email_attachment(
                {
                    "email_id": 10,
                    "file_name": "input.xlsx",
                    "received_at": datetime.now(UTC),
                    prohibited: "not allowed",
                }
            )

    assert connection.statements == []


@pytest.mark.anyio
async def test_service_request_create_update_and_protocol_lookup() -> None:
    updated_at = datetime.now(UTC)
    row = _request_row(20, "PROTO-1")
    connection = FakeConnection({"request_id": 20}, None, row)
    repository = OperationalRepository(connection)
    payload = {
        "protocol_number": "PROTO-1",
        "email_id": 10,
        "r1_run_id": 7,
        "updated_at": updated_at,
    }

    assert await repository.create_service_request(payload) == 20
    await repository.update_service_request(
        20,
        {"updated_at": updated_at, "status": "PROCESSING"},
    )
    result = await repository.get_service_request_by_protocol("PROTO-1")
    assert isinstance(result, ServiceRequestRecord)
    assert result.request_id == 20

    create, update, lookup = connection.statements
    assert "ops.service_requests" in normalized_sql(create).replace('"', "")
    assert create.parameters == tuple(payload.values())
    assert update.parameters == (updated_at, "PROCESSING", 20)
    assert "WHERE protocol_number = %s" in normalized_sql(lookup)
    assert lookup.parameters == ("PROTO-1",)
    assert "r2_run_id" not in (create.sql + update.sql + lookup.sql)


@pytest.mark.anyio
async def test_recent_service_requests_use_creation_timestamp_and_bounded_limit() -> None:
    row = _request_row(20, "POC-OPS-0004")
    connection = FakeConnection([row])
    repository = OperationalRepository(connection)

    records = await repository.list_recent_service_requests(3)

    assert len(records) == 1
    assert records[0].protocol_number == "POC-OPS-0004"
    statement = normalized_sql(connection.statements[0])
    assert "FROM ops.service_requests" in statement
    assert "ORDER BY created_at DESC, request_id DESC" in statement
    assert "LIMIT %s" in statement
    assert connection.statements[0].parameters == (3,)

    with pytest.raises(ValueError, match="between 1 and 5"):
        await repository.list_recent_service_requests(6)
    assert len(connection.statements) == 1


@pytest.mark.anyio
async def test_service_request_rejects_protocol_and_r1_identity_updates() -> None:
    connection = FakeConnection()
    repository = OperationalRepository(connection)

    for field in ("protocol_number", "email_id", "r1_run_id", "r2_run_id"):
        with pytest.raises(ValueError, match="Unsupported fields"):
            await repository.update_service_request(20, {field: "changed"})

    assert connection.statements == []


def _establishment(updated_at: datetime) -> dict[str, object]:
    return {
        "request_id": 20,
        "attachment_id": 12,
        "establishment_number": "000123",
        "generated_file_name": "PROTO-1_000123.csv",
        "processing_status": "PENDING",
        "updated_at": updated_at,
    }


@pytest.mark.anyio
async def test_establishment_upsert_inserts_when_both_unique_identities_are_free() -> None:
    payload = _establishment(datetime.now(UTC))
    connection = FakeConnection([], {"establishment_id": 30})
    repository = OperationalRepository(connection)

    assert await repository.upsert_establishment(payload) == 30

    lookup, insert = connection.statements
    lookup_sql = normalized_sql(lookup)
    assert "request_id = %s AND attachment_id = %s AND establishment_number = %s" in lookup_sql
    assert "request_id = %s AND generated_file_name = %s" in lookup_sql
    assert "INSERT INTO ops.establishments" in normalized_sql(insert).replace('"', "")
    assert insert.parameters == tuple(payload.values())


@pytest.mark.anyio
async def test_establishment_upsert_updates_only_when_both_identities_match() -> None:
    now = datetime.now(UTC)
    payload = _establishment(now)
    existing = {"establishment_id": 30, **{key: payload[key] for key in (
        "request_id", "attachment_id", "establishment_number", "generated_file_name"
    )}}
    connection = FakeConnection([existing], None)
    repository = OperationalRepository(connection)

    assert await repository.upsert_establishment(payload) == 30

    _, update = connection.statements
    assert "UPDATE ops.establishments SET" in normalized_sql(update).replace('"', "")
    assert update.parameters == ("PENDING", now, 30)


@pytest.mark.anyio
async def test_establishment_upsert_rejects_cross_unique_identity_collision() -> None:
    payload = _establishment(datetime.now(UTC))
    conflicting = {
        "establishment_id": 31,
        "request_id": 20,
        "attachment_id": 99,
        "establishment_number": "DIFFERENT",
        "generated_file_name": payload["generated_file_name"],
    }
    connection = FakeConnection([conflicting])
    repository = OperationalRepository(connection)

    with pytest.raises(ValueError, match="identity conflicts"):
        await repository.upsert_establishment(payload)

    assert len(connection.statements) == 1


@pytest.mark.anyio
async def test_establishment_update_rejects_identity_mutation_and_list_is_deterministic() -> None:
    rows = [_establishment_row(30), _establishment_row(31)]
    connection = FakeConnection(rows)
    repository = OperationalRepository(connection)

    with pytest.raises(ValueError, match="Unsupported fields"):
        await repository.update_establishment(30, {"generated_file_name": "new.csv"})
    result = await repository.list_establishments_for_request(20)
    assert len(result) == 2
    assert all(isinstance(e, EstablishmentRecord) for e in result)
    assert [e.establishment_id for e in result] == [30, 31]

    statement = connection.statements[0]
    assert "WHERE request_id = %s ORDER BY establishment_id ASC" in normalized_sql(statement)
    assert statement.parameters == (20,)


@pytest.mark.anyio
async def test_execution_log_is_append_only_and_timelines_follow_indexes() -> None:
    logged_at = datetime.now(UTC)
    event = {
        "run_id": 7,
        "logged_at": logged_at,
        "robot": "R1",
        "event": "UPLOAD_FINISHED",
        "status": "SUCCESS",
        "message": "sanitized",
        "request_id": 20,
    }
    rows = [_log_row(40), _log_row(39)]
    connection = FakeConnection({"log_id": 40}, rows, rows)
    repository = OperationalRepository(connection)

    assert await repository.append_execution_log(event) == 40
    run_tl = await repository.list_execution_timeline_for_run(7, 20)
    assert len(run_tl) == 2
    assert all(isinstance(l, ExecutionLogRecord) for l in run_tl)
    req_tl = await repository.list_execution_timeline_for_request(20, 20)
    assert len(req_tl) == 2
    assert all(isinstance(l, ExecutionLogRecord) for l in req_tl)

    append, run_timeline, request_timeline = connection.statements
    assert "INSERT INTO ops.execution_log" in normalized_sql(append).replace('"', "")
    assert append.parameters == tuple(event.values())
    assert "WHERE run_id = %s ORDER BY logged_at DESC, log_id DESC LIMIT %s" in normalized_sql(run_timeline)
    assert run_timeline.parameters == (7, 20)
    assert "el.request_id = %s" in normalized_sql(request_timeline)
    request_sql = normalized_sql(request_timeline).lower()
    assert "establishment_id in (" in request_sql
    assert "order by el.logged_at desc, el.log_id desc limit %s" in request_sql
    assert request_timeline.parameters == (20, 20, 20, 20, 20)
    source = inspect.getsource(OperationalRepository)
    assert "update_execution_log" not in source and "delete_execution_log" not in source


@pytest.mark.anyio
async def test_execution_timeline_rejects_unbounded_limits_before_sql() -> None:
    connection = FakeConnection()
    repository = OperationalRepository(connection)

    with pytest.raises(ValueError, match="between 1 and 100"):
        await repository.list_execution_timeline_for_run(7, 101)
    with pytest.raises(ValueError, match="between 1 and 100"):
        await repository.list_execution_timeline_for_request(20, 0)

    assert connection.statements == []


@pytest.mark.anyio
async def test_protocol_status_returns_only_deterministic_ops_facts() -> None:
    rows = [_protocol_status_row("PROTO-1")]
    connection = FakeConnection(rows)
    repository = OperationalRepository(connection)

    facts = await repository.get_protocol_status_facts("PROTO-1")
    assert len(facts) == 1
    assert isinstance(facts[0], ProtocolStatusFacts)
    assert facts[0].protocol_number == "PROTO-1"
    assert len(facts[0].establishments) == 1
    assert isinstance(facts[0].establishments[0], EstablishmentRecord)
    assert len(facts[0].execution_timeline) == 1
    assert isinstance(facts[0].execution_timeline[0], ExecutionLogRecord)

    statement = connection.statements[0]
    query = normalized_sql(statement)
    assert "FROM ops.service_requests AS sr" in query
    assert "FROM ops.establishments AS e" in query
    assert "FROM ops.execution_log AS l" in query
    assert "WHERE sr.protocol_number = %s" in query
    assert "ORDER BY l.logged_at ASC, l.log_id ASC" in query
    assert statement.parameters == ("PROTO-1",)
    lowered = query.lower()
    for forbidden in ("rag.", "audit.", "sla", "probable", "diagnosis", "escalat"):
        assert forbidden not in lowered


@pytest.mark.anyio
async def test_failure_facts_support_protocol_only_and_optional_run_filter() -> None:
    rows = [_failure_evidence_row(42, "PROTO-1")]
    connection = FakeConnection(rows, rows)
    repository = OperationalRepository(connection)

    result1 = await repository.get_execution_failure_facts("PROTO-1")
    assert len(result1) == 1
    assert isinstance(result1[0], ExecutionFailureEvidence)
    assert result1[0].log_id == 42
    result2 = await repository.get_execution_failure_facts("PROTO-1", run_id=7)
    assert len(result2) == 1
    assert isinstance(result2[0], ExecutionFailureEvidence)

    protocol_only, filtered = connection.statements
    protocol_sql = normalized_sql(protocol_only)
    filtered_sql = normalized_sql(filtered)
    assert "JOIN ops.execution_log AS l" in protocol_sql
    assert "JOIN ops.automation_runs AS ar" in protocol_sql
    assert "l.status IN ('ERROR', 'EXCEPTION')" in protocol_sql
    assert "previous_success.status = 'SUCCESS'" in protocol_sql
    assert "ORDER BY l.logged_at ASC, l.log_id ASC" in protocol_sql
    assert "l.run_id = %s" not in protocol_sql
    assert protocol_only.parameters == ("PROTO-1",)
    assert "AND l.run_id = %s" in filtered_sql
    assert filtered.parameters == ("PROTO-1", 7)


@pytest.mark.anyio
async def test_failure_facts_return_empty_for_missing_protocol_or_evidence() -> None:
    connection = FakeConnection([], [])
    repository = OperationalRepository(connection)

    assert await repository.get_execution_failure_facts("MISSING") == ()
    assert await repository.get_execution_failure_facts("NO-FAILURE", 9) == ()

    combined = " ".join(statement.sql for statement in connection.statements).lower()
    for forbidden in ("rag.", "audit.", "probable", "root cause", "escalat", "llm"):
        assert forbidden not in combined
