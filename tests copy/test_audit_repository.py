"""Unit tests for the connection-bound AuditRepository."""

import inspect
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from apps.agent_api.app.database.models import SecurityEventRecord
from apps.agent_api.app.database.repositories import audit as audit_module
from apps.agent_api.app.database.repositories.audit import AuditRepository
from tests.repository_fakes import FakeConnection, normalized_sql


def _event_row(event_id: int, review_status: str = "UNREVIEWED", reference: str = "request-1") -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "event_id": event_id,
        "occurred_at": now,
        "event_type": "PROMPT_INJECTION",
        "source_component": "agent_api",
        "user_identifier": None,
        "request_reference": reference,
        "resource_category": None,
        "sanitized_content": "[REDACTED]",
        "action_taken": "BLOCK",
        "result": "SUCCESS",
        "review_status": review_status,
        "reviewed_at": None,
        "review_note": None,
        "created_at": now,
    }


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_audit_repository_retains_connection_without_side_effects() -> None:
    connection = MagicMock()
    repository = AuditRepository(connection)

    assert repository._connection is connection
    connection.cursor.assert_not_called()
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_not_called()


def test_audit_repository_foundation_is_audit_only() -> None:
    source = inspect.getsource(audit_module)
    for forbidden in (
        "AsyncConnectionPool",
        "PostgresDatabase(",
        "AsyncConnection(",
        "rag.",
        "ops.",
        ".commit(",
        ".rollback(",
    ):
        assert forbidden not in source


@pytest.mark.anyio
async def test_sanitized_event_insert_uses_only_approved_columns() -> None:
    occurred_at = datetime.now(UTC)
    payload = {
        "occurred_at": occurred_at,
        "event_type": "PROMPT_INJECTION",
        "source_component": "agent_api",
        "request_reference": "request-1",
        "sanitized_content": "[REDACTED]",
        "action_taken": "BLOCK",
        "result": "SUCCESS",
    }
    connection = FakeConnection({"event_id": 90})
    repository = AuditRepository(connection)

    assert await repository.write_sanitized_security_event(payload) == 90

    statement = connection.statements[0]
    query = normalized_sql(statement).replace('"', "")
    assert "INSERT INTO audit.security_events" in query
    assert "RETURNING event_id" in query
    assert statement.parameters == tuple(payload.values())
    for forbidden in ("raw_request", "request_body", "payload", "rag.", "ops."):
        assert forbidden not in query.lower()


@pytest.mark.anyio
async def test_sanitized_event_rejects_unknown_and_secret_value_keys_before_sql() -> None:
    base = {
        "occurred_at": datetime.now(UTC),
        "event_type": "SECRET_REQUEST",
        "source_component": "agent_api",
        "action_taken": "REDACT",
        "result": "SUCCESS",
    }
    connection = FakeConnection()
    repository = AuditRepository(connection)

    with pytest.raises(ValueError, match="Unsupported fields"):
        await repository.write_sanitized_security_event({**base, "debug_dump": "x"})
    for prohibited in ("password", "api_token", "private-key", "connection_string", "raw_request_body"):
        with pytest.raises(ValueError, match="Prohibited"):
            await repository.write_sanitized_security_event({**base, prohibited: "secret"})

    assert connection.statements == []


@pytest.mark.anyio
async def test_security_event_lookup_uses_pk_and_handles_miss() -> None:
    row = _event_row(90)
    connection = FakeConnection(row, None)
    repository = AuditRepository(connection)

    result = await repository.get_security_event(90)
    assert isinstance(result, SecurityEventRecord)
    assert result.event_id == 90
    assert await repository.get_security_event(91) is None

    assert all(
        "FROM audit.security_events WHERE event_id = %s" in normalized_sql(statement)
        for statement in connection.statements
    )
    assert [statement.parameters for statement in connection.statements] == [(90,), (91,)]


@pytest.mark.anyio
async def test_request_reference_correlation_is_bounded_and_descending() -> None:
    rows = [_event_row(90, reference="request-1"), _event_row(89, reference="request-1")]
    connection = FakeConnection(rows)
    repository = AuditRepository(connection)

    result = await repository.list_security_events_by_request_reference("request-1", 25)
    assert len(result) == 2
    assert all(isinstance(e, SecurityEventRecord) for e in result)
    assert [e.event_id for e in result] == [90, 89]

    statement = connection.statements[0]
    query = normalized_sql(statement)
    assert "WHERE request_reference = %s" in query
    assert "ORDER BY occurred_at DESC, event_id DESC" in query
    assert "LIMIT %s" in query
    assert statement.parameters == ("request-1", 25)


@pytest.mark.anyio
async def test_request_reference_correlation_rejects_unbounded_limit() -> None:
    connection = FakeConnection()
    repository = AuditRepository(connection)

    with pytest.raises(ValueError, match="between 1 and 100"):
        await repository.list_security_events_by_request_reference("request-1", 101)

    assert connection.statements == []


@pytest.mark.anyio
async def test_unreviewed_events_query_matches_partial_index_predicate() -> None:
    rows = [_event_row(90, review_status="UNREVIEWED")]
    connection = FakeConnection(rows)
    repository = AuditRepository(connection)

    result = await repository.list_unreviewed_security_events(10)
    assert len(result) == 1
    assert isinstance(result[0], SecurityEventRecord)
    assert result[0].event_id == 90

    statement = connection.statements[0]
    query = normalized_sql(statement)
    assert "WHERE review_status = 'UNREVIEWED'" in query
    assert "ORDER BY occurred_at DESC, event_id DESC" in query
    assert statement.parameters == (10,)


@pytest.mark.anyio
async def test_review_update_uses_only_approved_fields_and_pk() -> None:
    reviewed_at = datetime.now(UTC)
    connection = FakeConnection()
    repository = AuditRepository(connection)

    await repository.update_security_event_review(
        90,
        review_status="REVIEWED",
        reviewed_at=reviewed_at,
        review_note="Authorized review complete",
    )

    statement = connection.statements[0]
    query = normalized_sql(statement)
    assert "UPDATE audit.security_events" in query
    assert "SET review_status = %s, reviewed_at = %s, review_note = %s" in query
    assert "WHERE event_id = %s" in query
    assert statement.parameters == (
        "REVIEWED",
        reviewed_at,
        "Authorized review complete",
        90,
    )


@pytest.mark.anyio
async def test_review_update_rejects_inconsistent_timestamp_before_sql() -> None:
    connection = FakeConnection()
    repository = AuditRepository(connection)

    with pytest.raises(ValueError, match="require reviewed_at"):
        await repository.update_security_event_review(
            90,
            review_status="REVIEWED",
            reviewed_at=None,
            review_note=None,
        )
    with pytest.raises(ValueError, match="cannot have reviewed_at"):
        await repository.update_security_event_review(
            90,
            review_status="UNREVIEWED",
            reviewed_at=datetime.now(UTC),
            review_note=None,
        )

    assert connection.statements == []
