"""AUDIT application service for the read-only ADMIN security dashboard."""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol

from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.errors import SafeDatabaseError
from apps.agent_api.app.database.repositories.audit import AuditRepository
from apps.agent_api.app.security.dashboard_models import (
    SecurityDashboardBreakdowns,
    SecurityDashboardDay,
    SecurityDashboardEventDetail,
    SecurityDashboardEventPage,
    SecurityDashboardFilters,
    SecurityDashboardPage,
    SecurityDashboardSummary,
)
from apps.agent_api.app.security.sanitization import sanitize_security_content


class SecurityDashboardUnavailable(Exception):
    """Safe service failure; it intentionally contains no driver detail."""


class SecurityDashboardEventMissing(Exception):
    """The requested event is not present in the AUDIT repository."""


class SecurityDashboardServiceContract(Protocol):
    async def summary(self, filters: SecurityDashboardFilters) -> SecurityDashboardSummary: ...

    async def timeseries(self, filters: SecurityDashboardFilters) -> tuple[SecurityDashboardDay, ...]: ...

    async def breakdowns(self, filters: SecurityDashboardFilters) -> SecurityDashboardBreakdowns: ...

    async def events(
        self,
        filters: SecurityDashboardFilters,
        page: SecurityDashboardPage,
    ) -> SecurityDashboardEventPage: ...

    async def event_detail(self, event_id: int) -> SecurityDashboardEventDetail: ...


class SecurityDashboardService:
    """Compose bounded dashboard reads through the existing AuditRepository."""

    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    async def summary(self, filters: SecurityDashboardFilters) -> SecurityDashboardSummary:
        try:
            async with self._database.connection() as connection:
                return await AuditRepository(connection).get_dashboard_summary(filters)
        except SafeDatabaseError as exc:
            raise SecurityDashboardUnavailable from exc

    async def timeseries(
        self,
        filters: SecurityDashboardFilters,
    ) -> tuple[SecurityDashboardDay, ...]:
        try:
            async with self._database.connection() as connection:
                rows = await AuditRepository(connection).get_dashboard_timeseries(filters)
        except SafeDatabaseError as exc:
            raise SecurityDashboardUnavailable from exc

        counts = {row.date: row.count for row in rows}
        day = filters.date_from
        end = filters.date_to
        assert day is not None and end is not None
        result: list[SecurityDashboardDay] = []
        while day <= end:
            result.append(SecurityDashboardDay(date=day, count=counts.get(day, 0)))
            day += timedelta(days=1)
        return tuple(result)

    async def breakdowns(
        self,
        filters: SecurityDashboardFilters,
    ) -> SecurityDashboardBreakdowns:
        try:
            async with self._database.connection() as connection:
                return await AuditRepository(connection).get_dashboard_breakdowns(filters)
        except SafeDatabaseError as exc:
            raise SecurityDashboardUnavailable from exc

    async def events(
        self,
        filters: SecurityDashboardFilters,
        page: SecurityDashboardPage,
    ) -> SecurityDashboardEventPage:
        try:
            async with self._database.connection() as connection:
                return await AuditRepository(connection).list_dashboard_events(filters, page)
        except SafeDatabaseError as exc:
            raise SecurityDashboardUnavailable from exc

    async def event_detail(self, event_id: int) -> SecurityDashboardEventDetail:
        try:
            async with self._database.connection() as connection:
                detail = await AuditRepository(connection).get_dashboard_event_detail(event_id)
        except SafeDatabaseError as exc:
            raise SecurityDashboardUnavailable from exc
        if detail is None:
            raise SecurityDashboardEventMissing
        return detail.model_copy(
            update={"sanitized_content": sanitize_security_content(detail.sanitized_content)}
        )
