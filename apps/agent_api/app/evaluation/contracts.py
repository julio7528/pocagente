"""Strict immutable contracts for versioned evaluation definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, field_validator, model_validator


class EvaluationDatasetContractError(ValueError):
    """Controlled failure for invalid evaluation definitions or adapters."""


class RAGAuditExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    event_type: str = Field(min_length=1)
    action_taken: str = Field(min_length=1)


class EvaluationClaimExpectation(BaseModel):
    """Versioned structured material claim with exact evidence semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    claim_id: str = Field(pattern=r"^claim-[a-z0-9-]+$")
    claim_type: Literal["MATERIAL_FACT"]
    expected_value: str = Field(pattern=r"^[A-Z0-9_]+$")
    allowed_sources: tuple[str, ...] = Field(min_length=1)
    allowed_sections: tuple[str, ...] = Field(min_length=1)
    support_rule: Literal["EXACT_SOURCE_AND_SECTION"]


class RAGDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    final_top_k: StrictInt = Field(ge=1)
    expected_source_in_top_k: StrictBool
    require_provenance: StrictBool


class RAGAcceptance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_source_top_5_rate: StrictFloat = Field(ge=0.0, le=1.0)
    provenance_success_rate: StrictFloat = Field(ge=0.0, le=1.0)
    unsupported_fact_rate: StrictFloat = Field(ge=0.0, le=1.0)
    insufficient_evidence_cases_must_not_hallucinate: StrictBool
    security_violation_cases_must_block: StrictBool
    security_violation_cases_must_log_audit_event: StrictBool
    secrets_must_be_redacted_before_audit: StrictBool


class RAGEvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    id: str = Field(pattern=r"^rag-[0-9]{3}$")
    category: str = Field(min_length=1)
    question: str = Field(min_length=1)
    expected_sources: tuple[str, ...] = ()
    expected_evidence: tuple[str, ...] = ()
    expects_evidence: StrictBool
    expected_behavior: Literal[
        "answer",
        "compare_rule_to_observed_state",
        "security_violation_alert",
        "insufficient_evidence",
    ]
    expected_claim_type: str | None = None
    expected_conclusion: tuple[str, ...] = ()
    required_actions: tuple[str, ...] = ()
    must_not: tuple[str, ...] = ()
    expected_audit_event: RAGAuditExpectation | None = None
    claim_expectations: tuple[EvaluationClaimExpectation, ...] = ()
    supplied_secret_fragments: tuple[str, ...] = ()

    @model_validator(mode="after")
    def evidence_contract_is_unambiguous(self) -> RAGEvaluationCase:
        claim_ids = tuple(item.claim_id for item in self.claim_expectations)
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("Claim expectation IDs must be unique within a case")
        for claim in self.claim_expectations:
            if not set(claim.allowed_sources).issubset(self.expected_sources):
                raise ValueError("Claim evidence sources must be declared expected sources")
        if any("SYNTHETIC" not in fragment.upper() for fragment in self.supplied_secret_fragments):
            raise ValueError("Supplied-secret fixtures must be explicitly synthetic")
        return self


class RAGEvaluationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["1.0", "1.1"]
    dataset_name: str = Field(min_length=1)
    language: str = Field(min_length=1)
    description: str = Field(min_length=1)
    defaults: RAGDefaults
    acceptance: RAGAcceptance
    claim_support_applicability: Literal["explicit_claim_expectations_only"] | None = None
    cases: tuple[RAGEvaluationCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def case_ids_are_unique(self) -> RAGEvaluationDataset:
        ids = tuple(case.id for case in self.cases)
        if len(ids) != len(set(ids)):
            raise ValueError("RAG evaluation case IDs must be unique")
        if self.version == "1.0":
            if self.claim_support_applicability is not None:
                raise ValueError("RAG dataset v1.0 cannot declare claim-support policy")
            if any(case.claim_expectations or case.supplied_secret_fragments for case in self.cases):
                raise ValueError("RAG dataset v1.0 cannot declare v1.1 case evidence")
        else:
            if self.claim_support_applicability != "explicit_claim_expectations_only":
                raise ValueError("RAG dataset v1.1 requires explicit claim applicability")
            if not any(case.claim_expectations for case in self.cases):
                raise ValueError("RAG dataset v1.1 requires measurable claim expectations")
            if not any(case.expected_behavior == "insufficient_evidence" for case in self.cases):
                raise ValueError("RAG dataset v1.1 requires insufficient-evidence coverage")
            if not any(case.supplied_secret_fragments for case in self.cases):
                raise ValueError("RAG dataset v1.1 requires supplied-secret coverage")
        for case in self.cases:
            if case.expected_behavior == "insufficient_evidence":
                if case.expects_evidence or case.expected_sources or case.claim_expectations:
                    raise ValueError("Insufficient-evidence cases cannot declare answer evidence")
            if case.claim_expectations and case.expected_behavior not in {
                "answer", "compare_rule_to_observed_state"
            }:
                raise ValueError("Claim expectations apply only to evidence-backed cases")
            if case.supplied_secret_fragments and case.expected_behavior != "security_violation_alert":
                raise ValueError("Supplied-secret fixtures apply only to security cases")
        return self


class ChallengeTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    turn: int = Field(ge=1)
    user_message: str = Field(min_length=1)
    expected_route: Literal["customer_support_agent", "human_escalation_agent"]
    expected_agents: tuple[str, ...] = ()
    expected_tools: tuple[str, ...] = ()
    expected_behavior: tuple[str, ...] = ()
    forbidden_behavior: tuple[str, ...] = ()


class ChallengeScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    id: str = Field(pattern=r"^challenge-[0-9]{3}$")
    category: str = Field(min_length=1)
    message: str = Field(min_length=1)
    expected_route: Literal[
        "knowledge",
        "conditional_support",
        "support_with_knowledge",
        "customer_support",
        "cooperative_knowledge_and_support",
        "security_block",
        "customer_support_to_human_escalation",
    ]
    expected_agents: tuple[str, ...] = ()
    expected_capabilities: tuple[Literal[
        "approved_public_getnet_rag", "grounded_answer", "web_search", "freshness_check",
        "intent_disambiguation", "controlled_customer_data_lookup_if_required",
        "approved_public_getnet_support_rag", "troubleshooting", "controlled_support_tool_if_required",
        "controlled_support_if_device_specific", "controlled_support_if_transaction_specific",
        "controlled_operational_lookup", "authorization_check", "internal_process_rag",
        "evidence_comparison", "security_guardrail", "redaction", "security_audit",
        "web_search_if_rag_insufficient", "execution_diagnostics_lookup", "evidence_based_diagnosis",
        "human_escalation_offer", "user_confirmation_check", "minimum_context_handoff",
        "automation_suspension",
    ], ...] = ()
    forbidden_capabilities: tuple[Literal[
        "operational_customer_lookup", "public_web_search_for_private_account_facts",
        "public_web_search_for_private_device_state", "public_web_search_for_private_transaction_state",
        "rag_only", "public_web_search", "public_rag_as_status_source",
        "public_web_search_for_protocol_state", "rag_secret_search", "operational_secret_lookup",
        "public_web_search_for_private_failure_state", "automatic_unconfirmed_escalation",
        "automatic_ai_ticket_creation", "unsupported_root_cause_fabrication",
    ], ...] = ()
    expected_behavior: tuple[str, ...] = ()
    must_not: tuple[str, ...] = ()
    expected_tools: tuple[Literal["lookup_protocol_status", "inspect_execution_failure"], ...] = ()
    preconditions: tuple[str, ...] = ()
    tool_class: tuple[Literal[
        "public_rag", "public_web_search", "controlled_customer_support_if_customer_specific",
        "controlled_support_if_device_specific", "controlled_support_if_transaction_specific",
        "public_web_search_if_needed", "controlled_ops", "internal_rag", "security_audit",
        "human_escalation", "public_web_search_for_private_failure_state",
    ], ...] = ()
    expected_source_class: tuple[str, ...] = ()
    freshness_requirement: Literal[
        "stable_or_semi_stable", "required", "customer_current_state_if_specific",
        "current_operational_state", "not_applicable",
    ] | None = None
    rag_requirement: Literal["not_required"] | None = None
    security_expectation: Literal[
        "normal", "authorization_required_for_customer_data", "authorization_required_for_device_data",
        "authorization_required_for_transaction_data", "authorization_required", "block_redact_and_audit",
        "authorization_required_with_redaction",
    ] | None = None
    turns: tuple[ChallengeTurn, ...] = ()

    @model_validator(mode="after")
    def turns_are_ordered(self) -> ChallengeScenario:
        if self.turns and tuple(turn.turn for turn in self.turns) != tuple(range(1, len(self.turns) + 1)):
            raise ValueError("Challenge turns must be contiguous and ordered from one")
        return self


class ChallengeDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1)
    discovered_web_results_are_persistent_sources: StrictBool
    external_content_is_untrusted_evidence: StrictBool
    prompt_injection_from_sources_is_ignored: StrictBool
    exact_answer_text_required: StrictBool


class ChallengeEvaluationSuite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["1.0"]
    suite_name: str = Field(min_length=1)
    language: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    defaults: ChallengeDefaults
    acceptance: tuple[str, ...]
    scenarios: tuple[ChallengeScenario, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def scenario_ids_are_unique(self) -> ChallengeEvaluationSuite:
        ids = tuple(scenario.id for scenario in self.scenarios)
        if len(ids) != len(set(ids)):
            raise ValueError("Challenge scenario IDs must be unique")
        return self


class LoadedRAGDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    suite_type: Literal["RAG"] = "RAG"
    source_path: Path
    dataset: RAGEvaluationDataset

    @property
    def version(self) -> str:
        return self.dataset.version

    @property
    def entry_count(self) -> int:
        return len(self.dataset.cases)


class LoadedChallengeSuite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    suite_type: Literal["CHALLENGE"] = "CHALLENGE"
    source_path: Path
    suite: ChallengeEvaluationSuite

    @property
    def version(self) -> str:
        return self.suite.version

    @property
    def entry_count(self) -> int:
        return len(self.suite.scenarios)
