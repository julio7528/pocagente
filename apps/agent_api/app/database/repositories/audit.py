"""Connection-bound persistence adapter for sanitized AUDIT events."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from psycopg import sql
from psycopg.rows import dict_row

from apps.agent_api.app.database.mapping import map_security_event
from apps.agent_api.app.database.models import SecurityEventRecord
from apps.agent_api.app.database.repositories.base import BaseRepository
from apps.agent_api.app.database.repositories.contracts import (
    RepositoryRecord,
    ReviewStatus,
)
from apps.agent_api.app.security.dashboard_models import (
    SecurityDashboardBreakdownRow,
    SecurityDashboardBreakdowns,
    SecurityDashboardDay,
    SecurityDashboardEventPage,
    SecurityDashboardEventDetail,
    SecurityDashboardEventRow,
    SecurityDashboardFilters,
    SecurityDashboardPage,
    SecurityDashboardSummary,
)


_EVENT_WRITE_COLUMNS = (
    "occurred_at",
    "event_type",
    "source_component",
    "user_identifier",
    "request_reference",
    "resource_category",
    "sanitized_content",
    "action_taken",
    "result",
    "review_status",
    "reviewed_at",
    "review_note",
)
_EVENT_REQUIRED_COLUMNS = frozenset(
    {"occurred_at", "event_type", "source_component", "action_taken", "result"}
)
_PROHIBITED_KEY_PARTS = (
    "password",
    "credential",
    "token",
    "api_key",
    "private_key",
    "connection_string",
    "cookie",
    "raw_request",
    "request_body",
    "payload",
)


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= 100:
        raise ValueError("Audit query limit must be between 1 and 100")


def _dashboard_where(
    filters: SecurityDashboardFilters,
    *,
    additional: sql.Composable | None = None,
) -> tuple[sql.Composable, tuple[object, ...]]:
    """Compose fixed predicates and bind all dashboard values as parameters."""

    clauses: list[sql.Composable] = [
        sql.SQL("occurred_at >= %s"),
        sql.SQL("occurred_at < %s"),
    ]
    parameters: list[object] = [filters.start_at, filters.end_before]
    if filters.event_type is not None:
        clauses.append(sql.SQL("event_type = %s"))
        parameters.append(filters.event_type.value)
    if filters.source_component is not None:
        clauses.append(sql.SQL("source_component = %s"))
        parameters.append(filters.source_component)
    if filters.user_identifier is not None:
        clauses.append(sql.SQL("user_identifier = %s"))
        parameters.append(filters.user_identifier)
    if additional is not None:
        clauses.append(additional)
    return sql.SQL(" WHERE ") + sql.SQL(" AND ").join(clauses), tuple(parameters)


def _validate_dashboard_page(page: SecurityDashboardPage) -> None:
    if not 1 <= page.page <= 1000:
        raise ValueError("Audit page must be between 1 and 1000")
    if not 1 <= page.page_size <= 100:
        raise ValueError("Audit page size must be between 1 and 100")


def _validate_event(event: Mapping[str, object]) -> tuple[str, ...]:
    for key in event:
        normalized = key.lower().replace("-", "_")
        if any(part in normalized for part in _PROHIBITED_KEY_PARTS):
            raise ValueError(f"Prohibited security-event field: {key}")
    unknown = set(event) - set(_EVENT_WRITE_COLUMNS)
    if unknown:
        raise ValueError(f"Unsupported fields: {', '.join(sorted(unknown))}")
    missing = _EVENT_REQUIRED_COLUMNS - set(event)
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(sorted(missing))}")
    return tuple(column for column in _EVENT_WRITE_COLUMNS if column in event)


class AuditRepository(BaseRepository):
    """Persist and retrieve sanitized security-event facts."""

    async def write_sanitized_security_event(self, event: RepositoryRecord) -> int:
        columns = _validate_event(event)
        statement = sql.SQL(
            "INSERT INTO audit.security_events ({columns}) VALUES ({values}) "
            "RETURNING event_id"
        ).format(
            columns=sql.SQL(", ").join(map(sql.Identifier, columns)),
            values=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, tuple(event[column] for column in columns))
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Security event creation returned no identity")
        return int(row["event_id"])

    async def get_security_event(
        self,
        event_id: int,
    ) -> SecurityEventRecord | None:
        statement = """
            SELECT event_id, occurred_at, event_type, source_component,
                  user_identifier, request_reference, resource_category,
                  sanitized_content, action_taken, result, review_status,
                  reviewed_at, review_note, created_at
            FROM audit.security_events
            WHERE event_id = %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (event_id,))
            row = await cursor.fetchone()
        return map_security_event(row) if row is not None else None

    async def get_dashboard_summary(
        self,
        filters: SecurityDashboardFilters,
    ) -> SecurityDashboardSummary:
        where, parameters = _dashboard_where(filters)
        statement = sql.SQL(
            "SELECT COUNT(*)::bigint AS total_events, "
            "COUNT(DISTINCT user_identifier)::bigint AS distinct_users, "
            "COUNT(DISTINCT event_type)::bigint AS distinct_event_types, "
            "COUNT(DISTINCT source_component)::bigint AS distinct_source_components "
            "FROM audit.security_events"
        ) + where
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, parameters)
            row = await cursor.fetchone()
        if row is None:
            return SecurityDashboardSummary(
                total_events=0,
                distinct_users=0,
                distinct_event_types=0,
                distinct_source_components=0,
            )
        return SecurityDashboardSummary(**row)

    async def get_dashboard_event_detail(
        self,
        event_id: int,
    ) -> SecurityDashboardEventDetail | None:
        """Read only the allowlisted columns approved for the dashboard detail."""

        statement = """
            SELECT event_id, occurred_at, event_type, source_component,
                   user_identifier, resource_category, action_taken, result,
                   review_status, request_reference, sanitized_content,
                   reviewed_at, created_at
            FROM audit.security_events
            WHERE event_id = %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (event_id,))
            row = await cursor.fetchone()
        return SecurityDashboardEventDetail(**row) if row is not None else None

    async def get_dashboard_timeseries(
        self,
        filters: SecurityDashboardFilters,
    ) -> tuple[SecurityDashboardDay, ...]:
        where, parameters = _dashboard_where(filters)
        statement = sql.SQL(
            "SELECT (occurred_at AT TIME ZONE 'UTC')::date AS event_date, "
            "COUNT(*)::bigint AS event_count "
            "FROM audit.security_events"
        ) + where + sql.SQL(
            " GROUP BY event_date ORDER BY event_date ASC"
        )
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, parameters)
            rows = await cursor.fetchall()
        return tuple(
            SecurityDashboardDay(date=row["event_date"], count=row["event_count"])
            for row in rows
        )

    async def get_dashboard_breakdowns(
        self,
        filters: SecurityDashboardFilters,
    ) -> SecurityDashboardBreakdowns:
        async def values_for(
            column: str,
            *,
            nonnull_only: bool = False,
        ) -> tuple[SecurityDashboardBreakdownRow, ...]:
            extra = (
                sql.SQL("{column} IS NOT NULL").format(column=sql.Identifier(column))
                if nonnull_only
                else None
            )
            query_where, query_parameters = _dashboard_where(filters, additional=extra)
            statement = sql.SQL(
                "SELECT {column} AS value, COUNT(*)::bigint AS event_count "
                "FROM audit.security_events"
            ).format(column=sql.Identifier(column)) + query_where + sql.SQL(
                " GROUP BY {column} ORDER BY event_count DESC, value ASC"
            ).format(column=sql.Identifier(column))
            async with self._cursor(row_factory=dict_row) as cursor:
                await cursor.execute(statement, query_parameters)
                rows = await cursor.fetchall()
            return tuple(
                SecurityDashboardBreakdownRow(value=row["value"], count=row["event_count"])
                for row in rows
            )

        # Fixed allowlist: SQL identifiers never originate from a request.
        event_types = await values_for("event_type")
        sources = await values_for("source_component")
        users = await values_for("user_identifier", nonnull_only=True)
        return SecurityDashboardBreakdowns(
            event_types=event_types,
            source_components=sources,
            users=users,
        )

    async def list_dashboard_events(
        self,
        filters: SecurityDashboardFilters,
        page: SecurityDashboardPage,
    ) -> SecurityDashboardEventPage:
        _validate_dashboard_page(page)
        where, parameters = _dashboard_where(filters)
        count_statement = sql.SQL(
            "SELECT COUNT(*)::bigint AS total FROM audit.security_events"
        ) + where
        offset = (page.page - 1) * page.page_size
        list_statement = sql.SQL(
            "SELECT event_id, occurred_at, event_type, source_component, "
            "user_identifier, resource_category, action_taken, result, review_status "
            "FROM audit.security_events"
        ) + where + sql.SQL(
            " ORDER BY occurred_at DESC, event_id DESC LIMIT %s OFFSET %s"
        )
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(count_statement, parameters)
            count_row = await cursor.fetchone()
            total = int(count_row["total"]) if count_row else 0
            await cursor.execute(list_statement, (*parameters, page.page_size, offset))
            rows = await cursor.fetchall()
        items = tuple(SecurityDashboardEventRow(**row) for row in rows)
        return SecurityDashboardEventPage(
            page=page.page,
            page_size=page.page_size,
            total=total,
            items=items,
        )

    async def list_security_events_by_request_reference(
        self,
        request_reference: str,
        limit: int,
    ) -> Sequence[SecurityEventRecord]:
        _validate_limit(limit)
        statement = """
            SELECT event_id, occurred_at, event_type, source_component,
                  user_identifier, request_reference, resource_category,
                  sanitized_content, action_taken, result, review_status,
                  reviewed_at, review_note, created_at
            FROM audit.security_events
            WHERE request_reference = %s
            ORDER BY occurred_at DESC, event_id DESC
            LIMIT %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (request_reference, limit))
            rows = await cursor.fetchall()
        return tuple(map_security_event(row) for row in rows)

    async def list_unreviewed_security_events(
        self,
        limit: int,
    ) -> Sequence[SecurityEventRecord]:
        _validate_limit(limit)
        statement = """
            SELECT event_id, occurred_at, event_type, source_component,
                  user_identifier, request_reference, resource_category,
                  sanitized_content, action_taken, result, review_status,
                  reviewed_at, review_note, created_at
            FROM audit.security_events
            WHERE review_status = 'UNREVIEWED'
            ORDER BY occurred_at DESC, event_id DESC
            LIMIT %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (limit,))
            rows = await cursor.fetchall()
        return tuple(map_security_event(row) for row in rows)

    async def update_security_event_review(
        self,
        event_id: int,
        *,
        review_status: ReviewStatus,
        reviewed_at: datetime | None,
        review_note: str | None,
    ) -> None:
        if review_status not in {"UNREVIEWED", "REVIEWED"}:
            raise ValueError("Unsupported review status")
        if review_status == "UNREVIEWED" and reviewed_at is not None:
            raise ValueError("Unreviewed events cannot have reviewed_at")
        if review_status == "REVIEWED" and reviewed_at is None:
            raise ValueError("Reviewed events require reviewed_at")
        statement = """
            UPDATE audit.security_events
            SET review_status = %s, reviewed_at = %s, review_note = %s
            WHERE event_id = %s
        """
        async with self._cursor() as cursor:
            await cursor.execute(
                statement,
                (review_status, reviewed_at, review_note, event_id),
            )
