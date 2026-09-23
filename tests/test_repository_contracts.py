"""Tests for async repository contracts and domain ownership boundaries."""

import inspect

import pytest

from apps.agent_api.app.database.repositories import contracts as contracts_module
from apps.agent_api.app.database.repositories.contracts import (
    AUDIT_OWNED_TABLES,
    OPS_OWNED_TABLES,
    RAG_OWNED_TABLES,
    AuditRepositoryContract,
    OperationalRepositoryContract,
    RAGRepositoryContract,
)


RAG_METHODS = {
    "get_source_by_id",
    "get_source_by_reference",
    "register_source",
    "get_document_by_id",
    "get_document_by_key",
    "document_checksum_changed",
    "save_document",
    "replace_document_chunks",
    "start_ingestion_run",
    "finish_ingestion_run",
    "search_lexical_candidates",
    "search_semantic_candidates",
}
OPERATIONAL_METHODS = {
    "create_automation_run",
    "update_automation_run",
    "get_automation_run",
    "create_incoming_email",
    "update_incoming_email",
    "create_email_attachment",
    "update_email_attachment",
    "create_service_request",
    "update_service_request",
    "get_service_request_by_protocol",
    "get_incoming_email",
    "list_email_attachments",
    "list_automation_runs_for_request",
    "upsert_establishment",
    "update_establishment",
    "list_establishments_for_request",
    "append_execution_log",
    "list_execution_timeline_for_run",
    "list_execution_timeline_for_request",
    "get_protocol_status_facts",
    "get_execution_failure_facts",
    "list_recent_service_requests",
    "list_recent_protocols_by_execution",
    "query_operational_analytics",
}
AUDIT_METHODS = {
    "write_sanitized_security_event",
    "get_security_event",
    "list_security_events_by_request_reference",
    "list_unreviewed_security_events",
    "update_security_event_review",
}


@pytest.mark.parametrize(
    ("contract", "expected_methods"),
    [
        (RAGRepositoryContract, RAG_METHODS),
        (OperationalRepositoryContract, OPERATIONAL_METHODS),
        (AuditRepositoryContract, AUDIT_METHODS),
    ],
)
def test_contract_methods_exist_and_are_async(
    contract: type,
    expected_methods: set[str],
) -> None:
    declared_methods = {
        name
        for name, value in contract.__dict__.items()
        if not name.startswith("__") and inspect.isfunction(value)
    }

    assert declared_methods == expected_methods
    assert all(inspect.iscoroutinefunction(getattr(contract, name)) for name in expected_methods)


@pytest.mark.parametrize(
    "contract",
    [RAGRepositoryContract, OperationalRepositoryContract, AuditRepositoryContract],
)
def test_protocol_contracts_have_no_runtime_implementation(contract: type) -> None:
    with pytest.raises(TypeError):
        contract()


def test_repository_table_ownership_is_exact_and_disjoint() -> None:
    assert RAG_OWNED_TABLES == (
        "rag.sources",
        "rag.documents",
        "rag.chunks",
        "rag.ingestion_runs",
    )
    assert OPS_OWNED_TABLES == (
        "ops.automation_runs",
        "ops.incoming_emails",
        "ops.email_attachments",
        "ops.service_requests",
        "ops.establishments",
        "ops.execution_log",
    )
    assert AUDIT_OWNED_TABLES == ("audit.security_events",)

    all_tables = RAG_OWNED_TABLES + OPS_OWNED_TABLES + AUDIT_OWNED_TABLES
    assert len(all_tables) == 11
    assert len(set(all_tables)) == 11


def test_contracts_expose_no_generic_database_interface() -> None:
    all_methods = RAG_METHODS | OPERATIONAL_METHODS | AUDIT_METHODS

    assert "execute_sql" not in all_methods
    assert "query" not in all_methods
    assert "execute" not in all_methods


def test_rag_retrieval_returns_search_candidates() -> None:
    assert (
        RAGRepositoryContract.search_lexical_candidates.__annotations__["return"]
        == "Sequence[SearchCandidate]"
    )
    assert (
        RAGRepositoryContract.search_semantic_candidates.__annotations__["return"]
        == "Sequence[SearchCandidate]"
    )


def test_repository_contracts_expose_typed_read_models() -> None:
    assert (
        RAGRepositoryContract.get_source_by_id.__annotations__["return"]
        == "RAGSourceRecord | None"
    )
    assert (
        RAGRepositoryContract.get_document_by_id.__annotations__["return"]
        == "RAGDocumentRecord | None"
    )
    assert (
        OperationalRepositoryContract.get_automation_run.__annotations__["return"]
        == "AutomationRunRecord | None"
    )
    assert (
        OperationalRepositoryContract.get_service_request_by_protocol.__annotations__["return"]
        == "ServiceRequestRecord | None"
    )
    assert (
        OperationalRepositoryContract.list_establishments_for_request.__annotations__["return"]
        == "Sequence[EstablishmentRecord]"
    )
    assert (
        OperationalRepositoryContract.get_protocol_status_facts.__annotations__["return"]
        == "Sequence[ProtocolStatusFacts]"
    )
    assert (
        OperationalRepositoryContract.get_execution_failure_facts.__annotations__["return"]
        == "Sequence[ExecutionFailureEvidence]"
    )
    assert (
        AuditRepositoryContract.get_security_event.__annotations__["return"]
        == "SecurityEventRecord | None"
    )
    assert (
        AuditRepositoryContract.list_security_events_by_request_reference.__annotations__["return"]
        == "Sequence[SecurityEventRecord]"
    )


def test_repository_contracts_preserve_write_payload_contracts() -> None:
    assert (
        RAGRepositoryContract.register_source.__annotations__["source"]
        == "RepositoryRecord"
    )
    assert (
        RAGRepositoryContract.save_document.__annotations__["document"]
        == "RepositoryRecord"
    )
    assert (
        OperationalRepositoryContract.create_automation_run.__annotations__["run"]
        == "RepositoryRecord"
    )
    assert (
        OperationalRepositoryContract.create_service_request.__annotations__["request"]
        == "RepositoryRecord"
    )
    assert (
        AuditRepositoryContract.write_sanitized_security_event.__annotations__["event"]
        == "RepositoryRecord"
    )


def test_contract_module_has_no_infrastructure_or_framework_coupling() -> None:
    source = inspect.getsource(contracts_module)

    for forbidden in (
        "AsyncConnectionPool",
        "PostgresDatabase",
        "SQLAlchemy",
        "Alembic",
        "FastAPI",
        "LangGraph",
        "MCP",
    ):
        assert forbidden not in source


def test_contract_import_creates_no_repository_instance() -> None:
    contract_types = (
        RAGRepositoryContract,
        OperationalRepositoryContract,
        AuditRepositoryContract,
    )
    instances = [
        value
        for value in vars(contracts_module).values()
        if type(value) in contract_types
    ]

    assert instances == []
