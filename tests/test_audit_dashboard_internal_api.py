"""Trusted, read-only FastAPI boundary for the ADMIN AUDIT dashboard."""

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from apps.agent_api.app.auth import ServiceAuthConfig
from apps.agent_api.app.main import create_app
from apps.agent_api.app.security.dashboard_models import (
    SecurityDashboardBreakdownRow,
    SecurityDashboardBreakdowns,
    SecurityDashboardDay,
    SecurityDashboardEventDetail,
    SecurityDashboardEventPage,
    SecurityDashboardFilters,
    SecurityDashboardPage,
    SecurityDashboardSummary,
)
from apps.agent_api.app.security.dashboard_service import (
    SecurityDashboardEventMissing,
    SecurityDashboardUnavailable,
)

TOKEN = "phase12-audit-read-test-token"
ROUTES = (
    "/internal/admin/audit/summary",
    "/internal/admin/audit/timeseries",
    "/internal/admin/audit/breakdowns",
    "/internal/admin/audit/events",
)


class FakeDashboardService:
    def __init__(self, *, fail: bool = False, missing: bool = False) -> None:
        self.filters: list[SecurityDashboardFilters] = []
        self.calls: list[str] = []
        self.fail = fail
        self.missing = missing

    def _record(self, name: str, filters: SecurityDashboardFilters):
        self.calls.append(name)
        self.filters.append(filters)
        if self.fail:
            raise SecurityDashboardUnavailable

    async def summary(self, filters):
        self._record("summary", filters)
        return SecurityDashboardSummary(
            total_events=3,
            distinct_users=2,
            distinct_event_types=1,
            distinct_source_components=2,
        )

    async def timeseries(self, filters):
        self._record("timeseries", filters)
        return (SecurityDashboardDay(date=filters.date_from, count=3),)

    async def breakdowns(self, filters):
        self._record("breakdowns", filters)
        return SecurityDashboardBreakdowns(
            event_types=(SecurityDashboardBreakdownRow(value="PROMPT_INJECTION", count=3),),
            source_components=(SecurityDashboardBreakdownRow(value="guardrail", count=3),),
            users=(SecurityDashboardBreakdownRow(value="client-1", count=2),),
        )

    async def events(self, filters, page: SecurityDashboardPage):
        self._record("events", filters)
        return SecurityDashboardEventPage(page=page.page, page_size=page.page_size, total=3, items=())

    async def event_detail(self, event_id: int):
        self.calls.append("event_detail")
        if self.fail:
            raise SecurityDashboardUnavailable
        if self.missing:
            raise SecurityDashboardEventMissing
        return SecurityDashboardEventDetail(
            event_id=event_id,
            occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
            event_type="PROMPT_INJECTION",
            source_component="guardrail",
            user_identifier="client-1",
            resource_category=None,
            action_taken="BLOCK",
            result="SUCCESS",
            review_status="UNREVIEWED",
            request_reference="ref-1",
            sanitized_content="Protected request detected; sensitive content withheld.",
            reviewed_at=None,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )


def _headers(role: str = "ADMIN", ops: str = "false") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {TOKEN}",
        "X-Authenticated-User-Id": "admin-uuid",
        "X-Authenticated-Role": role,
        "X-Ops-Authorized": ops,
    }


def _client(service: FakeDashboardService | None = None) -> TestClient:
    return TestClient(
        create_app(
            chat_service=object(),
            auth_config=ServiceAuthConfig(service_token=SecretStr(TOKEN)),
            audit_dashboard_service=service or FakeDashboardService(),
        )
    )


@pytest.mark.parametrize("path", ROUTES + ("/internal/admin/audit/events/9",))
def test_internal_audit_routes_require_authenticated_admin_with_ops_false(path: str) -> None:
    with _client() as client:
        denied = client.get(path)
        assert denied.status_code == 401
        assert "Bearer" not in denied.text

        for role in ("CLIENT", "SUPPORT_AGENT"):
            response = client.get(path, headers=_headers(role))
            assert response.status_code == 403

        ops_true = client.get(path, headers=_headers(ops="true"))
        assert ops_true.status_code == 403

        allowed = client.get(path, headers=_headers())
        assert allowed.status_code in {200, 404}


