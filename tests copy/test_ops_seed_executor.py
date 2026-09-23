"""Mocked behavior tests for the generic OPS scenario executor."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from database.seed.ops.loader import get_scenario, load_scenarios
from database.seed.ops.scenario_executor import execute_ops_scenario


class _Repository:
    def __init__(self, existing: object | None = None, fail_on: str | None = None) -> None:
        self.existing = existing
        self.fail_on = fail_on
        self.calls: list[tuple[str, object]] = []
        self.identities = iter((101, 201, 301, 401, 501, 102))

    async def _call(self, name: str, payload: object = None):
        self.calls.append((name, payload))
        if self.fail_on == name:
            raise RuntimeError("synthetic executor failure")

    async def get_service_request_by_protocol(self, protocol: str):
        await self._call("get_service_request_by_protocol", protocol)
        return self.existing

    async def create_automation_run(self, payload: object) -> int:
        await self._call("create_automation_run", payload)
        return next(self.identities) if payload["robot"] == "R1" else 102

    async def create_incoming_email(self, payload: object) -> int:
        await self._call("create_incoming_email", payload)
        return 201

    async def create_email_attachment(self, payload: object) -> int:
        await self._call("create_email_attachment", payload)
        return 301

    async def create_service_request(self, payload: object) -> int:
        await self._call("create_service_request", payload)
        return 401

    async def upsert_establishment(self, payload: object) -> int:
        await self._call("upsert_establishment", payload)
        return 501

    async def append_execution_log(self, payload: object) -> int:
        await self._call("append_execution_log", payload)
        return 1

    async def update_automation_run(self, identifier: int, payload: object) -> None:
        await self._call("update_automation_run", (identifier, payload))

    async def update_incoming_email(self, identifier: int, payload: object) -> None:
        await self._call("update_incoming_email", (identifier, payload))

    async def update_email_attachment(self, identifier: int, payload: object) -> None:
        await self._call("update_email_attachment", (identifier, payload))

    async def update_service_request(self, identifier: int, payload: object) -> None:
        await self._call("update_service_request", (identifier, payload))

    async def update_establishment(self, identifier: int, payload: object) -> None:
        await self._call("update_establishment", (identifier, payload))


def _case_002():
    return get_scenario("caso_002_erro_download_r2", load_scenarios())


def _case_003():
    return get_scenario("caso_003_erro_upload_r1", load_scenarios())


def test_generic_executor_materializes_r2_download_failure_through_repository_only() -> None:
    repository = _Repository()

    result = asyncio.run(execute_ops_scenario(repository, _case_002()))

    assert result.created is True
    assert [name for name, _ in repository.calls].count("create_incoming_email") == 1
    assert [name for name, _ in repository.calls].count("create_email_attachment") == 1
    assert [name for name, _ in repository.calls].count("create_service_request") == 1
    assert [name for name, _ in repository.calls].count("upsert_establishment") == 1
    logs = [payload for name, payload in repository.calls if name == "append_execution_log"]
    assert len(logs) == 15
    assert [log["status"] for log in logs[-2:]] == ["ERROR", "ERROR"]
    assert all(log["robot"] == "R2" for log in logs[-5:])
    request_updates = [entry[1][1] for entry in repository.calls if entry[0] == "update_service_request"]
    assert request_updates[-1]["status"] == "FAILED"
    assert request_updates[-1]["failure_reason"] == "Falha no download do arquivo de resultado pelo R2."
    assert request_updates[-1]["completed_at"] is None
    establishment_updates = [entry[1][1] for entry in repository.calls if entry[0] == "update_establishment"]
    assert establishment_updates[-1]["download_status"] == "ERROR"
    assert establishment_updates[-1]["processing_status"] == "ERROR"
    assert establishment_updates[-1]["return_email_at"] is None


def test_executor_skips_before_any_creation_when_protocol_exists() -> None:
    repository = _Repository(existing=SimpleNamespace(request_id=999))

    result = asyncio.run(execute_ops_scenario(repository, _case_002()))

    assert result.created is False
    assert repository.calls == [("get_service_request_by_protocol", "POC-OPS-0002")]


def test_executor_finalizes_failed_r1_without_creating_r2() -> None:
    repository = _Repository()

    result = asyncio.run(execute_ops_scenario(repository, _case_003()))

    assert result.created is True
    assert result.r2_run_id is None
    assert [name for name, _ in repository.calls].count("create_automation_run") == 1
    assert [name for name, _ in repository.calls].count("append_execution_log") == 11
    request_updates = [entry[1][1] for entry in repository.calls if entry[0] == "update_service_request"]
    assert request_updates[-1]["status"] == "FAILED"
    establishment_updates = [entry[1][1] for entry in repository.calls if entry[0] == "update_establishment"]
    assert establishment_updates[-1]["processing_status"] == "ERROR"
    assert establishment_updates[-1]["upload_status"] == "ERROR"
    assert establishment_updates[-1]["download_status"] == "NOT_AVAILABLE"


def test_unexpected_repository_failure_propagates_for_outer_transaction_rollback() -> None:
    repository = _Repository(fail_on="create_email_attachment")

    with pytest.raises(RuntimeError, match="synthetic executor failure"):
        asyncio.run(execute_ops_scenario(repository, _case_002()))
