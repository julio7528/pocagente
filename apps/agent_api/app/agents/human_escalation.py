"""Explicit, non-persistent Human Escalation state transitions."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.agent_api.app.agents.customer_support import (
    CustomerSupportResult,
    ObservedOperationalFact,
    OperationalInference,
)


_SENSITIVE = re.compile(
    r"sk-proj-[A-Za-z0-9_-]{20,}|"
    r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|"
    r"\bbearer\s+[A-Za-z0-9_.-]+|"
    r"\b(?:password|api[_ -]?key|token|credential|secret)\b(?:\s*(?:=|:|\s+)[^\s]+)?|"
    r"postgres(?:ql)?://|\bdsn\s*(?:=|:)|"
    r"\btraceback\b|\bfile\s+\"|\bselect\b[\s\S]{0,500}\bfrom\b",
    re.IGNORECASE,
)


def _sanitize(value: str | None) -> str | None:
    """Redact a complete unsafe field without leaking a token prefix or suffix."""

    if value is None:
        return None
    value = value.strip()
    return "Sensitive content withheld." if _SENSITIVE.search(value) else value


class HumanEscalationState(StrEnum):
    BOT = "BOT"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    WAITING_HUMAN = "WAITING_HUMAN"
    HUMAN = "HUMAN"
    RESOLVED = "RESOLVED"


class HumanEscalationReason(StrEnum):
    USER_REQUESTED_HUMAN = "USER_REQUESTED_HUMAN"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNRESOLVED_REQUEST = "UNRESOLVED_REQUEST"


class HumanEscalationAction(StrEnum):
    OFFER = "OFFER"
    CONFIRM = "CONFIRM"
    ACCEPT = "ACCEPT"
    RETURN_TO_AUTOMATION = "RETURN_TO_AUTOMATION"
    RESOLVE = "RESOLVE"
    NONE = "NONE"


class HumanEscalationStatus(StrEnum):
    TRANSITIONED = "TRANSITIONED"
    REJECTED = "REJECTED"
    AUTOMATION_SUSPENDED = "AUTOMATION_SUSPENDED"


class ConversationReference(BaseModel):
    """Application-supplied correlation only; no persistence is implied."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    conversation_id: str = Field(min_length=1, max_length=128)


class SupportOperatorAuthorization(BaseModel):
    """Trusted future-Django-compatible operator authority, never parsed from chat."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    operator_id: str = Field(min_length=1, max_length=128)
    is_support_agent: bool


class HandoffFact(BaseModel):
    """Sanitized observed fact; it remains distinct from a diagnosis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = Field(min_length=1)
    statement: str = Field(min_length=1)

    @field_validator("statement", mode="before")
    @classmethod
    def redact_sensitive_statement(cls, value: str) -> str:
        return _sanitize(value) or "Sensitive content withheld."


class HandoffInference(BaseModel):
    """Sanitized diagnosis/inference, never an observed operational fact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str = Field(min_length=1)

    @field_validator("statement", mode="before")
    @classmethod
    def redact_sensitive_statement(cls, value: str) -> str:
        return _sanitize(value) or "Sensitive content withheld."


class HandoffPackage(BaseModel):
    """Minimum allowlisted context for an authorized human operator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    conversation: ConversationReference
    reason: HumanEscalationReason
    problem_summary: str = Field(min_length=1, max_length=1000)
    protocol_reference: str | None = Field(default=None, max_length=128)
    run_reference: int | None = Field(default=None, gt=0)
    observed_operational_state: str | None = Field(default=None, max_length=1000)
    last_successful_stage: str | None = Field(default=None, max_length=500)
    failure_stage: str | None = Field(default=None, max_length=500)
    sanitized_error: str | None = Field(default=None, max_length=1000)
    timeline: tuple[str, ...] = ()
    facts: tuple[HandoffFact, ...] = ()
    inferences: tuple[HandoffInference, ...] = ()
    user_confirmation: bool = False

    @field_validator(
        "problem_summary",
        "protocol_reference",
        "observed_operational_state",
        "last_successful_stage",
        "failure_stage",
        "sanitized_error",
        mode="before",
    )
    @classmethod
    def redact_sensitive_fields(cls, value: str | None) -> str | None:
        return _sanitize(value)

    @field_validator("timeline", mode="before")
    @classmethod
    def redact_sensitive_timeline(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_sanitize(item) or "Sensitive content withheld." for item in value)