def test_admin_requires_explicit_false_ops_header_and_valid_service_token() -> None:
    with _client() as client:
        missing_ops = client.get(
            "/internal/admin/audit/summary",
            headers={key: value for key, value in _headers().items() if key != "X-Ops-Authorized"},
        )
        invalid_token = client.get(
            "/internal/admin/audit/summary",
            headers={**_headers(), "Authorization": "Bearer wrong"},
        )
        browser_claims = client.get(
            "/internal/admin/audit/summary",
            headers={key: value for key, value in _headers().items() if key != "Authorization"},
        )
    assert missing_ops.status_code == 403
    assert invalid_token.status_code == 401
    assert browser_claims.status_code == 401


def test_canonical_filters_and_page_are_passed_to_typed_service() -> None:
    service = FakeDashboardService()
    with _client(service) as client:
        query = (
            "?date_from=2026-01-01&date_to=2026-01-03&event_type=PROMPT_INJECTION"
            "&source_component=guardrail&user_identifier=client-1"
        )
        for route in ROUTES:
            response = client.get(route + query, headers=_headers())
            assert response.status_code == 200, response.text
        events = client.get("/internal/admin/audit/events" + query + "&page=2&page_size=50", headers=_headers())
        assert events.status_code == 200

    assert len(service.filters) == 5
    assert all(filters == service.filters[0] for filters in service.filters)
    assert service.filters[0].start_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert service.calls[-1] == "events"


@pytest.mark.parametrize(
    "query",
    [
        "?date_from=2026-01-04&date_to=2026-01-03",
        "?date_from=2026-01-01&date_to=2026-04-01",
        "?event_type=not-approved",
        "?source_component=%20%20",
        "?user_identifier=%20%20",
        "?source_component=" + "x" * 129,
        "?page=1001",
        "?page_size=101",
        "?event_type=%27%20OR%201%3D1%20--",
    ],
)
def test_invalid_filters_and_unbounded_pagination_are_safe_422(query: str) -> None:
    with _client() as client:
        response = client.get("/internal/admin/audit/events" + query, headers=_headers())
    assert response.status_code == 422
    assert "SQL" not in response.text
    assert "Traceback" not in response.text


def test_event_detail_is_allowlisted_and_missing_is_controlled() -> None:
    with _client() as client:
        found = client.get("/internal/admin/audit/events/9", headers=_headers())
        with _client(FakeDashboardService(missing=True)) as missing:
            absent = missing.get("/internal/admin/audit/events/999", headers=_headers())
    assert found.status_code == 200
    assert "review_note" not in found.json()
    assert "raw_request" not in found.json()
    assert absent.status_code == 404
    assert "not present" not in absent.text


def test_dashboard_database_failure_has_no_raw_exception_details() -> None:
    with _client(FakeDashboardService(fail=True)) as client:
        response = client.get("/internal/admin/audit/summary", headers=_headers())
    assert response.status_code == 503
    assert "temporarily unavailable" in response.text
    assert "driver" not in response.text.lower()


def test_admin_does_not_gain_general_chat_or_human_escalation_authority() -> None:
    with _client() as client:
        chat = client.post(
            "/chat",
            headers=_headers(),
            json={"message": "hello", "user_id": "admin-uuid"},
        )
        human = client.post(
            "/internal/human-escalation/transition",
            headers=_headers(),
            json={"conversation_id": "conversation", "current_state": "HUMAN", "action": "RESOLVE"},
        )
    assert chat.status_code == 403
    assert human.status_code == 403


def test_dashboard_internal_api_has_no_audit_mutation_methods() -> None:
    with _client() as client:
        response = client.post(
            "/internal/admin/audit/summary",
            headers=_headers(),
            json={"event_id": 1, "review_status": "REVIEWED"},
        )
    assert response.status_code == 405
    assert "review_status" not in response.text
