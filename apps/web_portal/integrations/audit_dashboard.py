"""Typed server-only client for the narrow internal AUDIT dashboard API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from apps.web_portal.accounts.models import User
from apps.web_portal.integrations.internal_service import (
    InternalServiceConfigurationError,
    InternalServicePrincipalError,
    request_internal,
)


class AuditDashboardUnavailable(Exception):
    """Safe failure for internal AUDIT API connectivity or contract errors."""


class AuditDashboardInvalidFilters(Exception):
    """The internal API rejected a locally normalized dashboard filter."""


class AuditDashboardEventMissing(Exception):
    """The requested AUDIT event is not available."""


class AuditSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    total_events: int = Field(ge=0)
    distinct_users: int = Field(ge=0)
    distinct_event_types: int = Field(ge=0)
    distinct_source_components: int = Field(ge=0)


class AuditDay(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    date: date
    count: int = Field(ge=0)


class AuditBreakdownRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str = Field(min_length=1, max_length=256)
    count: int = Field(ge=0)


class AuditBreakdowns(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_types: tuple[AuditBreakdownRow, ...]
    source_components: tuple[AuditBreakdownRow, ...]
    users: tuple[AuditBreakdownRow, ...]


class AuditEventRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: int = Field(ge=1)
    occurred_at: datetime
    event_type: str
    source_component: str
    user_identifier: str | None
    resource_category: str | None
    action_taken: str
    result: str
    review_status: str


class AuditEventPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    page: int = Field(ge=1, le=1000)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    items: tuple[AuditEventRow, ...]


class AuditEventDetail(AuditEventRow):
    request_reference: str | None
    sanitized_content: str | None
    reviewed_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class AuditDashboardFilters:
    """One normalized filter state shared by every dashboard endpoint."""

    date_from: date
    date_to: date
    event_type: str = ""
    source_component: str = ""
    user_identifier: str = ""

    def query_params(self) -> dict[str, str]:
        params = {
            "date_from": self.date_from.isoformat(),
            "date_to": self.date_to.isoformat(),
        }
        if self.event_type:
            params["event_type"] = self.event_type
        if self.source_component:
            params["source_component"] = self.source_component
        if self.user_identifier:
            params["user_identifier"] = self.user_identifier
        return params

    def state(self) -> dict[str, str]:
        return {
            **self.query_params(),
            "event_type": self.event_type,
            "source_component": self.source_component,
            "user_identifier": self.user_identifier,
        }


@dataclass(frozen=True)
class AuditDashboardSnapshot:
    summary: AuditSummary
    timeseries: tuple[AuditDay, ...]
    breakdowns: AuditBreakdowns
    events: AuditEventPage
    filters: AuditDashboardFilters


ModelT = TypeVar("ModelT", bound=BaseModel)


class AuditDashboardClient:
    """Call only the five approved, read-only internal AUDIT endpoints."""

    _ENDPOINTS = {
        "summary": "/internal/admin/audit/summary",
        "timeseries": "/internal/admin/audit/timeseries",
        "breakdowns": "/internal/admin/audit/breakdowns",
        "events": "/internal/admin/audit/events",
        "event_detail": "/internal/admin/audit/events/{event_id}",
    }

    def __init__(self, actor: User) -> None:
        self._actor = actor

    def _headers(self) -> dict[str, str]:
        if (
            not getattr(self._actor, "is_authenticated", False)
            or not self._actor.is_active
            or self._actor.role != User.Role.ADMIN
        ):
            raise AuditDashboardUnavailable
        from apps.web_portal.integrations.internal_service import trusted_service_headers

        try:
            return trusted_service_headers(self._actor, ops_authorized=False)
        except (InternalServiceConfigurationError, InternalServicePrincipalError) as exc:
            raise AuditDashboardUnavailable from exc

    def _get(
        self,
        endpoint: str,
        *,
        params: dict[str, str] | None,
        response_type: type[ModelT] | None,
    ) -> ModelT | tuple[AuditDay, ...]:
        self._headers()
        try:
            response = request_internal(
                "GET", endpoint, actor=self._actor, ops_authorized=False, params=params
            )
            if response.status_code == 422:
                raise AuditDashboardInvalidFilters
            if response.status_code == 404:
                raise AuditDashboardEventMissing
            if response.status_code != 200:
                raise AuditDashboardUnavailable
            payload = response.json()
            if response_type is None:
                return tuple(AuditDay.model_validate(item) for item in payload)
            return response_type.model_validate(payload)
        except (
            httpx.HTTPError,
            InternalServiceConfigurationError,
            InternalServicePrincipalError,
            ValidationError,
            TypeError,
            ValueError,
        ) as exc:
            raise AuditDashboardUnavailable from exc

    def snapshot(
        self,
        filters: AuditDashboardFilters,
        *,
        page: int = 1,
        page_size: int = 25,
    ) -> AuditDashboardSnapshot:
        params = filters.query_params()
        summary = self._get(
            self._ENDPOINTS["summary"], params=params, response_type=AuditSummary
        )
        timeseries = self._get(
            self._ENDPOINTS["timeseries"], params=params, response_type=None
        )
        breakdowns = self._get(
            self._ENDPOINTS["breakdowns"], params=params, response_type=AuditBreakdowns
        )
        events = self._get(
            self._ENDPOINTS["events"],
            params={**params, "page": str(page), "page_size": str(page_size)},
            response_type=AuditEventPage,
        )
        return AuditDashboardSnapshot(
            summary=summary,
            timeseries=timeseries,
            breakdowns=breakdowns,
            events=events,
            filters=filters,
        )

    def event_detail(self, event_id: int) -> AuditEventDetail:
        if event_id < 1:
            raise AuditDashboardEventMissing
        endpoint = self._ENDPOINTS["event_detail"].format(event_id=event_id)
        result = self._get(endpoint, params=None, response_type=AuditEventDetail)
        assert isinstance(result, AuditEventDetail)
        return result
