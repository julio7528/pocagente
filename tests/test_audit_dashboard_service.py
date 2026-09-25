"""AUDIT dashboard service mapping and bounded daily semantics."""

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime

import pytest

from apps.agent_api.app.database.errors import SafeConnectionError
from apps.agent_api.app.database.models import SecurityEventRecord
from apps.agent_api.app.security.dashboard_models import (
    SecurityDashboardBreakdowns,
    SecurityDashboardEventDetail,
    SecurityDashboardEventPage,
    SecurityDashboardFilters,
    SecurityDashboardPage,
    SecurityDashboardSummary,
)
from apps.agent_api.app.security.dashboard_service import (
    SecurityDashboardEventMissing,
    SecurityDashboardService,
    SecurityDashboardUnavailable,
)


class FakeRepository:
    async def get_dashboard_summary(self, filters):
        return SecurityDashboardSummary(
            total_events=1,
            distinct_users=1,
            distinct_event_types=1,
            distinct_source_components=1,
        )

    async def get_dashboard_timeseries(self, filters):
        from apps.agent_api.app.security.dashboard_models import SecurityDashboardDay

        return (SecurityDashboardDay(date=date(2026, 1, 2), count=2),)

    async def get_dashboard_breakdowns(self, filters):
        return SecurityDashboardBreakdowns(event_types=(), source_components=(), users=())

    async def list_dashboard_events(self, filters, page):
        return SecurityDashboardEventPage(page=page.page, page_size=page.page_size, total=0, items=())

    async def get_dashboard_event_detail(self, event_id):
        if event_id != 7:
            return None
        record = _record()
        return SecurityDashboardEventDetail(
            event_id=record.event_id,
            occurred_at=record.occurred_at,
            event_type=record.event_type,
            source_component=record.source_component,
            user_identifier=record.user_identifier,
            resource_category=record.resource_category,
            action_taken=record.action_taken,
            result=record.result,
            review_status=record.review_status,
            request_reference=record.request_reference,
            sanitized_content=record.sanitized_content,
            reviewed_at=record.reviewed_at,
            created_at=record.created_at,
        )


class FakeDatabase:
    def __init__(self, *, fail: bool = False):
        self.connection_count = 0
        self.fail = fail

    @asynccontextmanager
    async def connection(self):
        self.connection_count += 1
        if self.fail:
            raise SafeConnectionError
        yield object()


def _record() -> SecurityEventRecord:
    now = datetime(2026, 1, 2, 12, tzinfo=UTC)
    return SecurityEventRecord(
        event_id=7,
        occurred_at=now,
        event_type="PROMPT_INJECTION",
        source_component="guardrail",
        user_identifier="client-1",
        request_reference="req-7",
        resource_category="API_KEY",
        sanitized_content="Authorization: Bearer sk-abc123",
        action_taken="BLOCK",
        result="SUCCESS",
        review_status="UNREVIEWED",
        reviewed_at=None,
        review_note="Internal reviewer note must not be returned",
        created_at=now,
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_timeseries_is_zero_filled_over_exact_utc_filter_window(monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.agent_api.app.security.dashboard_service.AuditRepository",
        lambda _connection: FakeRepository(),
    )
    service = SecurityDashboardService(FakeDatabase())
    filters = SecurityDashboardFilters(date_from=date(2026, 1, 1), date_to=date(2026, 1, 3))

    result = await service.timeseries(filters)

    assert [(item.date, item.count) for item in result] == [
        (date(2026, 1, 1), 0),
        (date(2026, 1, 2), 2),
        (date(2026, 1, 3), 0),
    ]


@pytest.mark.anyio
async def test_event_detail_is_explicitly_mapped_sanitized_and_allowlisted(monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.agent_api.app.security.dashboard_service.AuditRepository",
        lambda _connection: FakeRepository(),
    )
    detail = await SecurityDashboardService(FakeDatabase()).event_detail(7)
    payload = detail.model_dump()
    assert detail.sanitized_content == "[REDACTED]"
    assert "sk-abc123" not in str(payload)
    assert "review_note" not in payload
    assert "raw_request" not in payload
    assert detail.event_id == 7


@pytest.mark.anyio
async def test_missing_event_and_database_failure_are_safe(monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.agent_api.app.security.dashboard_service.AuditRepository",
        lambda _connection: FakeRepository(),
    )
    service = SecurityDashboardService(FakeDatabase())
    with pytest.raises(SecurityDashboardEventMissing):
        await service.event_detail(99)
    with pytest.raises(SecurityDashboardUnavailable):
        await SecurityDashboardService(FakeDatabase(fail=True)).summary(
            SecurityDashboardFilters(date_from=date(2026, 1, 1), date_to=date(2026, 1, 2))
        )
