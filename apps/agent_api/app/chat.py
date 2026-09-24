"""Stable transport adapter between FastAPI and Phase 9 orchestration."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.agent_api.app.agents.customer_support import CustomerSupportOperation, OperationalQueryPlan
from apps.agent_api.app.agents.conversational import ConversationalAgent
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
from apps.agent_api.app.agents.semantic_routing import SemanticIntent
from apps.agent_api.app.agents.router import RouterRoute
from apps.agent_api.app.auth import AuthenticatedPrincipal, PrincipalRole
from apps.agent_api.app.security.models import SecurityAction as AuditAction, SecurityAuditContext, SecurityAuditStatus
from apps.agent_api.app.security.semantic import (
    OutputAction,
    OutputSecurityGate,
    SecurityCategory,
    SecurityResponseAgent,
)
from apps.agent_api.app.tools.ops import OpsAccessContext
from apps.agent_api.app.telemetry import RuntimeEventKind, RuntimeTelemetrySink, emit_runtime_event, runtime_telemetry


class OrchestrationCapability(Protocol):
    async def execute(self, request: OrchestrationRequest) -> OrchestrationResult: ...


class ChatSupportOperation(StrEnum):
    PROTOCOL_STATUS = "PROTOCOL_STATUS"
    EXECUTION_FAILURE = "EXECUTION_FAILURE"


class ChatOperationalContext(BaseModel):
    """Business selectors only; authorization is derived from trusted claims."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    protocol_number: str = Field(min_length=1, max_length=128)
    operation: ChatSupportOperation | None = None
    run_id: int | None = Field(default=None, gt=0)
    transient: bool = False


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
    analytics_grain_context: Literal["PROTOCOL", "EXECUTION", "EVENT"] | None = None
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
    operational_plan: OperationalQueryPlan | None = None
    selected_protocol_number: str | None = None
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
    intent: SemanticIntent | None = None
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


_SECURITY_BLOCK_FALLBACK = "Essa informação é restrita pela política de segurança. Posso ajudar com informações funcionais permitidas."


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
        "ServiceRequestRecord": "OPS_RECENT_PROTOCOLS",
        "RecentExecutedProtocolRecord": "OPS_EXECUTION_RECENCY",
        "IncomingEmailRecord": "OPS_ORIGIN_EMAIL",
        "EmailAttachmentRecord": "OPS_EMAIL_ATTACHMENT",
        "AutomationRunRecord": "OPS_AUTOMATION_RUN",
        "EstablishmentRecord": "OPS_ESTABLISHMENT_STATE",
        "ExecutionLogRecord": "OPS_EXECUTION_TIMELINE",
        "ProtocolTimestampSemantics": "OPS_TIMESTAMP_SEMANTICS",
    }.get(value, "OPS_EVIDENCE")


def _security_category(semantics: tuple[object, ...]) -> SecurityCategory:
    from apps.agent_api.app.security.models import SecurityEventType, SecurityResourceCategory

    if semantics:
        item = semantics[0]
        if getattr(item, "event_type", None) is SecurityEventType.DATABASE_ACCESS_REQUEST:
            return SecurityCategory.DATABASE_ACCESS
        if getattr(item, "event_type", None) is SecurityEventType.PROMPT_INJECTION:
            return SecurityCategory.PROMPT_INJECTION
        if getattr(item, "event_type", None) is SecurityEventType.CREDENTIAL_REQUEST:
            return SecurityCategory.CREDENTIAL_REQUEST
        if getattr(item, "event_type", None) is SecurityEventType.SECRET_REQUEST:
            return SecurityCategory.SECRET_REQUEST
        if getattr(item, "resource_category", None) is SecurityResourceCategory.PROTECTED_PATH:
            return SecurityCategory.PROTECTED_PATH
        if getattr(item, "event_type", None) is SecurityEventType.AUTHORIZATION_BYPASS_ATTEMPT:
            return SecurityCategory.AUTHORIZATION_BYPASS
        if getattr(item, "event_type", None) is SecurityEventType.SENSITIVE_INFRASTRUCTURE_REQUEST:
            return SecurityCategory.SENSITIVE_INFRASTRUCTURE
    return SecurityCategory.OTHER_POLICY_VIOLATION


def _redact_tree(value: object, gate: OutputSecurityGate) -> object:
    if isinstance(value, str):
        return gate.redact(value)
    if isinstance(value, list):
        return [_redact_tree(item, gate) for item in value]
    if isinstance(value, dict):
        return {key: _redact_tree(item, gate) for key, item in value.items()}
    return value


