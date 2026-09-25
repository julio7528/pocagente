"""Disposable-PostgreSQL validation of the Phase 12.10 AUDIT read model."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.repositories.audit import AuditRepository
from apps.agent_api.app.security.dashboard_models import SecurityDashboardFilters, SecurityDashboardPage
from apps.agent_api.app.security.dashboard_service import SecurityDashboardService
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_PHASE1210_DB_INTEGRATION") != "1",
    reason="Disposable PostgreSQL Phase 12.10 integration is opt-in",
)

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "database" / "migrations"


@pytest.fixture
def disposable_audit_config(real_database_config: DatabaseConfig):
    """Create, migrate, seed, and always drop one uniquely named test database."""

    database_name = f"getnet_support_phase12_10_{uuid4().hex[:10]}"
    connection_kwargs = real_database_config.psycopg_connection_kwargs()
    admin_kwargs = {key: value for key, value in connection_kwargs.items() if key != "dbname"}
    created = False
    with psycopg.connect(dbname="postgres", autocommit=True, **admin_kwargs) as administrator:
        with administrator.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_name,))
            if cursor.fetchone() is not None:
                raise RuntimeError("Unique disposable database name unexpectedly exists")
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
            created = True

    isolated_config = real_database_config.model_copy(update={"database": database_name})
    try:
        with psycopg.connect(**isolated_config.psycopg_connection_kwargs(), autocommit=True) as connection:
            for migration in sorted(MIGRATIONS.glob("000[1-6]_*.sql")):
                with connection.cursor() as cursor:
                    cursor.execute(migration.read_text(encoding="utf-8"), prepare=False)
            with connection.cursor() as cursor:
                start = datetime(2026, 1, 1, tzinfo=UTC)
                fixture_events = (
                    (start - timedelta(microseconds=1), "PROMPT_INJECTION", "router_security_guardrail", "fixture-client-a"),
                    (start, "PROMPT_INJECTION", "router_security_guardrail", "fixture-client-a"),
                    (start + timedelta(days=1, hours=12), "PROMPT_INJECTION", "semantic_security_classifier", "fixture-client-b"),
                    (start + timedelta(days=2), "CREDENTIAL_REQUEST", "router_security_guardrail", None),
                    (start + timedelta(days=3), "PROMPT_INJECTION", "router_security_guardrail", "fixture-client-a"),
                )
                for index, (occurred_at, event_type, source_component, user_identifier) in enumerate(fixture_events):
                    cursor.execute(
                        """
                        INSERT INTO audit.security_events (
                            occurred_at, event_type, source_component, user_identifier,
                            request_reference, sanitized_content, action_taken, result
                        ) VALUES (%s, %s, %s, %s, %s, %s, 'BLOCK', 'SUCCESS')
                        """,
                        (
                            occurred_at,
                            event_type,
                            source_component,
                            user_identifier,
                            f"phase12-10-fixture-{index}",
                            "Synthetic sanitized fixture content.",
                        ),
                    )
        yield isolated_config
    finally:
        if created:
            with psycopg.connect(dbname="postgres", autocommit=True, **admin_kwargs) as administrator:
                administrator.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name)))


def test_real_postgres_dashboard_aggregates_filters_boundaries_and_pagination(
    disposable_audit_config: DatabaseConfig,
) -> None:
    async def validate() -> None:
        database = PostgresDatabase(disposable_audit_config)
        await database.open()
        try:
            service = SecurityDashboardService(database)
            filters = SecurityDashboardFilters(
                date_from=date(2026, 1, 1),
                date_to=date(2026, 1, 3),
                event_type="PROMPT_INJECTION",
            )
            summary = await service.summary(filters)
            series = await service.timeseries(filters)
            breakdowns = await service.breakdowns(filters)
            page_one = await service.events(filters, SecurityDashboardPage(page=1, page_size=1))
            page_two = await service.events(filters, SecurityDashboardPage(page=2, page_size=1))
            assert summary.total_events == 2
            assert summary.distinct_users == 2
            assert [point.count for point in series] == [1, 1, 0]
            assert sum(point.count for point in series) == summary.total_events
            assert sum(row.count for row in breakdowns.event_types) == summary.total_events
            assert sum(row.count for row in breakdowns.source_components) == summary.total_events
            assert sum(row.count for row in breakdowns.users) == summary.total_events
            assert page_one.total == summary.total_events
            assert page_one.items[0].event_id != page_two.items[0].event_id
            assert page_one.items[0].occurred_at >= page_two.items[0].occurred_at

            combined = SecurityDashboardFilters(
                date_from=date(2026, 1, 2),
                date_to=date(2026, 1, 3),
                source_component="semantic_security_classifier",
                user_identifier="fixture-client-b",
            )
            result = await service.summary(combined)
            assert result.total_events == 1
            assert result.distinct_users == 1

            full_window = SecurityDashboardFilters(
                date_from=date(2026, 1, 1),
                date_to=date(2026, 1, 3),
            )
            full_summary = await service.summary(full_window)
            full_series = await service.timeseries(full_window)
            full_breakdowns = await service.breakdowns(full_window)
            assert full_summary.total_events == 3
            assert full_summary.distinct_users == 2
            assert sum(point.count for point in full_series) == 3
            assert sum(item.count for item in full_breakdowns.event_types) == 3
            assert sum(item.count for item in full_breakdowns.source_components) == 3
            # The NULL identifier event is omitted from the user breakdown.
            assert sum(item.count for item in full_breakdowns.users) == 2

            source_only = SecurityDashboardFilters(
                date_from=date(2026, 1, 1),
                date_to=date(2026, 1, 3),
                source_component="router_security_guardrail",
            )
            user_only = SecurityDashboardFilters(
                date_from=date(2026, 1, 1),
                date_to=date(2026, 1, 3),
                user_identifier="fixture-client-a",
            )
            exact_start = SecurityDashboardFilters(
                date_from=date(2026, 1, 1),
                date_to=date(2026, 1, 1),
            )
            just_after_start_day = SecurityDashboardFilters(
                date_from=date(2026, 1, 2),
                date_to=date(2026, 1, 2),
            )
            assert (await service.summary(source_only)).total_events == 2
            assert (await service.summary(user_only)).total_events == 1
            assert (await service.summary(exact_start)).total_events == 1
            assert (await service.summary(just_after_start_day)).total_events == 1
        finally:
            await database.close()

    run_async(validate())


def test_real_postgres_event_detail_has_safe_allowlisted_fields(
    disposable_audit_config: DatabaseConfig,
) -> None:
    async def validate() -> None:
        database = PostgresDatabase(disposable_audit_config)
        await database.open()
        try:
            async with database.connection() as connection:
                rows = await AuditRepository(connection).list_dashboard_events(
                    SecurityDashboardFilters(date_from=date(2026, 1, 1), date_to=date(2026, 1, 5)),
                    SecurityDashboardPage(page=1, page_size=100),
                )
            # The fifth fixture is deliberately one microsecond before the
            # inclusive Jan 1 start boundary and must not be returned.
            assert rows.total == 4
            assert all(not hasattr(row, "sanitized_content") for row in rows.items)
            detail = await SecurityDashboardService(database).event_detail(rows.items[0].event_id)
            assert detail.event_id == rows.items[0].event_id
            assert "review_note" not in detail.model_dump()
        finally:
            await database.close()

    run_async(validate())
