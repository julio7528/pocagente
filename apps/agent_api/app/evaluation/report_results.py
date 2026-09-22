"""Frozen, secret-safe Phase 11.5 report contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from apps.agent_api.app.agents.human_escalation import HumanEscalationState
from apps.agent_api.app.agents.router import RouterRoute

from .challenge_results import ChallengeExecutionMode, ChallengeScenarioStatus
from .metrics import MetricOutcome, MetricResult
from .rag_results import EvaluationCaseStatus, EvaluationExecutionMode


class OverallEvaluationOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCOMPLETE_NOT_MEASURABLE = "INCOMPLETE_NOT_MEASURABLE"


class ReportMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_label: Literal["phase11-local-evidence"] = "phase11-local-evidence"


class StatusCount(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = Field(min_length=1)
    count: int = Field(ge=0)


class ClassCount(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_class: str = Field(min_length=1)
    count: int = Field(ge=0)


class RAGCaseEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    case_class: str = Field(min_length=1)
    status: EvaluationCaseStatus
    reason: str | None = None
    expected_source_found: bool | None = None
    retrieval_status: str | None = None
    provenance_status: str | None = None
    grounding_status: str | None = None
    semantic_status: str | None = None
    security_blocked: bool | None = None
    audit_observed: bool | None = None
    redaction_status: str | None = None
    evaluated_claim_count: int = Field(ge=0)
    unsupported_claim_count: int = Field(ge=0)
    unsupported_fact_status: str
    insufficient_evidence_status: str


class ChallengeCaseEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: str = Field(min_length=1)
    status: ChallengeScenarioStatus
    reason: str | None = None
    expected_route: RouterRoute | None = None
    observed_route: RouterRoute | None = None
    authorization_applicable: bool
    authorization_respected: bool | None
    expected_tools_satisfied: bool
    unexpected_tools_absent: bool
    forbidden_capabilities_respected: bool
    security_blocked: bool | None = None
    human_states: tuple[HumanEscalationState, ...] = ()


class Phase11EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    report_schema_version: Literal["1.0"] = "1.0"
    metadata: ReportMetadata
    rag_dataset_name: str = Field(min_length=1)
    rag_dataset_version: str = Field(min_length=1)
    challenge_suite_name: str = Field(min_length=1)
    challenge_suite_version: str = Field(min_length=1)
    rag_runner_version: str = Field(min_length=1)
    challenge_runner_version: str = Field(min_length=1)
    rag_execution_mode: EvaluationExecutionMode
    challenge_execution_mode: ChallengeExecutionMode
    rag_case_count: int = Field(ge=0)
    challenge_scenario_count: int = Field(ge=0)
    rag_status_counts: tuple[StatusCount, ...]
    rag_class_counts: tuple[ClassCount, ...]
    challenge_status_counts: tuple[StatusCount, ...]
    metrics: tuple[MetricResult, ...]
    rag_cases: tuple[RAGCaseEvidence, ...]
    challenge_cases: tuple[ChallengeCaseEvidence, ...]
    overall_outcome: OverallEvaluationOutcome
    overall_reason: str = Field(min_length=1)