async def _apply_output_security(
    response: ChatResponse,
    gate: OutputSecurityGate,
    security_response_agent: SecurityResponseAgent | None,
) -> tuple[ChatResponse, SecurityCategory | None, AuditAction | None]:
    import json

    original = response.model_dump(mode="json")
    # Empty/ambiguous outcomes carry no candidate disclosure to validate.
    if not (
        response.answer
        or response.citations
        or response.knowledge is not None
        or response.customer_support is not None
        or response.human is not None
    ):
        return response, None, None
    safe_candidate = _redact_tree(original, gate)
    changed = safe_candidate != original
    emit_runtime_event(RuntimeEventKind.SECURITY_OUTPUT, value="STARTED")
    try:
        review = await gate.review(json.dumps(safe_candidate, ensure_ascii=False))
    except Exception:
        # An unavailable reviewer cannot authorize a potentially unsafe answer.
        emit_runtime_event(RuntimeEventKind.SECURITY_OUTPUT, value="CONTROLLED_ERROR")
        category = SecurityCategory.OTHER_POLICY_VIOLATION
        return await _blocked_output_response(response, category, security_response_agent), category, AuditAction.BLOCK
    if review.action is OutputAction.BLOCK or review.action is OutputAction.REDACT:
        emit_runtime_event(RuntimeEventKind.SECURITY_OUTPUT, value="BLOCKED")
        return await _blocked_output_response(response, review.category, security_response_agent), review.category, AuditAction.BLOCK
    emit_runtime_event(RuntimeEventKind.SECURITY_OUTPUT, value="REDACTED" if changed else "ALLOWED")
    if changed:
        category = gate.redaction_category(json.dumps(original, ensure_ascii=False))
        return ChatResponse.model_validate(safe_candidate), category, AuditAction.REDACT
    return ChatResponse.model_validate(safe_candidate), None, None


async def _blocked_output_response(
    response: ChatResponse,
    category: SecurityCategory,
    security_response_agent: SecurityResponseAgent | None,
) -> ChatResponse:
    answer = _SECURITY_BLOCK_FALLBACK
    if security_response_agent is not None:
        try:
            answer = await security_response_agent.respond(category)
        except Exception:
            pass
    # Never return the candidate, nested fact payloads, citations, or handoff data.
    return ChatResponse(
        status=OrchestrationStatus.SECURITY_BLOCKED.value,
        route=response.route,
        answer=answer,
        reason="OUTPUT_SECURITY_BLOCK",
    )


