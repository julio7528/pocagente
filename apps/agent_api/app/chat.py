"""Stable transport adapter between FastAPI and Phase 9 orchestration."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.agent_api.app.agents.customer_support import CustomerSupportOperation
from apps.agent_api.app.agents.human_escalation import (
    ConversationReference,
    HandoffFact,
    HandoffInference,
    HandoffPackage,
    HumanEscalationAction,
    HumanEscalationReason,
    HumanEscalationRequest,
    HumanEscalationState,
    SupportOperatorAuthorization,
)
from apps.agent_api.app.agents.orchestration import (
    CustomerSupportContext,
    OrchestrationRequest,
    OrchestrationResult,
    OrchestrationStatus,
)
from apps.agent_api.app.auth import AuthenticatedPrincipal, PrincipalRole
from apps.agent_api.app.tools.ops import OpsAccessContext


class OrchestrationCapability(Protocol):
    async def execute(self, request: OrchestrationRequest) -> OrchestrationResult: ...


class ChatSupportOperation(StrEnum):
    PROTOCOL_STATUS = "PROTOCOL_STATUS"
    EXECUTION_FAILURE = "EXECUTION_FAILURE"


class ChatOperationalContext(BaseModel):
    """Business selectors only; authorization is derived from trusted claims."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    protocol_number: str = Field(min_length=1, max_length=128)
    operation: ChatSupportOperation
    run_id: int | None = Field(default=None, gt=0)


class ChatHandoffFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = Field(min_length=1, max_length=128)
    statement: str = Field(min_length=1, max_length=1000)


class ChatHandoffInference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str = Field(min_length=1, max_length=1000)


class ChatHandoffPackage(BaseModel):
    """Allowlisted transport representation of an already sanitized handoff."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    conversation_id: str = Field(min_length=1, max_length=128)
    problem_summary: str = Field(min_length=1, max_length=1000)
    reason: HumanEscalationReason
    protocol_reference: str | None = Field(default=None, max_length=128)
    run_reference: int | None = Field(default=None, gt=0)
    observed_operational_state: str | None = Field(default=None, max_length=1000)
    last_successful_stage: str | None = Field(default=None, max_length=500)
    failure_stage: str | None = Field(default=None, max_length=500)
    sanitized_error: str | None = Field(default=None, max_length=1000)
    timeline: tuple[str, ...] = ()
    facts: tuple[ChatHandoffFact, ...] = ()
    inferences: tuple[ChatHandoffInference, ...] = ()
    user_confirmation: bool = False


class ChatHumanContext(BaseModel):
    """Explicit transition event; actor authority comes from authentication."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    conversation_id: str = Field(min_length=1, max_length=128)
    current_state: HumanEscalationState
    action: HumanEscalationAction
    reason: HumanEscalationReason | None = None
    handoff: ChatHandoffPackage | None = None
    active_operator_id: str | None = Field(default=None, min_length=1, max_length=128)


class ChatRequest(BaseModel):
    """Strict challenge-compatible request with narrowly typed optional context."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=4000)
    user_id: str = Field(min_length=1, max_length=128)
    operational_context: ChatOperationalContext | None = None
    human_context: ChatHumanContext | None = None

    @field_validator("message", "user_id")
    @classmethod
    def value_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value


class ChatCitation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    label: str
    attribution: str
    source_url: str | None = None


class ChatKnowledgePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    answer: str | None = None
    citations: tuple[ChatCitation, ...] = ()


class ChatSupportFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    statement: str


class ChatSupportInference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str


class ChatSupportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    answer: str | None = None
    facts: tuple[ChatSupportFact, ...] = ()
    inferences: tuple[ChatSupportInference, ...] = ()


class ChatHumanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: HumanEscalationState
    conversation_id: str
    assigned_operator_id: str | None = None
    automation_suspended: bool = False
    handoff: ChatHandoffPackage | None = None

    @model_validator(mode="after")
    def waiting_does_not_claim_ownership(self) -> ChatHumanPayload:
        if self.state is HumanEscalationState.WAITING_HUMAN and (
            self.assigned_operator_id is not None or self.automation_suspended
        ):
            raise ValueError("waiting handoff cannot claim active human ownership")
        return self


class ChatResponse(BaseModel):
    """Deliberately allowlisted provider-neutral response for a future portal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    route: str
    answer: str | None = None
    citations: tuple[ChatCitation, ...] = ()
    knowledge: ChatKnowledgePayload | None = None
    customer_support: ChatSupportPayload | None = None
    requires_human: bool = False
    human: ChatHumanPayload | None = None
    reason: str


class SafeErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


class SafeErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    error: SafeErrorDetail


class ChatAuthorizationError(Exception):
    pass


class ChatUnavailableError(Exception):
    pass


_UNSAFE_OUTPUT = re.compile(
    r"sk-proj-[A-Za-z0-9_-]{8,}|eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|"
    r"\bbearer\s+[A-Za-z0-9_.-]+|postgres(?:ql)?://|\btraceback\b|"
    r"\bselect\b[\s\S]{0,500}\bfrom\b|(?:[A-Za-z]:\\[^\s]+)",
    re.IGNORECASE,
)
_SAFE_REASON = re.compile(r"^[A-Za-z0-9_]{1,128}$")


def _safe_text(value: str | None) -> str | None:
    if value is None:
        return None
    return "Sensitive content withheld." if _UNSAFE_OUTPUT.search(value) else value


def _safe_reason(value: str) -> str:
    return value if _SAFE_REASON.fullmatch(value) else "REQUEST_COULD_NOT_BE_COMPLETED_SAFELY"


def _safe_fact_source(value: str) -> str:
    return {
        "ProtocolStatusFacts": "OPS_PROTOCOL_STATUS",
        "ExecutionFailureEvidence": "OPS_EXECUTION_FAILURE",
    }.get(value, "OPS_EVIDENCE")