class HumanEscalationRequest(BaseModel):
    """Trusted application event; free-form user text cannot perform a transition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    conversation: ConversationReference
    current_state: HumanEscalationState
    action: HumanEscalationAction
    reason: HumanEscalationReason | None = None
    handoff_package: HandoffPackage | None = None
    explicit_user_confirmation: bool = False
    operator: SupportOperatorAuthorization | None = None
    active_operator_id: str | None = Field(default=None, min_length=1, max_length=128)


class HumanEscalationResult(BaseModel):
    """Controlled transition result suitable for a future HTTP/Django adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: HumanEscalationStatus
    conversation: ConversationReference
    state: HumanEscalationState
    reason: str = Field(min_length=1)
    handoff_package: HandoffPackage | None = None
    assigned_operator_id: str | None = None
    automation_suspended: bool = False

    @model_validator(mode="after")
    def ownership_matches_state(self) -> HumanEscalationResult:
        if self.state is HumanEscalationState.HUMAN:
            if self.status is not HumanEscalationStatus.REJECTED and (
                not self.assigned_operator_id or not self.automation_suspended
            ):
                raise ValueError("active human ownership requires an assigned authorized operator")
        elif self.assigned_operator_id is not None or self.automation_suspended:
            raise ValueError("only active human ownership may have an operator or suspend automation")
        return self


def build_handoff_package(
    *,
    conversation: ConversationReference,
    reason: HumanEscalationReason,
    problem_summary: str,
    customer_support_result: CustomerSupportResult | None = None,
    protocol_reference: str | None = None,
    run_reference: int | None = None,
    observed_operational_state: str | None = None,
    last_successful_stage: str | None = None,
    failure_stage: str | None = None,
    sanitized_error: str | None = None,
    timeline: tuple[str, ...] = (),
) -> HandoffPackage:
    """Compose an allowlisted, redacted package without retaining raw diagnostics."""

    facts: tuple[HandoffFact, ...] = ()
    inferences: tuple[HandoffInference, ...] = ()
    if customer_support_result is not None:
        facts = tuple(
            HandoffFact(source=item.source, statement=_sanitize(item.statement) or "Sensitive content withheld.")
            for item in customer_support_result.facts
        )
        inferences = tuple(
            HandoffInference(statement=_sanitize(item.statement) or "Sensitive content withheld.")
            for item in customer_support_result.inferences
        )
    return HandoffPackage(
        conversation=conversation,
        reason=reason,
        problem_summary=_sanitize(problem_summary) or "Support request requires human review.",
        protocol_reference=_sanitize(protocol_reference),
        run_reference=run_reference,
        observed_operational_state=_sanitize(observed_operational_state),
        last_successful_stage=_sanitize(last_successful_stage),
        failure_stage=_sanitize(failure_stage),
        sanitized_error=_sanitize(sanitized_error),
        timeline=tuple(_sanitize(item) or "Sensitive content withheld." for item in timeline),
        facts=facts,
        inferences=inferences,
    )


