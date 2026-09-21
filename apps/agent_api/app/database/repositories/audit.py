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
