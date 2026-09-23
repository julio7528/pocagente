"""Application-owned, provider-neutral persistence for router security blocks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.repositories.audit import AuditRepository
from apps.agent_api.app.security.models import (
    SecurityAction,
    SecurityClassification,
    SanitizedSecurityEvent,
    SecurityAuditContext,
    SecurityAuditResult,
    SecurityAuditStatus,
    SecurityEventType,
)
from apps.agent_api.app.security.sanitization import sanitize_security_content


class SecurityAuditSink(Protocol):
    """Persistence-independent sink consumed by the orchestration boundary."""

    async def record_many(
        self, events: tuple[SanitizedSecurityEvent, ...]
    ) -> tuple[int, ...]:
        """Persist one request's already-sanitized events atomically."""

    async def record(self, event: SanitizedSecurityEvent) -> int:
        """Persist one event through the same batch transaction boundary."""


class PostgresSecurityAuditSink:
    """Adapter that owns the approved transaction -> AuditRepository handoff."""

    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    async def record_many(self, events: tuple[SanitizedSecurityEvent, ...]) -> tuple[int, ...]:
        async with self._database.transaction() as connection:
            repository = AuditRepository(connection)
            event_ids: list[int] = []
            for event in events:
                event_ids.append(
                    await repository.write_sanitized_security_event(event.as_repository_record())
                )
            return tuple(event_ids)

    async def record(self, event: SanitizedSecurityEvent) -> int:
        return (await self.record_many((event,)))[0]


class SecurityAuditService:
    """Sanitize and record a request already classified as ``SECURITY_BLOCK``."""

    def __init__(self, sink: SecurityAuditSink) -> None:
        self._sink = sink

    async def record_router_security_block(
        self,
        *,
        message: str,
        context: SecurityAuditContext,
        security_semantics: tuple[SecurityClassification, ...],
        source_component: str = "router_security_guardrail",
        action_taken: SecurityAction = SecurityAction.BLOCK,
    ) -> SecurityAuditResult:
        """Record one request's typed policy-trigger events without reclassifying user text."""

        try:
            if not security_semantics:
                raise ValueError("security blocks require typed security semantics")
            sanitized_content = sanitize_security_content(message)
            occurred_at = datetime.now(UTC)
            events = tuple(
                SanitizedSecurityEvent(
                    occurred_at=occurred_at,
                    event_type=semantic.event_type,
                    user_identifier=context.user_identifier,
                    request_reference=context.request_reference,
                    resource_category=semantic.resource_category,
                    sanitized_content=sanitized_content,
                    source_component=source_component,
                    action_taken=action_taken,
                )
                for semantic in security_semantics
            )
            record_many = getattr(self._sink, "record_many", None)
            if record_many is None and len(events) == 1:
                event_ids = (await self._sink.record(events[0]),)  # type: ignore[attr-defined]
            elif record_many is None:
                raise TypeError("audit sink does not support atomic event batches")
            else:
                event_ids = await record_many(events)
        except Exception:
            return SecurityAuditResult(
                status=SecurityAuditStatus.UNAVAILABLE,
                reason="SECURITY_AUDIT_UNAVAILABLE",
            )
        return SecurityAuditResult(
            status=SecurityAuditStatus.RECORDED,
            event_ids=event_ids,
            reason="SECURITY_AUDIT_RECORDED",
        )
