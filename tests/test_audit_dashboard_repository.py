"""Bounded dashboard reads over the existing AUDIT repository."""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from apps.agent_api.app.database.repositories.audit import AuditRepository
from apps.agent_api.app.security.dashboard_models import (
    SecurityDashboardFilters,
    SecurityDashboardPage,
)
from tests.repository_fakes import FakeConnection, normalized_sql


def _filters(**values: object) -> SecurityDashboardFilters:
    return SecurityDashboardFilters(date_from=date(2026, 1, 1), date_to=date(2026, 1, 3), **values)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_dashboard_filter_defaults_are_bounded_utc_days() -> None:
    filters = SecurityDashboardFilters()
    assert filters.date_from is not None and filters.date_to is not None
    assert (filters.date_to - filters.date_from).days == 29
    assert filters.start_at.tzinfo is UTC
    assert filters.end_before.tzinfo is UTC
    assert filters.end_before > filters.start_at


@pytest.mark.parametrize(
    "values",
    [
        {"date_from": date(2026, 1, 4), "date_to": date(2026, 1, 3)},
        {"date_from": date(2026, 1, 1), "date_to": date(2026, 4, 1)},
        {"source_component": "   "},
        {"user_identifier": "   "},
        {"source_component": "x" * 129},
        {"user_identifier": "x" * 129},
        {"event_type": "' OR 1=1 --"},
    ],
)
def test_dashboard_filters_reject_invalid_or_unbounded_values(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SecurityDashboardFilters(**values)


@pytest.mark.anyio
async def test_dashboard_summary_binds_one_canonical_filter() -> None:
    connection = FakeConnection(
        {
            "total_events": 3,
            "distinct_users": 2,
            "distinct_event_types": 1,
            "distinct_source_components": 2,
        }
    )
    result = await AuditRepository(connection).get_dashboard_summary(
        _filters(event_type="PROMPT_INJECTION", source_component="guardrail", user_identifier="client-1")
    )
    assert result.total_events == 3
    statement = connection.statements[0]
    query = normalized_sql(statement).lower()
    assert "from audit.security_events" in query
    assert "event_type = %s" in query
    assert "source_component = %s" in query
    assert "user_identifier = %s" in query
    assert statement.parameters == (
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 4, tzinfo=UTC),
        "PROMPT_INJECTION",
        "guardrail",
        "client-1",
    )
    assert "portal." not in query and "ops." not in query and "rag." not in query


@pytest.mark.anyio
async def test_dashboard_timeseries_uses_utc_calendar_days_and_stable_order() -> None:
    connection = FakeConnection(
        [
            {"event_date": date(2026, 1, 1), "event_count": 2},
            {"event_date": date(2026, 1, 3), "event_count": 1},
        ]
    )
    result = await AuditRepository(connection).get_dashboard_timeseries(_filters())
    assert [(item.date, item.count) for item in result] == [
        (date(2026, 1, 1), 2),
        (date(2026, 1, 3), 1),
    ]
    query = normalized_sql(connection.statements[0]).lower()
    assert "occurred_at at time zone 'utc'" in query
    assert "order by event_date asc" in query


@pytest.mark.anyio
async def test_dashboard_detail_selects_only_explicitly_allowed_columns() -> None:
    moment = datetime(2026, 1, 2, 12, tzinfo=UTC)
    connection = FakeConnection(
        {
            "event_id": 7,
            "occurred_at": moment,
            "event_type": "PROMPT_INJECTION",
            "source_component": "guardrail",
            "user_identifier": "client-1",
            "resource_category": "API_KEY",
            "action_taken": "BLOCK",
            "result": "SUCCESS",
            "review_status": "UNREVIEWED",
            "request_reference": "reference-7",
            "sanitized_content": "[REDACTED]",
            "reviewed_at": None,
            "created_at": moment,
        }
    )
    detail = await AuditRepository(connection).get_dashboard_event_detail(7)
    assert detail is not None and detail.event_id == 7
    query = normalized_sql(connection.statements[0]).lower()
    assert "from audit.security_events" in query
    assert "sanitized_content" in query
    assert "review_note" not in query
    assert "raw_request" not in query
    assert connection.statements[0].parameters == (7,)


@pytest.mark.anyio
async def test_dashboard_breakdowns_allowlist_columns_and_exclude_null_users() -> None:
    connection = FakeConnection(
        [{"value": "PROMPT_INJECTION", "event_count": 3}],
        [{"value": "guardrail", "event_count": 3}],
        [{"value": "client-1", "event_count": 2}],
    )
    result = await AuditRepository(connection).get_dashboard_breakdowns(_filters())
    assert result.event_types[0].value == "PROMPT_INJECTION"
    assert result.source_components[0].value == "guardrail"
    assert result.users[0].count == 2
    statements = [normalized_sql(item).lower() for item in connection.statements]
    assert len(statements) == 3
    assert 'group by "event_type" order by event_count desc, value asc' in statements[0]
    assert 'group by "source_component" order by event_count desc, value asc' in statements[1]
    assert '"user_identifier" is not null' in statements[2]
    assert all("from audit.security_events" in query for query in statements)


@pytest.mark.anyio
async def test_event_page_is_bounded_allowlisted_and_stably_ordered() -> None:
    moment = datetime(2026, 1, 2, 12, tzinfo=UTC)
    connection = FakeConnection(
        {"total": 26},
        [
            {
                "event_id": 26,
                "occurred_at": moment,
                "event_type": "PROMPT_INJECTION",
                "source_component": "guardrail",
                "user_identifier": None,
                "resource_category": None,
                "action_taken": "BLOCK",
                "result": "SUCCESS",
                "review_status": "UNREVIEWED",
            }
        ],
    )
    result = await AuditRepository(connection).list_dashboard_events(
        _filters(), SecurityDashboardPage(page=2, page_size=25)
    )
    assert result.total == 26
    assert result.items[0].event_id == 26
    query = normalized_sql(connection.statements[1]).lower()
    assert "order by occurred_at desc, event_id desc limit %s offset %s" in query
    assert "sanitized_content" not in query and "review_note" not in query
    assert connection.statements[1].parameters[-2:] == (25, 25)


@pytest.mark.anyio
async def test_event_page_rejects_invalid_page_without_query() -> None:
    connection = FakeConnection()
    with pytest.raises(ValidationError):
        await AuditRepository(connection).list_dashboard_events(_filters(), SecurityDashboardPage(page=1001))
    assert connection.statements == []
