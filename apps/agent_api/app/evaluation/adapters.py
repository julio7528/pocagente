"""Versioned dataset-to-runtime expectation adapters; never runtime policy."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, StrictBool

from apps.agent_api.app.agents.human_escalation import HumanEscalationState
from apps.agent_api.app.agents.router import RouterCapability, RouterRoute, WebSearchPolicy
from apps.agent_api.app.security.models import SecurityAction, SecurityEventType

from .contracts import ChallengeScenario, EvaluationDatasetContractError, RAGAuditExpectation, RAGEvaluationCase


class RAGEvaluationClass(StrEnum):
    RETRIEVAL = "RETRIEVAL"
    RULE_VS_OBSERVED = "RULE_VS_OBSERVED"
    SECURITY = "SECURITY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


def classify_rag_case(case: RAGEvaluationCase) -> RAGEvaluationClass:
    """Classify only from the declared versioned behavior field."""

    mapping = {
        "answer": RAGEvaluationClass.RETRIEVAL,
        "compare_rule_to_observed_state": RAGEvaluationClass.RULE_VS_OBSERVED,
        "security_violation_alert": RAGEvaluationClass.SECURITY,
        "insufficient_evidence": RAGEvaluationClass.INSUFFICIENT_EVIDENCE,
    }
    try:
        return mapping[case.expected_behavior]
    except KeyError as error:
        raise EvaluationDatasetContractError("Unsupported RAG expected_behavior") from error


class ChallengeRouteConcept(StrEnum):
    KNOWLEDGE = "knowledge"
    CONDITIONAL_SUPPORT = "conditional_support"
    SUPPORT_WITH_KNOWLEDGE = "support_with_knowledge"
    CUSTOMER_SUPPORT = "customer_support"
    COOPERATIVE_KNOWLEDGE_AND_SUPPORT = "cooperative_knowledge_and_support"
    SECURITY_BLOCK = "security_block"
    CUSTOMER_SUPPORT_TO_HUMAN_ESCALATION = "customer_support_to_human_escalation"


class ChallengeRuntimeExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    route: RouterRoute | None
    capabilities: tuple[RouterCapability, ...] = ()
    web_search_policy: WebSearchPolicy = WebSearchPolicy.NONE
    terminal_state: HumanEscalationState | None = None
    requires_operator_acceptance: StrictBool = False
    automation_suspended: StrictBool = False
    turn_states: tuple[HumanEscalationState, ...] = ()


_CHALLENGE_ROUTE_MAP: dict[ChallengeRouteConcept, ChallengeRuntimeExpectation] = {
    ChallengeRouteConcept.KNOWLEDGE: ChallengeRuntimeExpectation(route=RouterRoute.KNOWLEDGE),
    ChallengeRouteConcept.CONDITIONAL_SUPPORT: ChallengeRuntimeExpectation(route=RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT),
    ChallengeRouteConcept.SUPPORT_WITH_KNOWLEDGE: ChallengeRuntimeExpectation(route=RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT),
    ChallengeRouteConcept.CUSTOMER_SUPPORT: ChallengeRuntimeExpectation(route=RouterRoute.CUSTOMER_SUPPORT),
    ChallengeRouteConcept.COOPERATIVE_KNOWLEDGE_AND_SUPPORT: ChallengeRuntimeExpectation(route=RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT),
    ChallengeRouteConcept.SECURITY_BLOCK: ChallengeRuntimeExpectation(route=RouterRoute.SECURITY_BLOCK),
    ChallengeRouteConcept.CUSTOMER_SUPPORT_TO_HUMAN_ESCALATION: ChallengeRuntimeExpectation(
        route=RouterRoute.CUSTOMER_SUPPORT,
        terminal_state=HumanEscalationState.WAITING_HUMAN,
        requires_operator_acceptance=True,
    ),
}


def adapt_challenge_route(concept: str) -> ChallengeRuntimeExpectation:
    try:
        return _CHALLENGE_ROUTE_MAP[ChallengeRouteConcept(concept)]
    except ValueError as error:
        raise EvaluationDatasetContractError(f"Unsupported challenge route concept: {concept}") from error


def adapt_challenge_scenario(scenario: ChallengeScenario) -> ChallengeRuntimeExpectation:
    """Adapt declared scenario semantics without inspecting its message text."""

    base = adapt_challenge_route(scenario.expected_route)
    _validate_declared_challenge_semantics(scenario)

    if scenario.expected_route == ChallengeRouteConcept.SECURITY_BLOCK.value:
        # RouterDecision's internal SECURITY_GUARDRAIL is the typed runtime
        # capability; the adapter never exposes the dataset's raw strings.
        return ChallengeRuntimeExpectation(
            route=RouterRoute.SECURITY_BLOCK,
            capabilities=(RouterCapability.SECURITY_GUARDRAIL,),
        )

    if scenario.expected_route == ChallengeRouteConcept.CUSTOMER_SUPPORT_TO_HUMAN_ESCALATION.value:
        return ChallengeRuntimeExpectation(
            route=RouterRoute.CUSTOMER_SUPPORT,
            capabilities=(RouterCapability.CUSTOMER_SUPPORT,),
            terminal_state=HumanEscalationState.WAITING_HUMAN,
            requires_operator_acceptance=True,
            automation_suspended=False,
            turn_states=(HumanEscalationState.WAITING_CONFIRMATION, HumanEscalationState.WAITING_HUMAN),
        )

    if scenario.freshness_requirement == "required":
        return ChallengeRuntimeExpectation(
            route=RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK,
            capabilities=(RouterCapability.KNOWLEDGE, RouterCapability.WEB_FALLBACK),
            web_search_policy=WebSearchPolicy.REQUIRED,
        )

    if "web_search_if_rag_insufficient" in scenario.expected_capabilities:
        return ChallengeRuntimeExpectation(
            route=RouterRoute.KNOWLEDGE,
            capabilities=(RouterCapability.KNOWLEDGE,),
            web_search_policy=WebSearchPolicy.FALLBACK_IF_RAG_INSUFFICIENT,
        )

    if scenario.expected_route == ChallengeRouteConcept.CUSTOMER_SUPPORT.value:
        capabilities = (RouterCapability.CUSTOMER_SUPPORT,)
        route = RouterRoute.CUSTOMER_SUPPORT
    elif scenario.expected_route in {
        ChallengeRouteConcept.CONDITIONAL_SUPPORT.value,
        ChallengeRouteConcept.SUPPORT_WITH_KNOWLEDGE.value,
        ChallengeRouteConcept.COOPERATIVE_KNOWLEDGE_AND_SUPPORT.value,
    }:
        capabilities = (RouterCapability.KNOWLEDGE, RouterCapability.CUSTOMER_SUPPORT)
        route = RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT
    else:
        capabilities = (RouterCapability.KNOWLEDGE,)
        route = base.route
    return ChallengeRuntimeExpectation(
        route=route,
        capabilities=capabilities,
        web_search_policy=WebSearchPolicy.NONE,
        terminal_state=base.terminal_state,
        requires_operator_acceptance=base.requires_operator_acceptance,
        automation_suspended=base.automation_suspended,
        turn_states=base.turn_states,
    )


def _validate_declared_challenge_semantics(scenario: ChallengeScenario) -> None:
    """Reject contradictions using only typed dataset fields."""

    caps = set(scenario.expected_capabilities)
    tools = set(scenario.tool_class)
    route = scenario.expected_route

    if "security_guardrail" in caps or "redaction" in caps or "security_audit" in caps:
        if route != ChallengeRouteConcept.SECURITY_BLOCK.value:
            raise EvaluationDatasetContractError("Security capabilities require security_block")
    if route == ChallengeRouteConcept.SECURITY_BLOCK.value:
        required = {"security_guardrail", "redaction", "security_audit"}
        if not required.issubset(caps) or tools != {"security_audit"} or scenario.security_expectation != "block_redact_and_audit":
            raise EvaluationDatasetContractError("security_block semantics are incomplete or inconsistent")

    if scenario.freshness_requirement == "required":
        required = {"web_search", "freshness_check"}
        if (
            route != ChallengeRouteConcept.KNOWLEDGE.value
            or not required.issubset(caps)
            or "public_web_search" not in tools
            or scenario.rag_requirement != "not_required"
        ):
            raise EvaluationDatasetContractError("required freshness semantics must require current public Web Search")
    if "web_search" in caps:
        if scenario.freshness_requirement != "required" or "public_web_search" not in tools:
            raise EvaluationDatasetContractError("web_search requires declared required freshness semantics")
    if scenario.rag_requirement == "not_required" and scenario.freshness_requirement != "required":
        raise EvaluationDatasetContractError("rag_requirement=not_required requires current public Web Search semantics")

    if "web_search_if_rag_insufficient" in caps:
        if (
            route != ChallengeRouteConcept.KNOWLEDGE.value
            or "approved_public_getnet_rag" not in caps
            or "public_rag" not in tools
            or "public_web_search_if_needed" not in tools
        ):
            raise EvaluationDatasetContractError("conditional fallback semantics are incomplete or inconsistent")

    if route == ChallengeRouteConcept.CUSTOMER_SUPPORT_TO_HUMAN_ESCALATION.value:
        required_caps = {
            "human_escalation_offer", "user_confirmation_check", "minimum_context_handoff", "automation_suspension",
        }
        if (
            len(scenario.turns) != 2
            or tuple(turn.expected_route for turn in scenario.turns) != ("customer_support_agent", "human_escalation_agent")
            or not required_caps.issubset(caps)
            or "human_escalation" not in tools
        ):
            raise EvaluationDatasetContractError("human handoff semantics require two ordered turns and handoff capabilities")


class SecurityRuntimeExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    acceptable_event_types: tuple[SecurityEventType, ...]
    action: SecurityAction
    requires_audit: bool = True


def adapt_security_expectation(expectation: RAGAuditExpectation) -> SecurityRuntimeExpectation:
    if expectation.action_taken != "BLOCKED_AND_LOGGED":
        raise EvaluationDatasetContractError("Unsupported historical audit action expectation")
    if expectation.event_type == "CREDENTIAL_REQUEST":
        event_types = (SecurityEventType.CREDENTIAL_REQUEST,)
    elif expectation.event_type == "SENSITIVE_ACCESS_REQUEST":
        event_types = (
            SecurityEventType.SENSITIVE_INFRASTRUCTURE_REQUEST,
            SecurityEventType.SECRET_REQUEST,
            SecurityEventType.DATABASE_ACCESS_REQUEST,
        )
    else:
        raise EvaluationDatasetContractError("Unsupported historical security event expectation")
    return SecurityRuntimeExpectation(acceptable_event_types=event_types, action=SecurityAction.BLOCK)


CHALLENGE_014_CLIENT_STATES = (
    HumanEscalationState.BOT,
    HumanEscalationState.WAITING_CONFIRMATION,
    HumanEscalationState.WAITING_HUMAN,
)
CHALLENGE_014_OPERATOR_ACCEPTANCE_STATE = HumanEscalationState.HUMAN


def adapt_challenge_014_operator_acceptance() -> ChallengeRuntimeExpectation:
    return ChallengeRuntimeExpectation(
        route=None,
        capabilities=(RouterCapability.HUMAN_ESCALATION,),
        terminal_state=CHALLENGE_014_OPERATOR_ACCEPTANCE_STATE,
        automation_suspended=True,
    )
