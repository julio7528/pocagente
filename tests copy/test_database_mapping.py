"""Tests for centralized database result mapping module."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from apps.agent_api.app.database.mapping import (
    map_automation_run,
    map_establishment,
    map_execution_failure_evidence,
    map_execution_log,
    map_protocol_status_facts,
    map_rag_document,
    map_rag_source,
    map_search_candidate,
    map_security_event,
    map_service_request,
)
from apps.agent_api.app.rag.models import (
    PersistedChunk,
    RetrievedChunk,
    SearchCandidate,
)


# --- Positive Cases ---


def test_map_rag_source_positive() -> None:
    now = datetime.now(timezone.utc)
    source_id = uuid4()
    row = {
        "source_id": source_id,
        "name": "Manual Getnet",
        "source_type": "INTERNAL_DOCUMENT",
        "origin": "INTERNAL",
        "reference": "DOC-MANUAL-01",
        "domain": "operational",
        "status": "ACTIVE",
        "priority": 1,
        "created_at": now,
        "updated_at": now,
    }
    result = map_rag_source(row)
    assert result.source_id == source_id
    assert result.name == "Manual Getnet"
    assert result.priority == 1


def test_map_rag_document_positive() -> None:
    now = datetime.now(timezone.utc)
    doc_id = uuid4()
    source_id = uuid4()
    row = {
        "document_id": doc_id,
        "source_id": source_id,
        "document_key": "pdd-reconciliation",
        "title": "PDD Conciliacao",
        "document_type": "PDD",
        "content_checksum": "abcdef" * 10 + "1234",
        "status": "ACTIVE",
        "last_ingested_at": now,
        "created_at": now,
        "updated_at": now,
    }
    result = map_rag_document(row)
    assert result.document_id == doc_id
    assert result.title == "PDD Conciliacao"


def test_map_lexical_candidate_positive() -> None:
    now = datetime.now(timezone.utc)
    doc_id = uuid4()
    source_id = uuid4()
    row = {
        "chunk_id": 101,
        "document_id": doc_id,
        "content": "Fluxo de cancelamento de maquininha",
        "chunk_order": 0,
        "section": "Secao 2.1",
        "content_type": "BUSINESS_RULE",
        "metadata": {"tags": ["cancelamento", "pos"]},
        "created_at": now,
        "source_id": source_id,
        "source_name": "Manual POS",
        "source_type": "INTERNAL_DOCUMENT",
        "origin": "INTERNAL",
        "source_reference": "POS-001",
        "domain": "pos",
        "priority": 2,
        "document_key": "pos-doc-01",
        "title": "Manual Operacional POS",
        "document_type": "PDD",
        "content_checksum": "1" * 64,
        "last_ingested_at": now,
        "retrieval_channel": "lexical",
        "channel_rank": 1,
        "channel_score": 0.92,
    }
    result = map_search_candidate(row)
    assert isinstance(result, SearchCandidate)
    assert isinstance(result.chunk, PersistedChunk)
    assert not isinstance(result, RetrievedChunk)
    assert result.chunk.chunk_id == 101
    assert result.chunk.content_type == "BUSINESS_RULE"
    assert result.provenance.source_id == source_id
    assert result.provenance.document_key == "pos-doc-01"
    assert result.retrieval_channel == "lexical"
    assert result.channel_rank == 1
    assert result.channel_score == 0.92
    assert not hasattr(result, "matched_channels")
    assert not hasattr(result, "score")
    assert not hasattr(result, "rank")
    assert not hasattr(result.chunk, "matched_channels")
    assert not hasattr(result.chunk, "score")
    assert not hasattr(result.chunk, "rank")


def test_map_semantic_candidate_positive() -> None:
    now = datetime.now(timezone.utc)
    doc_id = uuid4()
    source_id = uuid4()
    row = {
        "chunk_id": 202,
        "document_id": doc_id,
        "content": "Algoritmo de reconciliacao de transacoes",
        "chunk_order": 1,
        "section": "Secao 3",
        "content_type": "CODE",
        "metadata": {},
        "created_at": now,
        "source_id": source_id,
        "source_name": "Manual DEV",
        "source_type": "INTERNAL_DOCUMENT",
        "origin": "INTERNAL",
        "source_reference": "DEV-001",
        "domain": "dev",
        "priority": 0,
        "document_key": "dev-doc-01",
        "title": "Especificacao Tecnica",
        "document_type": "SDD",
        "content_checksum": None,
        "last_ingested_at": None,
        "retrieval_channel": "semantic",
        "channel_rank": 2,
        "channel_score": 0.15,
    }
    result = map_search_candidate(row)
    assert isinstance(result, SearchCandidate)
    assert isinstance(result.chunk, PersistedChunk)
    assert not isinstance(result, RetrievedChunk)
    assert result.chunk.chunk_id == 202
    assert result.provenance.document_type == "SDD"
    assert result.retrieval_channel == "semantic"
    assert result.channel_rank == 2
    assert result.channel_score == 0.15
    assert not hasattr(result, "matched_channels")
    assert not hasattr(result, "score")
    assert not hasattr(result, "rank")
    assert not hasattr(result.chunk, "matched_channels")
    assert not hasattr(result.chunk, "score")
    assert not hasattr(result.chunk, "rank")


def test_map_automation_run_positive() -> None:
    now = datetime.now(timezone.utc)
    row = {
        "run_id": 5,
        "robot": "R1",
        "started_at": now,
        "finished_at": now,
        "status": "SUCCESS",
        "result_message": "Completed 10 items",
        "created_at": now,
    }
    result = map_automation_run(row)
    assert result.run_id == 5
    assert result.robot == "R1"
    assert result.status == "SUCCESS"


def test_map_service_request_positive() -> None:
    now = datetime.now(timezone.utc)
    row = {
        "request_id": 12,
        "protocol_number": "P202609001",
        "email_id": 4,
        "r1_run_id": 5,
        "created_at": now,
        "updated_at": now,
        "status": "COMPLETED",
        "result": "OK",
        "failure_reason": None,
        "completed_at": now,
        "return_email_at": now,
    }
    result = map_service_request(row)
    assert result.protocol_number == "P202609001"
    assert result.status == "COMPLETED"


def test_map_establishment_positive() -> None:
    now = datetime.now(timezone.utc)
    row = {
        "establishment_id": 7,
        "request_id": 12,
        "attachment_id": 8,
        "establishment_number": "00987654",
        "generated_file_name": "retorno_00987654.txt",
        "processing_status": "COMPLETED",
        "upload_status": "SUCCESS",
        "upload_at": now,
        "download_status": "DOWNLOADED",
        "download_at": now,
        "return_email_at": now,
        "result_message": "Processed without error",
        "updated_at": now,
    }
    result = map_establishment(row)
    assert result.establishment_number == "00987654"
    assert result.upload_status == "SUCCESS"


def test_map_execution_log_positive() -> None:
    now = datetime.now(timezone.utc)
    row = {
        "log_id": 88,
        "run_id": 5,
        "logged_at": now,
        "robot": "R1",
        "event": "ATTACHMENT_DOWNLOADED",
        "status": "SUCCESS",
        "message": "Downloaded 1 file",
        "email_id": 4,
        "attachment_id": 8,
        "request_id": 12,
        "establishment_id": None,
        "created_at": now,
    }
    result = map_execution_log(row)
    assert result.log_id == 88
    assert result.event == "ATTACHMENT_DOWNLOADED"


def test_map_protocol_status_facts_positive() -> None:
    now = datetime.now(timezone.utc)
    row = {
        "request_id": 12,
        "protocol_number": "P202609001",
        "email_id": 4,
        "r1_run_id": 5,
        "created_at": now,
        "updated_at": now,
        "status": "PROCESSING",
        "result": None,
        "failure_reason": None,
        "completed_at": None,
        "return_email_at": None,
        "establishments": [
            {
                "establishment_id": 7,
                "request_id": 12,
                "attachment_id": 8,
                "establishment_number": "00987654",
                "generated_file_name": "retorno_00987654.txt",
                "processing_status": "UPLOADING",
                "upload_status": "PENDING",
                "upload_at": None,
                "download_status": "NOT_AVAILABLE",
                "download_at": None,
                "return_email_at": None,
                "result_message": None,
                "updated_at": now,
            }
        ],
        "execution_timeline": [
            {
                "log_id": 88,
                "run_id": 5,
                "logged_at": now,
                "robot": "R1",
                "event": "ATTACHMENT_DOWNLOADED",
                "status": "SUCCESS",
                "message": "Downloaded 1 file",
                "email_id": 4,
                "attachment_id": 8,
                "request_id": 12,
                "establishment_id": None,
                "created_at": now,
            }
        ],
    }
    result = map_protocol_status_facts(row)
    assert result.request_id == 12
    assert len(result.establishments) == 1
    assert result.establishments[0].establishment_number == "00987654"
    assert len(result.execution_timeline) == 1
    assert result.execution_timeline[0].log_id == 88


def test_map_execution_failure_evidence_with_previous_success() -> None:
    now = datetime.now(timezone.utc)
    row = {
        "request_id": 12,
        "protocol_number": "P202609001",
        "request_status": "FAILED",
        "failure_reason": "Upload timeout",
        "run_id": 5,
        "robot": "R1",
        "started_at": now,
        "finished_at": now,
        "run_status": "ERROR",
        "run_result_message": "Run aborted on timeout",
        "log_id": 90,
        "logged_at": now,
        "event": "UPLOAD_TIMEOUT",
        "event_status": "ERROR",
        "event_message": "Socket timed out after 30s",
        "email_id": 4,
        "attachment_id": 8,
        "establishment_id": 7,
        "last_successful_evidence": {
            "log_id": 88,
            "run_id": 5,
            "logged_at": now,
            "robot": "R1",
            "event": "FILE_VALIDATED",
            "status": "SUCCESS",
            "message": "File valid",
            "email_id": 4,
            "attachment_id": 8,
            "request_id": 12,
            "establishment_id": None,
            "created_at": now,
        },
    }
    result = map_execution_failure_evidence(row)
    assert result.log_id == 90
    assert result.event_status == "ERROR"
    assert result.last_successful_evidence is not None
    assert result.last_successful_evidence.log_id == 88
    assert result.last_successful_evidence.status == "SUCCESS"


def test_map_execution_failure_evidence_without_previous_success() -> None:
    now = datetime.now(timezone.utc)
    row = {
        "request_id": 12,
        "protocol_number": "P202609001",
        "request_status": "FAILED",
        "failure_reason": "Immediate crash",
        "run_id": 5,
        "robot": "R1",
        "started_at": now,
        "finished_at": now,
        "run_status": "ERROR",
        "run_result_message": "Early crash",
        "log_id": 90,
        "logged_at": now,
        "event": "CRASH",
        "event_status": "EXCEPTION",
        "event_message": "Unhandled exception",
        "email_id": 4,
        "attachment_id": 8,
        "establishment_id": None,
        "last_successful_evidence": None,
    }
    result = map_execution_failure_evidence(row)
    assert result.last_successful_evidence is None


def test_map_security_event_positive() -> None:
    now = datetime.now(timezone.utc)
    row = {
        "event_id": 1001,
        "occurred_at": now,
        "event_type": "DATABASE_ACCESS_REQUEST",
        "source_component": "api_gateway",
        "user_identifier": "usr_99",
        "request_reference": "REQ-777",
        "resource_category": "DATABASE_CREDENTIAL",
        "sanitized_content": "blocked attempt to query pg_catalog",
        "action_taken": "BLOCK",
        "result": "SUCCESS",
        "review_status": "UNREVIEWED",
        "reviewed_at": None,
        "review_note": None,
        "created_at": now,
    }
    result = map_security_event(row)
    assert result.event_id == 1001
    assert result.event_type == "DATABASE_ACCESS_REQUEST"
    assert result.action_taken == "BLOCK"


# --- Negative Cases ---


def test_map_rag_source_missing_required_field() -> None:
    now = datetime.now(timezone.utc)
    row = {
        "source_id": uuid4(),
        # missing "name"
        "source_type": "INTERNAL_DOCUMENT",
        "origin": "INTERNAL",
        "reference": "DOC-001",
        "status": "ACTIVE",
        "priority": 1,
        "created_at": now,
        "updated_at": now,
    }
    with pytest.raises(ValidationError):
        map_rag_source(row)


def test_map_rag_source_unexpected_top_level_field() -> None:
    now = datetime.now(timezone.utc)
    row = {
        "source_id": uuid4(),
        "name": "Manual",
        "source_type": "INTERNAL_DOCUMENT",
        "origin": "INTERNAL",
        "reference": "DOC-001",
        "status": "ACTIVE",
        "priority": 1,
        "created_at": now,
        "updated_at": now,
        "unknown_column": 123,
    }
    with pytest.raises(ValidationError):
        map_rag_source(row)


def test_map_search_candidate_malformed_uuid() -> None:
    now = datetime.now(timezone.utc)
    row = {
        "chunk_id": 101,
        "document_id": "not-a-valid-uuid",
        "content": "Content",
        "chunk_order": 0,
        "content_type": "TEXT",
        "metadata": {},
        "created_at": now,
        "source_id": uuid4(),
        "source_name": "Manual",
        "source_type": "INTERNAL_DOCUMENT",
        "origin": "INTERNAL",
        "source_reference": "POS-001",
        "domain": "pos",
        "priority": 2,
        "document_key": "pos-doc-01",
        "title": "Title",
        "document_type": "PDD",
        "content_checksum": None,
        "last_ingested_at": None,
        "retrieval_channel": "lexical",
        "channel_rank": 1,
        "channel_score": 0.92,
    }
    with pytest.raises(ValidationError):
        map_search_candidate(row)


def test_map_search_candidate_invalid_retrieval_channel() -> None:
    now = datetime.now(timezone.utc)
    doc_id = uuid4()
    src_id = uuid4()
    row = {
        "chunk_id": 101,
        "document_id": doc_id,
        "content": "Content",
        "chunk_order": 0,
        "content_type": "TEXT",
        "metadata": {},
        "created_at": now,
        "source_id": src_id,
        "source_name": "Manual",
        "source_type": "INTERNAL_DOCUMENT",
        "origin": "INTERNAL",
        "source_reference": "POS-001",
        "domain": "pos",
        "priority": 2,
        "document_key": "pos-doc-01",
        "title": "Title",
        "document_type": "PDD",
        "content_checksum": None,
        "last_ingested_at": None,
        "retrieval_channel": "unsupported_channel",
        "channel_rank": 1,
        "channel_score": 0.92,
    }
    with pytest.raises(ValidationError):
        map_search_candidate(row)


def test_map_search_candidate_invalid_rank() -> None:
    now = datetime.now(timezone.utc)
    doc_id = uuid4()
    src_id = uuid4()
    row = {
        "chunk_id": 101,
        "document_id": doc_id,
        "content": "Content",
        "chunk_order": 0,
        "content_type": "TEXT",
        "metadata": {},
        "created_at": now,
        "source_id": src_id,
        "source_name": "Manual",
        "source_type": "INTERNAL_DOCUMENT",
        "origin": "INTERNAL",
        "source_reference": "POS-001",
        "domain": "pos",
        "priority": 2,
        "document_key": "pos-doc-01",
        "title": "Title",
        "document_type": "PDD",
        "content_checksum": None,
        "last_ingested_at": None,
        "retrieval_channel": "lexical",
        "channel_rank": 0,  # invalid rank < 1
        "channel_score": 0.92,
    }
    with pytest.raises(ValidationError):
        map_search_candidate(row)


def test_map_search_candidate_unexpected_field() -> None:
    now = datetime.now(timezone.utc)
    doc_id = uuid4()
    src_id = uuid4()
    row = {
        "chunk_id": 101,
        "document_id": doc_id,
        "content": "Content",
        "chunk_order": 0,
        "content_type": "TEXT",
        "metadata": {},
        "created_at": now,
        "source_id": src_id,
        "source_name": "Manual",
        "source_type": "INTERNAL_DOCUMENT",
        "origin": "INTERNAL",
        "source_reference": "POS-001",
        "domain": "pos",
        "priority": 2,
        "document_key": "pos-doc-01",
        "title": "Title",
        "document_type": "PDD",
        "content_checksum": None,
        "last_ingested_at": None,
        "retrieval_channel": "lexical",
        "channel_rank": 1,
        "channel_score": 0.92,
        "unexpected_extra": "rejected",
    }
    with pytest.raises(ValidationError):
        map_search_candidate(row)


def test_map_protocol_status_facts_malformed_nested_establishment() -> None:
    now = datetime.now(timezone.utc)
    row = {
        "request_id": 12,
        "protocol_number": "P202609001",
        "email_id": 4,
        "r1_run_id": 5,
        "created_at": now,
        "updated_at": now,
        "status": "PROCESSING",
        "establishments": [
            {
                "establishment_id": "not_an_int",  # invalid type
                "request_id": 12,
            }
        ],
        "execution_timeline": [],
    }
    with pytest.raises(ValidationError):
        map_protocol_status_facts(row)


def test_map_protocol_status_facts_malformed_nested_execution_event() -> None:
    now = datetime.now(timezone.utc)
    row = {
        "request_id": 12,
        "protocol_number": "P202609001",
        "email_id": 4,
        "r1_run_id": 5,
        "created_at": now,
        "updated_at": now,
        "status": "PROCESSING",
        "establishments": [],
        "execution_timeline": [
            {
                "log_id": 1,
                # missing all required fields
            }
        ],
    }
    with pytest.raises(ValidationError):
        map_protocol_status_facts(row)


def test_map_automation_run_invalid_datetime() -> None:
    row = {
        "run_id": 5,
        "robot": "R1",
        "started_at": "not-a-datetime",
        "status": "SUCCESS",
        "created_at": "not-a-datetime",
    }
    with pytest.raises(ValidationError):
        map_automation_run(row)
