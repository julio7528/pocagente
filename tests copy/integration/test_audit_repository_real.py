"""Real transactional validation of the concrete AUDIT repository."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from apps.agent_api.app.database.config import DatabaseConfig
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.models import SecurityEventRecord
from apps.agent_api.app.database.repositories.audit import AuditRepository
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL integration tests are opt-in",
)


class _RollbackScenario(Exception):
    pass


def test_real_audit_repository_lifecycle_and_rollback(
    real_database_config: DatabaseConfig,
) -> None:
    unique = uuid4().hex
    request_reference = f"integration-audit-{unique}"
    occurred_at = datetime.now(UTC)

    async def validate() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            event_id: int | None = None
            with pytest.raises(_RollbackScenario):
                async with database.transaction() as connection:
                    repository = AuditRepository(connection)
                    event_id = await repository.write_sanitized_security_event(
                        {
                            "occurred_at": occurred_at,
                            "event_type": "PROMPT_INJECTION",
                            "source_component": "integration_validation",
                            "request_reference": request_reference,
                            "sanitized_content": "[SYNTHETIC REDACTED CONTENT]",
                            "action_taken": "BLOCK",
                            "result": "SUCCESS",
                        }
                    )
                    event = await repository.get_security_event(event_id)
                    assert isinstance(event, SecurityEventRecord)
                    assert event.request_reference == request_reference

                    correlated = (
                        await repository.list_security_events_by_request_reference(
                            request_reference, 10
                        )
                    )
                    assert [item.event_id for item in correlated] == [event_id]
                    unreviewed = await repository.list_unreviewed_security_events(100)
                    assert any(item.event_id == event_id for item in unreviewed)

                    reviewed_at = occurred_at + timedelta(seconds=1)
                    await repository.update_security_event_review(
                        event_id,
                        review_status="REVIEWED",
                        reviewed_at=reviewed_at,
                        review_note="Synthetic authorized review complete",
                    )
                    reviewed = await repository.get_security_event(event_id)
                    assert isinstance(reviewed, SecurityEventRecord)
                    assert reviewed.review_status == "REVIEWED"
                    assert reviewed.reviewed_at == reviewed_at
                    raise _RollbackScenario()

            assert event_id is not None
            async with database.connection() as connection:
                assert await AuditRepository(connection).get_security_event(event_id) is None
        finally:
            await database.close()

    run_async(validate())