class ChatApplicationService:
    """Translate transport contracts; it neither routes nor executes capabilities directly."""

    def __init__(self, orchestrator: OrchestrationCapability) -> None:
        self._orchestrator = orchestrator

    async def handle(self, request: ChatRequest, principal: AuthenticatedPrincipal) -> ChatResponse:
        if request.user_id != principal.user_id:
            raise ChatAuthorizationError()
        operational = self._operational_context(request, principal)
        human = self._human_context(request.human_context, principal)
        result = await self._orchestrator.execute(
            OrchestrationRequest(
                message=request.message,
                has_authorized_protocol_context=(
                    operational is not None and operational.authorization.can_read_operational_facts
                ),
                customer_support_context=operational,
                human_escalation_request=human,
            )
        )
        if result.status is OrchestrationStatus.ORCHESTRATION_ERROR:
            raise ChatUnavailableError()
        return self._response(result)

    @staticmethod
    def _operational_context(
        request: ChatRequest,
        principal: AuthenticatedPrincipal,
    ) -> CustomerSupportContext | None:
        context = request.operational_context
        if context is None:
            return None
        return CustomerSupportContext(
            protocol_number=context.protocol_number,
            operation=CustomerSupportOperation(context.operation.value),
            authorization=OpsAccessContext(
                principal_id=principal.user_id,
                can_read_operational_facts=principal.can_read_operational_facts,
            ),
            run_id=context.run_id,
        )

    @staticmethod
    def _human_context(
        context: ChatHumanContext | None,
        principal: AuthenticatedPrincipal,
    ) -> HumanEscalationRequest | None:
        if context is None:
            return None
        client_actions = {HumanEscalationAction.OFFER, HumanEscalationAction.CONFIRM, HumanEscalationAction.NONE}
        operator_actions = {
            HumanEscalationAction.ACCEPT,
            HumanEscalationAction.RETURN_TO_AUTOMATION,
            HumanEscalationAction.RESOLVE,
        }
        if context.action in client_actions and principal.role is not PrincipalRole.CLIENT:
            raise ChatAuthorizationError()
        if context.action in operator_actions and principal.role is not PrincipalRole.SUPPORT_AGENT:
            raise ChatAuthorizationError()
        conversation = ConversationReference(conversation_id=context.conversation_id)
        package = ChatApplicationService._handoff_package(context.handoff)
        operator = None
        if principal.role is PrincipalRole.SUPPORT_AGENT:
            operator = SupportOperatorAuthorization(operator_id=principal.user_id, is_support_agent=True)
        return HumanEscalationRequest(
            conversation=conversation,
            current_state=context.current_state,
            action=context.action,
            reason=context.reason,
            handoff_package=package,
            explicit_user_confirmation=(
                context.action is HumanEscalationAction.CONFIRM
                and principal.role is PrincipalRole.CLIENT
            ),
            operator=operator,
            active_operator_id=context.active_operator_id,
        )

    @staticmethod
    def _handoff_package(
        value: ChatHandoffPackage | None,
    ) -> HandoffPackage | None:
        if value is None:
            return None
        return HandoffPackage(
            conversation=ConversationReference(conversation_id=value.conversation_id),
            reason=value.reason,
            problem_summary=value.problem_summary,
            protocol_reference=value.protocol_reference,
            run_reference=value.run_reference,
            observed_operational_state=value.observed_operational_state,
            last_successful_stage=value.last_successful_stage,
            failure_stage=value.failure_stage,
            sanitized_error=value.sanitized_error,
            timeline=value.timeline,
            facts=tuple(HandoffFact(source=_safe_fact_source(item.source), statement=item.statement) for item in value.facts),
            inferences=tuple(HandoffInference(statement=item.statement) for item in value.inferences),
            user_confirmation=value.user_confirmation,
        )

    @staticmethod
    def _response(result: OrchestrationResult) -> ChatResponse:
        knowledge = None
        if result.knowledge_result is not None:
            knowledge = ChatKnowledgePayload(
                status=result.knowledge_result.status.value,
                answer=_safe_text(result.knowledge_result.answer),
                citations=tuple(
                    ChatCitation(
                        id=item.id,
                        label=_safe_text(item.label) or "Source",
                        attribution=_safe_text(item.attribution) or "Approved source",
                        source_url=item.source_url,
                    )
                    for item in result.knowledge_result.citations
                ),
            )
        support = None
        if result.customer_support_result is not None:
            support = ChatSupportPayload(
                status=result.customer_support_result.status.value,
                answer=_safe_text(result.customer_support_result.answer),
                facts=tuple(
                    ChatSupportFact(source=_safe_fact_source(item.source), statement=_safe_text(item.statement) or "Sensitive content withheld.")
                    for item in result.customer_support_result.facts
                ),
                inferences=tuple(
                    ChatSupportInference(statement=_safe_text(item.statement) or "Sensitive content withheld.")
                    for item in result.customer_support_result.inferences
                ),
            )
        human = None
        if result.human_escalation_result is not None:
            item = result.human_escalation_result
            handoff = None
            if item.handoff_package is not None:
                package = item.handoff_package
                handoff = ChatHandoffPackage(
                    conversation_id=package.conversation.conversation_id,
                    problem_summary=package.problem_summary,
                    reason=package.reason,
                    protocol_reference=package.protocol_reference,
                    run_reference=package.run_reference,
                    observed_operational_state=package.observed_operational_state,
                    last_successful_stage=package.last_successful_stage,
                    failure_stage=package.failure_stage,
                    sanitized_error=package.sanitized_error,
                    timeline=package.timeline,
                    facts=tuple(ChatHandoffFact(source=_safe_fact_source(f.source), statement=f.statement) for f in package.facts),
                    inferences=tuple(ChatHandoffInference(statement=i.statement) for i in package.inferences),
                    user_confirmation=package.user_confirmation,
                )
            human = ChatHumanPayload(
                state=item.state,
                conversation_id=item.conversation.conversation_id,
                assigned_operator_id=item.assigned_operator_id,
                automation_suspended=item.automation_suspended,
                handoff=handoff,
            )
        direct_answer = None
        citations: tuple[ChatCitation, ...] = ()
        if knowledge is not None and support is None:
            direct_answer, citations = knowledge.answer, knowledge.citations
        elif support is not None and knowledge is None:
            direct_answer = support.answer
        return ChatResponse(
            status=result.status.value,
            route=result.route.value,
            answer=direct_answer,
            citations=citations,
            knowledge=knowledge,
            customer_support=support,
            requires_human=result.human_escalation_required,
            human=human,
            reason=_safe_reason(result.reason),
        )
