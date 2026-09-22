"""Typed, secret-safe observations produced by the Phase 11.3 RAG boundary."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from apps.agent_api.app.agents.router import RouterRoute
from apps.agent_api.app.rag.grounding.context_builder import EvidenceStatus
from apps.agent_api.app.security.models import SecurityAction, SecurityEventType

from .adapters import RAGEvaluationClass


class EvaluationExecutionMode(StrEnum):
    RUNNER_CONTRACT = "RUNNER_CONTRACT"
    LOCAL_RAG = "LOCAL_RAG"


class EvaluationCaseStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_MEASURABLE = "NOT_MEASURABLE"


class RetrievalDimensionStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_MEASURABLE = "NOT_MEASURABLE"


class RedactionStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ClaimSupportStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RedactionObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: RedactionStatus
    sanitization_invoked: bool
    supplied_secret_count: int = Field(ge=0)


class RetrievedProvenanceObservation(BaseModel):
    """Exact stable provenance identity observed for one final result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int = Field(ge=1)
    document_key: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)
    section: str | None = None
    expected_source_match: bool


class EvaluatedClaimObservation(BaseModel):
    """One structured claim evaluated against exact source/section evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(min_length=1)
    expected_value: str = Field(min_length=1)
    status: ClaimSupportStatus
    supporting_evidence: tuple[RetrievedProvenanceObservation, ...] = ()


class ClaimSupportObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    applicable: bool
    evaluated_claim_count: int = Field(ge=0)
    unsupported_claim_count: int = Field(ge=0)
    claims: tuple[EvaluatedClaimObservation, ...] = ()


class RetrievalObservation(BaseModel):
    """Structural retrieval evidence without chunk content or user text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    result_count: int = Field(ge=0)
    final_rank: tuple[int, ...] = ()
    results: tuple[RetrievedProvenanceObservation, ...] = ()
    expected_source_found: bool
    evidence_status: EvidenceStatus
    evidence_reason: str | None = None
    evidence_count: int = Field(ge=0)
    citation_count: int = Field(ge=0)
    retrieval_status: RetrievalDimensionStatus
    provenance_status: RetrievalDimensionStatus
    grounding_status: RetrievalDimensionStatus
    semantic_status: RetrievalDimensionStatus

    @property
    def provenance_ids(self) -> tuple[str, ...]:
        return tuple(item.document_key for item in self.results)

    @property
    def source_matches(self) -> tuple[bool, ...]:
        return tuple(item.expected_source_match for item in self.results)


class SecurityObservation(BaseModel):
    """Typed security-terminal evidence; protected request content is excluded."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    blocked: bool
    router_route: RouterRoute
    event_types: tuple[SecurityEventType, ...] = ()
    audit_actions: tuple[SecurityAction, ...] = ()
    forbidden_call_counts: dict[str, int] = Field(default_factory=dict)
    redaction: RedactionObservation

    @property
    def redaction_verified(self) -> bool:
        return self.redaction.status is RedactionStatus.PASS


class RAGCaseResult(BaseModel):
    """One immutable case result for the Phase 11.3 boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    runner_version: Literal["1.0"] = "1.0"
    execution_mode: EvaluationExecutionMode
    case_class: RAGEvaluationClass
    status: EvaluationCaseStatus
    reason: str | None = None
    retrieval: RetrievalObservation | None = None
    security: SecurityObservation | None = None
    claim_support: ClaimSupportObservation = ClaimSupportObservation(
        applicable=False,
        evaluated_claim_count=0,
        unsupported_claim_count=0,
    )
    unsupported_fact_status: RetrievalDimensionStatus = RetrievalDimensionStatus.NOT_MEASURABLE
    insufficient_evidence_status: RetrievalDimensionStatus = RetrievalDimensionStatus.NOT_MEASURABLE