class ChatApplicationService:
    """Translate transport contracts; it neither routes nor executes capabilities directly."""

    def __init__(
        self,
        orchestrator: OrchestrationCapability,
        security_response_agent: SecurityResponseAgent | None = None,
        output_security_gate: OutputSecurityGate | None = None,
        recovery_agent: ConversationalAgent | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._security_response_agent = security_response_agent
        self._output_security_gate = output_security_gate
        self._recovery_agent = recovery_agent

    async def handle(
        self,
        request: ChatRequest,
        principal: AuthenticatedPrincipal,
        *,
        telemetry_sink: RuntimeTelemetrySink | None = None,
    ) -> ChatResponse:
        if request.user_id != principal.user_id:
            raise ChatAuthorizationError()
        operational = self._operational_context(request, principal)
        human = self._human_context(request.human_context, principal)
        audit_context = SecurityAuditContext(
            user_identifier=principal.user_id,
            request_reference=f"chat-{uuid4().hex}",
        )
        with runtime_telemetry(telemetry_sink):
            result = await self._orchestrator.execute(
                OrchestrationRequest(
                    message=request.message,
                    ops_access_context=OpsAccessContext(
                        principal_id=principal.user_id,
                        can_read_operational_facts=principal.can_read_operational_facts,
                    ),
                    customer_support_context=operational,
                    analytics_grain_context=request.analytics_grain_context,
                    human_escalation_request=human,
                    security_audit_context=audit_context,
                )
            )
            security_answer = None
            if result.status is OrchestrationStatus.SECURITY_BLOCKED:
                category = _security_category(result.security_semantics)
                if self._security_response_agent is not None:
                    try:
                        security_answer = await self._security_response_agent.respond(category)
                        emit_runtime_event(RuntimeEventKind.CAPABILITY, name="SecurityResponseAgent", value="LLM_FORMULATED_RESPONSE")
                    except Exception:
                        security_answer = _SECURITY_BLOCK_FALLBACK
                        emit_runtime_event(RuntimeEventKind.SECURITY_OUTPUT, value="CONTROLLED_ERROR")
                else:
                    security_answer = _SECURITY_BLOCK_FALLBACK
                    emit_runtime_event(RuntimeEventKind.SECURITY_OUTPUT, value="CONTROLLED_ERROR")
            response = self._response(result, security_answer=security_answer)
            recovery_kind = self._recovery_kind(result)
            if response.answer is None and recovery_kind is not None and self._recovery_agent is not None:
                recovery = await self._recovery_agent.recover(
                    request.message,
                    route=result.route.value,
                    failure_kind=recovery_kind,
                    interpretation=(
                        result.knowledge_result.retrieval_query
                        if result.knowledge_result is not None
                        else None
                    ),
                )
                response = response.model_copy(update={"answer": recovery.answer})
                emit_runtime_event(
                    RuntimeEventKind.CAPABILITY,
                    name="RecoveryResponseAgent",
                    value=recovery.reason,
                )
            output_block_category = None
            output_action = None
            if self._output_security_gate is not None:
                response, output_block_category, output_action = await _apply_output_security(
                    response, self._output_security_gate, self._security_response_agent
                )
            if output_block_category is not None and output_action is not None and result.status is not OrchestrationStatus.SECURITY_BLOCKED:
                audit_output = getattr(self._orchestrator, "audit_output_security_block", None)
                if audit_output is not None:
                    try:
                        audit_result = await audit_output(
                            message=request.message, context=audit_context, category=output_block_category,
                            action_taken=output_action,
                        )
                    except Exception:
                        raise ChatUnavailableError() from None
                    if audit_result.status is not SecurityAuditStatus.RECORDED:
                        raise ChatUnavailableError()
        if result.status in {
            OrchestrationStatus.ORCHESTRATION_ERROR,
            OrchestrationStatus.SECURITY_AUDIT_UNAVAILABLE,
        }:
            raise ChatUnavailableError()
        return response

    @staticmethod
    def _recovery_kind(result: OrchestrationResult) -> str | None:
        if result.status in {OrchestrationStatus.SECURITY_BLOCKED, OrchestrationStatus.ORCHESTRATION_ERROR, OrchestrationStatus.SECURITY_AUDIT_UNAVAILABLE}:
            return None
        knowledge = result.knowledge_result
        if knowledge is not None:
            if knowledge.status.value == "INSUFFICIENT_EVIDENCE":
                return "INSUFFICIENT_EVIDENCE"
            if knowledge.status.value == "PROVIDER_ERROR":
                return "PROVIDER_UNAVAILABLE"
        support = result.customer_support_result
        if support is not None:
            if support.status.value == "CLARIFICATION_REQUIRED":
                return "CLARIFICATION_REQUIRED"
            if support.status.value in {"NOT_FOUND", "INVALID_INPUT"}:
                return "NOT_FOUND"
            if support.status.value in {"OPERATIONAL_UNAVAILABLE", "PROVIDER_ERROR"}:
                return "PROVIDER_UNAVAILABLE"
        if result.status is OrchestrationStatus.WEB_FALLBACK_PENDING:
            return "PROVIDER_UNAVAILABLE"
        if result.status is OrchestrationStatus.MISSING_OPERATIONAL_CONTEXT:
            return "CLARIFICATION_REQUIRED"
        return None

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
            operation=(CustomerSupportOperation(context.operation.value) if context.operation else None),
            run_id=context.run_id,
            transient=context.transient,
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
    def _response(result: OrchestrationResult, *, security_answer: str | None = None) -> ChatResponse:
        if result.status is OrchestrationStatus.SECURITY_BLOCKED:
            return ChatResponse(
                status=result.status.value,
                route=result.route.value,
                answer=security_answer or _SECURITY_BLOCK_FALLBACK,
                reason="SECURITY_REQUEST_BLOCKED",
            )
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
                operational_plan=result.customer_support_result.plan,
                selected_protocol_number=result.customer_support_result.selected_protocol_number,
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
        elif support is not None and knowledge is not None and result.route is RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT:
            direct_answer = support.answer
            citations = knowledge.citations
        elif result.conversational_result is not None and knowledge is None and support is None:
            direct_answer = _safe_text(result.conversational_result.answer)
        elif result.direct_general_result is not None and result.direct_general_result.status == "ANSWERED" and knowledge is None and support is None:
            direct_answer = _safe_text(result.direct_general_result.answer)
        elif result.ambiguous_response is not None and knowledge is None and support is None:
            direct_answer = _safe_text(result.ambiguous_response.answer)
        return ChatResponse(
            status=result.status.value,
            route=result.route.value,
            intent=result.semantic_intent,
            answer=direct_answer,
            citations=citations,
            knowledge=knowledge,
            customer_support=support,
            requires_human=result.human_escalation_required,
            human=human,
            reason=_safe_reason(result.reason),
        )
