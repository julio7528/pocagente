"""Secret-safe immutable observations produced by the Challenge evaluator."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from apps.agent_api.app.agents.human_escalation import HumanEscalationState
from apps.agent_api.app.agents.router import RouterCapability, RouterRoute, WebSearchPolicy
from apps.agent_api.app.security.models import SecurityAction, SecurityEventType


class ChallengeExecutionMode(StrEnum):
    """The Phase 11.4 deterministic authenticated application boundary."""

    DETERMINISTIC_E2E = "DETERMINISTIC_E2E"


class ChallengeScenarioStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class ChallengeInvocationCounts(BaseModel):
    """Actual capability invocations, captured as a per-scenario/turn delta."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    knowledge: int = Field(ge=0)
    web: int = Field(ge=0)
    customer_support: int = Field(ge=0)
    ops_lookup_protocol_status: int = Field(ge=0)
    ops_inspect_execution_failure: int = Field(ge=0)
    interpretation_provider: int = Field(ge=0)
    human_escalation: int = Field(ge=0)


class ChallengeSecurityObservation(BaseModel):
    """Direct Phase 10 audit evidence without protected request material."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    blocked: bool
    event_types: tuple[SecurityEventType, ...] = ()
    audit_actions: tuple[SecurityAction, ...] = ()
    sanitized: bool
    public_response_safe: bool
    audit_recorded: bool
    protective_action_observed: bool
    forbidden_continuation_absent: bool


class ChallengeAuthorizationObservation(BaseModel):
    """Measured authorization evidence; non-applicable is explicit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    applicable: bool
    authorized_request_succeeded: bool | None = None
    unauthorized_request_checked: bool = False
    unauthorized_repository_calls: int = Field(default=0, ge=0)
    unauthorized_access_blocked: bool | None = None
    operator_authorization_checked: bool = False
    operator_acceptance_succeeded: bool | None = None
    wrong_operator_rejected: bool | None = None
    ownership_preserved: bool | None = None

    @property
    def respected(self) -> bool | None:
        if not self.applicable:
            return None
        evidence: tuple[bool | None, ...] = (
            self.authorized_request_succeeded,
            self.unauthorized_request_checked,
            self.unauthorized_access_blocked,
        )
        if self.operator_authorization_checked:
            evidence += (
                self.operator_acceptance_succeeded,
                self.wrong_operator_rejected,
                self.ownership_preserved,
            )
        return all(value is True for value in evidence)


class ChallengeToolObservation(BaseModel):
    """Exact approved OPS-tool observation for one scenario."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_tools: tuple[str, ...] = ()
    observed_tools: tuple[str, ...] = ()
    expected_tools_satisfied: bool
    unexpected_tools_absent: bool


class ChallengeFactInferenceObservation(BaseModel):
    """Structural FACT/INFERENCE evidence, never semantic LLM judging."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    applicable: bool
    facts_present: bool | None = None
    inferences_present: bool | None = None
    separated: bool | None = None


class ChallengeForbiddenObservation(BaseModel):
    """Every declared forbidden capability is explicitly evaluated or architectural."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    declared: tuple[str, ...] = ()
    checked: tuple[str, ...] = ()
    architectural_prohibitions: tuple[str, ...] = ()
    respected: bool


class ChallengeTurnObservation(BaseModel):
    """One ordered client or controlled operator verification transition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    turn_number: int = Field(ge=1)
    kind: Literal["CLIENT", "OPERATOR_ACCEPT", "AUTOMATION_SUSPENSION", "OPERATOR_REJECT", "OPERATOR_RESOLVE"]
    route: RouterRoute | None = None
    status: str = Field(min_length=1)
    invocation_counts: ChallengeInvocationCounts
    tool_calls: tuple[str, ...] = ()
    human_state: HumanEscalationState | None = None
    assigned_operator_present: bool = False
    automation_suspended: bool = False
    fact_count: int = Field(ge=0)
    inference_count: int = Field(ge=0)
    reason: str | None = None


class ConditionalFallbackObservation(BaseModel):
    """Supporting branch evidence for one declared conditional scenario."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary_knowledge_called: bool
    primary_web_called: bool
    fallback_knowledge_called: bool
    fallback_web_called: bool
    fallback_after_knowledge: bool
    primary_events: tuple[str, ...] = ()
    fallback_events: tuple[str, ...] = ()
    persistent_write_boundary_available: bool = False


class ChallengeHumanObservation(BaseModel):
    """Handoff state evidence, stripped to safe structural properties."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    states: tuple[HumanEscalationState, ...] = ()
    operator_authorization_rejected: bool = False
    wrong_operator_ownership_preserved: bool = False
    assigned_operator_resolution_succeeded: bool = False
    handoff_context_safe: bool = True


class ChallengeScenarioResult(BaseModel):
    """One immutable result in source-suite order; no raw message or payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: str = Field(min_length=1)
    suite_version: str = Field(min_length=1)
    runner_version: Literal["1.0"] = "1.0"
    execution_mode: ChallengeExecutionMode
    status: ChallengeScenarioStatus
    reason: str | None = None
    expected_route: RouterRoute | None = None
    observed_route: RouterRoute | None = None
    expected_capabilities: tuple[RouterCapability, ...] = ()
    invocation_counts: ChallengeInvocationCounts
    observed_tool_calls: tuple[str, ...] = ()
    forbidden_capabilities_absent: bool
    forbidden: ChallengeForbiddenObservation
    web_search_policy: WebSearchPolicy = WebSearchPolicy.NONE
    authorization: ChallengeAuthorizationObservation
    tools: ChallengeToolObservation
    fact_inference: ChallengeFactInferenceObservation
    security: ChallengeSecurityObservation | None = None
    turns: tuple[ChallengeTurnObservation, ...] = ()
    human: ChallengeHumanObservation | None = None
    conditional_fallback: ConditionalFallbackObservation | None = None