class HumanEscalationAgent:
    """Application-owned state machine; it has no database, LLM, or queue dependency."""

    def transition(self, request: HumanEscalationRequest) -> HumanEscalationResult:
        if request.action is HumanEscalationAction.OFFER:
            if request.current_state is HumanEscalationState.BOT and request.reason is not None:
                return self._transitioned(request, HumanEscalationState.WAITING_CONFIRMATION, "HUMAN_ESCALATION_OFFERED")
            return self._rejected(request, "OFFER_REQUIRES_BOT_AND_REASON")
        if request.action is HumanEscalationAction.CONFIRM:
            if (
                request.current_state is HumanEscalationState.WAITING_CONFIRMATION
                and request.explicit_user_confirmation
                and request.handoff_package is not None
                and request.handoff_package.conversation == request.conversation
            ):
                package = request.handoff_package.model_copy(update={"user_confirmation": True})
                return self._transitioned(request, HumanEscalationState.WAITING_HUMAN, "HANDOFF_CONFIRMED_AWAITING_OPERATOR", package)
            return self._rejected(request, "CONFIRMATION_REQUIRES_WAITING_CONFIRMATION_AND_SAFE_PACKAGE")
        if request.action is HumanEscalationAction.ACCEPT:
            if (
                request.current_state is HumanEscalationState.WAITING_HUMAN
                and request.handoff_package is not None
                and request.handoff_package.conversation == request.conversation
                and request.handoff_package.user_confirmation
                and request.operator is not None
                and request.operator.is_support_agent
            ):
                return HumanEscalationResult(
                    status=HumanEscalationStatus.TRANSITIONED,
                    conversation=request.conversation,
                    state=HumanEscalationState.HUMAN,
                    reason="AUTHORIZED_OPERATOR_ACCEPTED_HANDOFF",
                    handoff_package=request.handoff_package,
                    assigned_operator_id=request.operator.operator_id,
                    automation_suspended=True,
                )
            return self._rejected(request, "ACCEPTANCE_REQUIRES_AUTHORIZED_OPERATOR_AND_WAITING_HANDOFF")
        if request.action in {HumanEscalationAction.RETURN_TO_AUTOMATION, HumanEscalationAction.RESOLVE}:
            if (
                request.current_state is not HumanEscalationState.HUMAN
                or request.operator is None
                or not request.operator.is_support_agent
                or request.active_operator_id is None
                or request.operator.operator_id != request.active_operator_id
            ):
                return self._rejected(request, "ACTIVE_HUMAN_OWNER_MATCH_REQUIRED")
            target = HumanEscalationState.BOT if request.action is HumanEscalationAction.RETURN_TO_AUTOMATION else HumanEscalationState.RESOLVED
            return self._transitioned(request, target, "EXPLICIT_RETURN_TO_AUTOMATION" if target is HumanEscalationState.BOT else "EXPLICIT_HUMAN_RESOLUTION")
        if request.current_state is HumanEscalationState.HUMAN:
            if request.active_operator_id is None:
                return self._rejected(request, "ACTIVE_HUMAN_OWNER_REFERENCE_REQUIRED")
            return HumanEscalationResult(
                status=HumanEscalationStatus.AUTOMATION_SUSPENDED,
                conversation=request.conversation,
                state=HumanEscalationState.HUMAN,
                reason="AUTOMATION_SUSPENDED_WHILE_HUMAN_OWNS_CONVERSATION",
                assigned_operator_id=request.active_operator_id,
                automation_suspended=True,
            )
        return self._rejected(request, "NO_APPROVED_HUMAN_ESCALATION_TRANSITION")

    @staticmethod
    def _transitioned(request: HumanEscalationRequest, state: HumanEscalationState, reason: str, package: HandoffPackage | None = None) -> HumanEscalationResult:
        return HumanEscalationResult(status=HumanEscalationStatus.TRANSITIONED, conversation=request.conversation, state=state, reason=reason, handoff_package=package)

    @staticmethod
    def _rejected(request: HumanEscalationRequest, reason: str) -> HumanEscalationResult:
        human_owned = request.current_state is HumanEscalationState.HUMAN and request.active_operator_id is not None
        return HumanEscalationResult(
            status=HumanEscalationStatus.REJECTED,
            conversation=request.conversation,
            state=request.current_state,
            reason=reason,
            assigned_operator_id=request.active_operator_id if human_owned else None,
            automation_suspended=human_owned,
        )
