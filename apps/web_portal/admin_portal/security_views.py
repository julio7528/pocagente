"""Product ADMIN views for read-only security-event inspection."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlencode

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.web_portal.accounts.models import User
from apps.web_portal.accounts.views import role_required
from apps.web_portal.admin_portal.security_forms import SecurityDashboardFilterForm
from apps.web_portal.integrations.audit_dashboard import (
    AuditDashboardClient,
    AuditDashboardEventMissing,
    AuditDashboardInvalidFilters,
    AuditDashboardUnavailable,
)


PAGE_SIZE = 25


def _filter_form(request: HttpRequest) -> SecurityDashboardFilterForm:
    """Bind a complete UTC date window even when only some query fields exist."""

    data = request.GET.copy()
    today = datetime.now(UTC).date()
    try:
        end = date.fromisoformat(data.get("date_to", "")) if data.get("date_to") else today
    except ValueError:
        end = today
    if not data.get("date_to"):
        data["date_to"] = today.isoformat()
    if not data.get("date_from"):
        data["date_from"] = (end - timedelta(days=29)).isoformat()
    if not data.get("page"):
        data["page"] = "1"
    return SecurityDashboardFilterForm(data, today=today)


def _snapshot_payload(snapshot) -> dict[str, object]:
    events = snapshot.events.model_dump(mode="json")
    for item in events["items"]:
        item["detail_url"] = reverse(
            "admin-security-event-detail", kwargs={"event_id": item["event_id"]}
        )
    return {
        "summary": snapshot.summary.model_dump(mode="json"),
        "timeseries": [point.model_dump(mode="json") for point in snapshot.timeseries],
        "breakdowns": snapshot.breakdowns.model_dump(mode="json"),
        "events": events,
        "filters": snapshot.filters.state(),
        "page_count": max(1, math.ceil(snapshot.events.total / PAGE_SIZE)),
    }


def _data_error(message: str, status_code: int) -> JsonResponse:
    return JsonResponse({"error": message}, status=status_code)


def _read_snapshot(request: HttpRequest, form: SecurityDashboardFilterForm):
    filters = form.dashboard_filters()
    client = AuditDashboardClient(request.user)
    requested_page = form.page_number
    snapshot = client.snapshot(filters, page=requested_page, page_size=PAGE_SIZE)
    last_page = max(1, math.ceil(snapshot.events.total / PAGE_SIZE))
    if requested_page > last_page:
        snapshot = client.snapshot(filters, page=last_page, page_size=PAGE_SIZE)
    return snapshot


@never_cache
@role_required(User.Role.ADMIN)
@require_GET
def security_dashboard(request: HttpRequest) -> HttpResponse:
    form = _filter_form(request)
    if not form.is_valid():
        return render(
            request,
            "admin_portal/security_dashboard.html",
            {"section": "security", "form": form, "snapshot": None, "error_message": None},
            status=400,
        )
    try:
        filters = form.dashboard_filters()
        snapshot = _read_snapshot(request, form)
    except AuditDashboardInvalidFilters:
        form.add_error(None, "Os filtros informados não são válidos. Revise o período e tente novamente.")
        return render(
            request,
            "admin_portal/security_dashboard.html",
            {"section": "security", "form": form, "snapshot": None, "error_message": None},
            status=400,
        )
    except AuditDashboardUnavailable:
        return render(
            request,
            "admin_portal/security_dashboard.html",
            {
                "section": "security",
                "form": form,
                "snapshot": None,
                "error_message": "Os dados de segurança estão temporariamente indisponíveis.",
            },
            status=503,
        )
    payload = _snapshot_payload(snapshot)
    query = filters.query_params()
    query.pop("page", None)
    page_query = urlencode(query)
    return render(
        request,
        "admin_portal/security_dashboard.html",
        {
            "section": "security",
            "form": form,
            "snapshot": payload,
            "source_values": snapshot.breakdowns.source_components,
            "user_values": snapshot.breakdowns.users,
            "page_query": page_query,
            "reset_url": reverse("admin-security"),
        },
    )


@never_cache
@role_required(User.Role.ADMIN)
@require_GET
def security_dashboard_data(request: HttpRequest) -> JsonResponse:
    form = _filter_form(request)
    if not form.is_valid():
        return _data_error(
            "Revise os filtros informados.",
            422,
        )
    try:
        snapshot = _read_snapshot(request, form)
    except AuditDashboardInvalidFilters:
        return _data_error("Revise os filtros informados.", 422)
    except AuditDashboardUnavailable:
        return _data_error("Os dados de segurança estão temporariamente indisponíveis.", 503)
    return JsonResponse(_snapshot_payload(snapshot))


@never_cache
@role_required(User.Role.ADMIN)
@require_GET
def security_event_detail(request: HttpRequest, event_id: int) -> HttpResponse:
    try:
        event = AuditDashboardClient(request.user).event_detail(event_id)
    except AuditDashboardEventMissing:
        return render(
            request,
            "admin_portal/security_event_not_found.html",
            {"section": "security"},
            status=404,
        )
    except AuditDashboardUnavailable:
        return render(
            request,
            "admin_portal/security_event_unavailable.html",
            {"section": "security"},
            status=503,
        )
    return render(
        request,
        "admin_portal/security_event_detail.html",
        {"section": "security", "event": event},
    )
