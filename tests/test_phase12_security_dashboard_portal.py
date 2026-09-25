"""Phase 12.10 Django client, filter, and rendered-output checks."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apps.web_portal.config.settings")
os.environ.setdefault("DJANGO_SECRET_KEY", "phase12-security-dashboard-test-key")

import django

django.setup()

import pytest
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from apps.agent_api.app.security.models import SecurityEventType
from apps.web_portal.admin_portal import security_views
from apps.web_portal.admin_portal.security_forms import (
    APPROVED_SECURITY_EVENT_TYPE_VALUES,
    SecurityDashboardFilterForm,
)
from apps.web_portal.integrations import audit_dashboard, internal_service
from apps.web_portal.integrations.audit_dashboard import (
    AuditBreakdownRow,
    AuditBreakdowns,
    AuditDashboardClient,
    AuditDashboardFilters,
    AuditDay,
    AuditEventDetail,
    AuditEventPage,
    AuditEventRow,
    AuditSummary,
    AuditDashboardSnapshot,
)
from apps.web_portal.integrations.audit_dashboard import AuditDashboardUnavailable


def _actor(*, role: str = "ADMIN", active: bool = True):
    return SimpleNamespace(
        is_authenticated=True,
        is_active=active,
        role=role,
        pk=uuid4(),
    )


def _snapshot(filters: AuditDashboardFilters, *, source: str = "guardrail") -> AuditDashboardSnapshot:
    row = AuditEventRow(
        event_id=8,
        occurred_at="2026-01-02T12:00:00+00:00",
        event_type="PROMPT_INJECTION",
        source_component=source,
        user_identifier="client-1",
        resource_category="API_KEY",
        action_taken="BLOCK",
        result="SUCCESS",
        review_status="UNREVIEWED",
    )
    return AuditDashboardSnapshot(
        summary=AuditSummary(
            total_events=1,
            distinct_users=1,
            distinct_event_types=1,
            distinct_source_components=1,
        ),
        timeseries=(AuditDay(date=date(2026, 1, 2), count=1),),
        breakdowns=AuditBreakdowns(
            event_types=(AuditBreakdownRow(value="PROMPT_INJECTION", count=1),),
            source_components=(AuditBreakdownRow(value=source, count=1),),
            users=(AuditBreakdownRow(value="client-1", count=1),),
        ),
        events=AuditEventPage(page=1, page_size=25, total=1, items=(row,)),
        filters=filters,
    )


def _request(path: str, *, user=None):
    request = RequestFactory().get(path)
    request.user = user or SimpleNamespace(is_authenticated=False, is_active=False)
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def test_filter_choices_match_exact_approved_security_event_enum() -> None:
    assert APPROVED_SECURITY_EVENT_TYPE_VALUES == {item.value for item in SecurityEventType}


def test_filter_form_defaults_to_last_30_utc_days_and_bounds_the_span() -> None:
    today = date(2026, 8, 12)
    form = SecurityDashboardFilterForm(
        {"date_from": "", "date_to": "", "page": "1"},
        today=today,
    )
    assert form.is_valid(), form.errors
    filters = form.dashboard_filters()
    assert (filters.date_to - filters.date_from).days == 29
    assert filters.date_to == today

    too_long = SecurityDashboardFilterForm(
        {"date_from": "2026-01-01", "date_to": "2026-04-01"},
        today=today,
    )
    assert not too_long.is_valid()


def test_filter_form_rejects_invalid_type_blank_and_oversized_identifiers() -> None:
    invalid_type = SecurityDashboardFilterForm(
        {"date_from": "2026-08-01", "date_to": "2026-08-12", "event_type": "INVENTED"}
    )
    assert not invalid_type.is_valid()
    blank_source = SecurityDashboardFilterForm(
        {"date_from": "2026-08-01", "date_to": "2026-08-12", "source_component": "   "}
    )
    assert not blank_source.is_valid()
    oversized_user = SecurityDashboardFilterForm(
        {
            "date_from": "2026-08-01",
            "date_to": "2026-08-12",
            "user_identifier": "x" * 129,
        }
    )
    assert not oversized_user.is_valid()


def test_typed_client_sends_same_normalized_filter_and_trusted_headers(monkeypatch) -> None:
    requests: list[tuple[str, dict[str, str], dict[str, str]]] = []
    actor = _actor()

    class Response:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class Client:
        def __init__(self, **kwargs):
            self.base_url = kwargs["base_url"]
            assert kwargs["trust_env"] is False
            assert kwargs["follow_redirects"] is False
            assert kwargs["timeout"].connect <= 10

        def request(self, method, path, *, params, headers, json):
            url = self.base_url + path
            requests.append((method, url, dict(params or {}), dict(headers)))
            if url.endswith("/summary"):
                payload = {
                    "total_events": 1,
                    "distinct_users": 1,
                    "distinct_event_types": 1,
                    "distinct_source_components": 1,
                }
            elif url.endswith("/timeseries"):
                payload = [{"date": "2026-01-02", "count": 1}]
            elif url.endswith("/breakdowns"):
                payload = {
                    "event_types": [{"value": "PROMPT_INJECTION", "count": 1}],
                    "source_components": [{"value": "guardrail", "count": 1}],
                    "users": [{"value": "client-1", "count": 1}],
                }
            else:
                payload = {
                    "page": 2,
                    "page_size": 25,
                    "total": 1,
                    "items": [],
                }
            return Response(payload)

        def close(self):
            return None

    monkeypatch.setattr(audit_dashboard.httpx, "Client", Client)
    monkeypatch.setattr(internal_service.settings, "AGENT_API_SERVICE_TOKEN", "server-only-token")
    monkeypatch.setattr(internal_service.settings, "AGENT_API_INTERNAL_URL", "http://private-api")
    filters = AuditDashboardFilters(
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 30),
        event_type="PROMPT_INJECTION",
        source_component="guardrail",
        user_identifier="client-1",
    )

    snapshot = AuditDashboardClient(actor).snapshot(filters, page=2)

    assert snapshot.summary.total_events == 1
    assert len(requests) == 4
    canonical = requests[0][2]
    assert all(request[2] == canonical for request in requests[:3])
    assert {key: value for key, value in requests[3][2].items() if key not in {"page", "page_size"}} == canonical
    assert requests[3][2]["page"] == "2"
    assert all(request[3]["X-Authenticated-Role"] == "ADMIN" for request in requests)
    assert all(request[3]["X-Ops-Authorized"] == "false" for request in requests)
    assert all(request[3]["X-Authenticated-User-Id"] == str(actor.pk) for request in requests)
    assert all(request[3]["Authorization"] == "Bearer server-only-token" for request in requests)
    assert "server-only-token" not in repr(snapshot)


def test_typed_client_fails_closed_for_wrong_or_inactive_actor(monkeypatch) -> None:
    with pytest.raises(audit_dashboard.AuditDashboardUnavailable):
        AuditDashboardClient(_actor(role="CLIENT")).snapshot(
            AuditDashboardFilters(date_from=date(2026, 1, 1), date_to=date(2026, 1, 2))
        )
    with pytest.raises(audit_dashboard.AuditDashboardUnavailable):
        AuditDashboardClient(_actor(active=False)).snapshot(
            AuditDashboardFilters(date_from=date(2026, 1, 1), date_to=date(2026, 1, 2))
        )


def test_dashboard_html_escapes_audit_values_and_never_renders_secrets(monkeypatch) -> None:
    malicious_source = "<img src=x onerror=alert(1)>"
    filters = AuditDashboardFilters(date_from=date(2026, 1, 1), date_to=date(2026, 1, 30))
    monkeypatch.setattr(
        security_views.AuditDashboardClient,
        "snapshot",
        lambda self, filters, *, page, page_size: _snapshot(filters, source=malicious_source),
    )
    response = security_views.security_dashboard(
        _request(
            "/admin-portal/security/?date_from=2026-01-01&date_to=2026-01-30",
            user=_actor(),
        )
    )
    body = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "&lt;img src=x onerror=alert(1)&gt;" in body
    assert malicious_source not in body
    assert "security-dashboard-data" in body
    assert "AGENT_API_SERVICE_TOKEN" not in body
    assert "server-only-token" not in body
    assert "review_note" not in body
    assert "localhost:8000" not in body


def test_dashboard_clamps_pages_beyond_the_last_result(monkeypatch) -> None:
    calls = []

    def snapshot(self, filters, *, page, page_size):
        calls.append(page)
        return _snapshot(filters)

    monkeypatch.setattr(audit_dashboard.AuditDashboardClient, "snapshot", snapshot)
    response = security_views.security_dashboard(
        _request(
            "/admin-portal/security/?date_from=2026-01-01&date_to=2026-01-30&page=99",
            user=_actor(),
        )
    )
    body = response.content.decode("utf-8")
    assert response.status_code == 200
    assert calls == [99, 1]
    assert "Página 1 de 1" in body


def test_event_detail_template_escapes_sanitized_content(monkeypatch) -> None:
    event = AuditEventDetail(
        event_id=5,
        occurred_at="2026-01-02T12:00:00+00:00",
        event_type="PROMPT_INJECTION",
        source_component="guardrail",
        user_identifier=None,
        resource_category=None,
        action_taken="BLOCK",
        result="SUCCESS",
        review_status="UNREVIEWED",
        request_reference=None,
        sanitized_content="<script>alert(1)</script>",
        reviewed_at=None,
        created_at="2026-01-02T12:00:00+00:00",
    )
    monkeypatch.setattr(audit_dashboard.AuditDashboardClient, "event_detail", lambda self, event_id: event)
    response = security_views.security_event_detail(
        _request("/admin-portal/security/events/5/", user=_actor()),
        event_id=5,
    )
    body = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
    assert "<script>alert(1)</script>" not in body
    assert "review_note" not in body


def test_security_views_preserve_active_admin_boundary(monkeypatch) -> None:
    monkeypatch.setattr(
        security_views.AuditDashboardClient,
        "snapshot",
        lambda self, filters, *, page, page_size: _snapshot(filters),
    )
    anonymous = security_views.security_dashboard(_request("/admin-portal/security/"))
    assert anonymous.status_code == 302
    for role in ("CLIENT", "SUPPORT_AGENT"):
        with pytest.raises(PermissionDenied):
            security_views.security_dashboard(_request("/admin-portal/security/", user=_actor(role=role)))


def test_invalid_dashboard_data_request_returns_controlled_json() -> None:
    response = security_views.security_dashboard_data(
        _request(
            "/admin-portal/security/data/?date_from=2026-01-01&date_to=2026-04-01",
            user=_actor(),
        )
    )
    assert response.status_code == 422
    assert b"database" not in response.content.lower()
    assert b"Traceback" not in response.content


def test_api_unavailable_and_empty_states_are_controlled(monkeypatch) -> None:
    def unavailable(*_args, **_kwargs):
        raise AuditDashboardUnavailable

    monkeypatch.setattr(audit_dashboard.AuditDashboardClient, "snapshot", unavailable)
    unavailable_response = security_views.security_dashboard(
        _request("/admin-portal/security/", user=_actor())
    )
    assert unavailable_response.status_code == 503
    assert "temporariamente indisponíveis" in unavailable_response.content.decode("utf-8")
    assert "httpx" not in unavailable_response.content.decode("utf-8").lower()

    empty = _snapshot(AuditDashboardFilters(date_from=date(2026, 1, 1), date_to=date(2026, 1, 30)))
    empty = replace(
        empty,
        summary=AuditSummary(total_events=0, distinct_users=0, distinct_event_types=0, distinct_source_components=0),
        timeseries=(),
        breakdowns=AuditBreakdowns(event_types=(), source_components=(), users=()),
        events=AuditEventPage(page=1, page_size=25, total=0, items=()),
    )
    monkeypatch.setattr(audit_dashboard.AuditDashboardClient, "snapshot", lambda self, filters, **_kwargs: empty)
    empty_response = security_views.security_dashboard(
        _request("/admin-portal/security/", user=_actor())
    )
    assert empty_response.status_code == 200
    assert "Nenhum evento de segurança encontrado" in empty_response.content.decode("utf-8")


def test_security_javascript_uses_text_safe_chart_labels_and_no_fastapi() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "apps/web_portal/static/admin-security.js").read_text(encoding="utf-8")
    assert "requestSubmit" in source
    assert "innerHTML" not in source
    assert "fetch(" not in source
    assert "localhost:8000" not in source
    assert "AGENT_API_SERVICE_TOKEN" not in source
