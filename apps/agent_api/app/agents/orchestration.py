"""LangGraph coordination over the approved Router and specialized agents."""

from __future__ import annotations

from enum import StrEnum
from time import perf_counter
from typing import Literal, Protocol, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.agent_api.app.agents.customer_support import (
    CustomerSupportOperation,
    CustomerSupportRequest,
    CustomerSupportResult,
    CustomerSupportStatus,
)
from apps.agent_api.app.agents.conversational import ConversationalAgent, ConversationalResult, DirectGeneralResult, bounded_conversational_response
from apps.agent_api.app.agents.conversation_context import (
    ConversationContextMessage,
    validate_context_window,
)
from apps.agent_api.app.agents.knowledge import KnowledgeRequest, KnowledgeResult, KnowledgeResultStatus
from apps.agent_api.app.agents.human_escalation import (
    HumanEscalationAction,
    HumanEscalationAgent,
    ConversationReference,
    HumanEscalationRequest,
    HumanEscalationReason,
    HumanEscalationResult,
    HumanEscalationState,
)
from apps.agent_api.app.agents.router import (
    RouterAgent,
    RouterDecision,
    RouterRequest,
    RouterRoute,
    WebSearchPolicy,
)
from apps.agent_api.app.agents.semantic_routing import SemanticIntent
from apps.agent_api.app.rag.scope import KnowledgeScope
from apps.agent_api.app.tools.ops import OpsAccessContext
from apps.agent_api.app.security.models import (
    SecurityAction as AuditAction,
    SecurityAuditContext,
    SecurityAuditResult,
    SecurityAuditStatus,
    SecurityClassification,
)
from apps.agent_api.app.security.semantic import SecurityCategory
from apps.agent_api.app.telemetry import RuntimeEventKind, emit_runtime_event


class KnowledgeCapability(Protocol):
    """Approved Knowledge boundary consumed by the graph."""

    async def answer(self, request: KnowledgeRequest) -> KnowledgeResult:
        """Return the existing typed Knowledge result."""


class CustomerSupportCapability(Protocol):
    """Approved Customer Support boundary consumed by the graph."""

    async def answer(self, request: CustomerSupportRequest) -> CustomerSupportResult:
        """Return the existing typed Customer Support result."""


class WebKnowledgeCapability(Protocol):
    """Controlled live-public Knowledge boundary used only for approved web routes."""

    async def answer(
        self, question: str, *, knowledge_scope: KnowledgeScope = KnowledgeScope.NONE,
        search_query: str | None = None,
        conversation_context: tuple[ConversationContextMessage, ...] = (),
    ) -> KnowledgeResult:
        """Return a typed result based on non-persistent live web evidence."""


class HumanEscalationCapability(Protocol):
    """Trusted application-owned handoff state transition boundary."""

    def transition(self, request: HumanEscalationRequest) -> HumanEscalationResult:
        """Perform one explicit, non-persistent approved transition."""


class SecurityAuditCapability(Protocol):
    """Approved application audit boundary invoked only after router blocking."""

    async def record_router_security_block(
        self,
        *,
        message: str,
        context: SecurityAuditContext,
        security_semantics: tuple[SecurityClassification, ...],
        source_component: str = "router_security_guardrail",
        action_taken: AuditAction = AuditAction.BLOCK,
    ) -> SecurityAuditResult: ...


class CustomerSupportContext(BaseModel):
    """Optional preselected business selectors; contains no authorization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_number: str | None = Field(default=None, min_length=1)
    operation: CustomerSupportOperation | None = None
    run_id: int | None = Field(default=None, gt=0)
    transient: bool = False


class OrchestrationRequest(BaseModel):
    """Narrow graph input; authorization is supplied only by trusted application code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message: str = Field(min_length=1)
    # Opaque request correlation only; never an authority claim or portal lookup.
    conversation_id: str | None = Field(default=None, min_length=1, max_length=128)
    ops_access_context: OpsAccessContext | None = None
    customer_support_context: CustomerSupportContext | None = None
    analytics_grain_context: Literal["PROTOCOL", "EXECUTION", "EVENT"] | None = None
    human_escalation_request: HumanEscalationRequest | None = None
    security_audit_context: SecurityAuditContext | None = None
    conversation_context: tuple[ConversationContextMessage, ...] = Field(
        default=(), max_length=12
    )

    @model_validator(mode="after")
    def context_is_bounded_data(self) -> OrchestrationRequest:
        validate_context_window(self.conversation_context)
        return self


class OrchestrationStatus(StrEnum):
    """Safe graph outcomes suitable for a future HTTP adapter."""

    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    SECURITY_BLOCKED = "SECURITY_BLOCKED"
    SECURITY_AUDIT_UNAVAILABLE = "SECURITY_AUDIT_UNAVAILABLE"
    AMBIGUOUS = "AMBIGUOUS"
    WEB_FALLBACK_PENDING = "WEB_FALLBACK_PENDING"
    HUMAN_ESCALATION_REQUIRED = "HUMAN_ESCALATION_REQUIRED"
    HUMAN_ESCALATION_REJECTED = "HUMAN_ESCALATION_REJECTED"
    HUMAN_OWNERSHIP_ACTIVE = "HUMAN_OWNERSHIP_ACTIVE"
    MISSING_OPERATIONAL_CONTEXT = "MISSING_OPERATIONAL_CONTEXT"
    ORCHESTRATION_ERROR = "ORCHESTRATION_ERROR"


class OrchestrationResult(BaseModel):
    """Typed aggregation that preserves specialized results without semantic merging."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: OrchestrationStatus
    route: RouterRoute
    semantic_intent: SemanticIntent | None = None
    knowledge_scope: KnowledgeScope = KnowledgeScope.NONE
    conversational_result: ConversationalResult | None = None
    direct_general_result: DirectGeneralResult | None = None
    ambiguous_response: ConversationalResult | None = None
    knowledge_result: KnowledgeResult | None = None
    persistent_knowledge_result: KnowledgeResult | None = None
    web_knowledge_result: KnowledgeResult | None = None
    customer_support_result: CustomerSupportResult | None = None
    web_fallback_required: bool = False
    live_web_evidence_used: bool = False
    human_escalation_required: bool = False
    human_escalation_result: HumanEscalationResult | None = None
    reason: str = Field(min_length=1)
    security_semantics: tuple[SecurityClassification, ...] = ()

    @model_validator(mode="after")
    def conversational_result_is_exclusive(self) -> OrchestrationResult:
        if self.conversational_result is not None:
            if self.route is not RouterRoute.CONVERSATIONAL or self.status is not OrchestrationStatus.COMPLETED:
                raise ValueError("conversational result requires a completed conversational route")
            if any((
                self.knowledge_result,
                self.persistent_knowledge_result,
                self.web_knowledge_result,
                self.customer_support_result,
                self.human_escalation_result,
            )):
                raise ValueError("conversational result cannot include other capability results")
            if (
                self.knowledge_scope is not KnowledgeScope.NONE
                or self.human_escalation_required
                or self.web_fallback_required
                or self.live_web_evidence_used
            ):
                raise ValueError("conversational result cannot carry capability authority")
        return self


class OrchestrationState(TypedDict, total=False):
    """Only request, decision, typed results, and controlled graph outcome state."""

    request: OrchestrationRequest
    routing_decision: RouterDecision
    knowledge_scope: KnowledgeScope
    conversational_result: ConversationalResult
    direct_general_result: DirectGeneralResult
    ambiguous_response: ConversationalResult
    knowledge_result: KnowledgeResult
    persistent_knowledge_result: KnowledgeResult
    web_knowledge_result: KnowledgeResult
    customer_support_result: CustomerSupportResult
    status: OrchestrationStatus
    reason: str
    web_fallback_required: bool
    live_web_evidence_used: bool
    human_escalation_required: bool
    human_escalation_result: HumanEscalationResult


class LangGraphOrchestrator:
    """Acyclic coordinator; all capability behavior remains in injected agents."""

    def __init__(
        self,
        router: RouterAgent,
        knowledge_agent: KnowledgeCapability,
        customer_support_agent: CustomerSupportCapability,
        web_knowledge_agent: WebKnowledgeCapability | None = None,
        human_escalation_agent: HumanEscalationCapability | None = None,
        security_audit_service: SecurityAuditCapability | None = None,
        conversational_agent: ConversationalAgent | None = None,
    ) -> None:
        self._router = router
        self._knowledge_agent = knowledge_agent
        self._customer_support_agent = customer_support_agent
        self._web_knowledge_agent = web_knowledge_agent
        self._human_escalation_agent = human_escalation_agent
        self._security_audit_service = security_audit_service
        self._conversational_agent = conversational_agent
        self._graph = self._build_graph()

    async def execute(self, request: OrchestrationRequest) -> OrchestrationResult:
        """Run one bounded graph execution and return a framework-independent result."""

        started_at = perf_counter()
        try:
            state = await self._graph.ainvoke({"request": request})
        except Exception:
            emit_runtime_event(
                RuntimeEventKind.ORCHESTRATION,
                value=OrchestrationStatus.ORCHESTRATION_ERROR.value,
                elapsed_ms=int((perf_counter() - started_at) * 1000),
            )
            return OrchestrationResult(
                status=OrchestrationStatus.ORCHESTRATION_ERROR,
                route=RouterRoute.AMBIGUOUS,
                reason="ORCHESTRATION_UNAVAILABLE",
            )
        result = OrchestrationResult(
            status=state["status"],
            route=state["routing_decision"].route,
            semantic_intent=state["routing_decision"].semantic_intent,
            knowledge_scope=state["knowledge_scope"],
            conversational_result=state.get("conversational_result"),
            direct_general_result=state.get("direct_general_result"),
            ambiguous_response=state.get("ambiguous_response"),
            knowledge_result=state.get("knowledge_result"),
            persistent_knowledge_result=state.get("persistent_knowledge_result"),
            web_knowledge_result=state.get("web_knowledge_result"),
            customer_support_result=state.get("customer_support_result"),
            web_fallback_required=state.get("web_fallback_required", False),
            live_web_evidence_used=state.get("live_web_evidence_used", False),
            human_escalation_required=state.get("human_escalation_required", False),
            human_escalation_result=state.get("human_escalation_result"),
            reason=state["reason"],
            security_semantics=state["routing_decision"].security_semantics,
        )
        emit_runtime_event(
            RuntimeEventKind.ORCHESTRATION,
            value=result.status.value,
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        return result

    async def audit_output_security_block(
        self, *, message: str, context: SecurityAuditContext, category: SecurityCategory,
        action_taken: AuditAction = AuditAction.BLOCK,
    ) -> SecurityAuditResult:
        """Persist a sanitized outbound-policy event through the existing AUDIT boundary."""
        if self._security_audit_service is None:
            return SecurityAuditResult(status=SecurityAuditStatus.UNAVAILABLE, reason="SECURITY_AUDIT_UNAVAILABLE")
        semantics = RouterAgent._semantic_security_audit_semantics(category)
        if not semantics:
            return SecurityAuditResult(status=SecurityAuditStatus.UNAVAILABLE, reason="SECURITY_AUDIT_CATEGORY_UNAVAILABLE")
        try:
            return await self._security_audit_service.record_router_security_block(
                message=message, context=context, security_semantics=semantics,
                source_component="output_security_gate",
                action_taken=action_taken,
            )
        except Exception:
            return SecurityAuditResult(status=SecurityAuditStatus.UNAVAILABLE, reason="SECURITY_AUDIT_UNAVAILABLE")

    def _build_graph(self):
        graph = StateGraph(OrchestrationState)
        graph.add_node("router", self._router_node)
        graph.add_node("conversational", self._conversational_node)
        graph.add_node("direct_general", self._direct_general_node)
        graph.add_node("knowledge", self._knowledge_node)
        graph.add_node("customer_support", self._customer_support_node)
        graph.add_node("cooperative_synthesis", self._cooperative_synthesis_node)
        graph.add_node("web_knowledge", self._web_knowledge_node)
        graph.add_node("security_terminal", self._security_terminal)
        graph.add_node("ambiguous_terminal", self._ambiguous_terminal)
        graph.add_node("human_escalation", self._human_escalation_node)
        graph.add_node("assembly", self._assembly_node)

        graph.add_edge(START, "router")
        graph.add_conditional_edges(
            "router",
            self._route_after_router,
            {
                "knowledge": "knowledge",
                "conversational": "conversational",
                "direct_general": "direct_general",
                "customer_support": "customer_support",
                "cooperative": "customer_support",
                "web_fallback": "web_knowledge",
                "human": "human_escalation",
                "security": "security_terminal",
                "ambiguous": "ambiguous_terminal",
            },
        )
        graph.add_conditional_edges(
            "knowledge",
            self._route_after_knowledge,
            {
                "customer_support": "customer_support",
                "web_fallback": "web_knowledge",
                "cooperative_synthesis": "cooperative_synthesis",
                "assembly": "assembly",
            },
        )
        graph.add_conditional_edges(
            "customer_support",
            self._route_after_customer_support,
            {"human": "human_escalation", "knowledge": "knowledge", "assembly": "assembly"},
        )
        graph.add_edge("cooperative_synthesis", "assembly")
        graph.add_edge("web_knowledge", "assembly")
        graph.add_conditional_edges("direct_general", self._route_after_direct_general, {"web": "web_knowledge", "assembly": "assembly"})
        graph.add_edge("conversational", "assembly")
        graph.add_edge("security_terminal", "assembly")
        graph.add_edge("ambiguous_terminal", "assembly")
        graph.add_edge("human_escalation", "assembly")
        graph.add_edge("assembly", END)
        return graph.compile()

    async def _router_node(self, state: OrchestrationState) -> dict[str, RouterDecision | KnowledgeScope]:
        request = state["request"]
        router_request = RouterRequest(
            message=request.message,
            conversation_context=request.conversation_context,
            protocol_context=(
                request.customer_support_context.protocol_number
                if request.customer_support_context is not None else None
            ),
            ops_read_authorized=(
                request.ops_access_context is not None
                and request.ops_access_context.can_read_operational_facts
            ),
        )
        route_async = getattr(self._router, "route_async", None)
        if route_async is None:
            # Compatibility for narrow deterministic test doubles.  The real
            # RouterAgent always exposes the native async seam.
            decision = self._router.route(router_request)
        else:
            decision = await route_async(router_request)
        emit_runtime_event(RuntimeEventKind.ROUTER, value=decision.route.value)
        for need in decision.semantic_capability_needs:
            emit_runtime_event(RuntimeEventKind.CAPABILITY_NEED, value=need.value)
        emit_runtime_event(RuntimeEventKind.KNOWLEDGE_SCOPE, value=decision.knowledge_scope.value)
        if decision.web_search_policy is not WebSearchPolicy.NONE:
            emit_runtime_event(RuntimeEventKind.WEB_POLICY, value=decision.web_search_policy.value)
        return {"routing_decision": decision, "knowledge_scope": decision.knowledge_scope}

    @staticmethod
    def _route_after_router(state: OrchestrationState) -> str:
        human = state["request"].human_escalation_request
        if state["routing_decision"].route is not RouterRoute.SECURITY_BLOCK and human is not None:
            if human.current_state is HumanEscalationState.HUMAN or human.action in {
                HumanEscalationAction.CONFIRM,
                HumanEscalationAction.ACCEPT,
                HumanEscalationAction.RETURN_TO_AUTOMATION,
                HumanEscalationAction.RESOLVE,
            }:
                return "human"
        route = state["routing_decision"].route
        return {
            RouterRoute.KNOWLEDGE: "knowledge",
            RouterRoute.CONVERSATIONAL: "conversational",
            RouterRoute.DIRECT_GENERAL: "direct_general",
            RouterRoute.CUSTOMER_SUPPORT: "customer_support",
            RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT: "cooperative",
            RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK: "web_fallback",
            RouterRoute.HUMAN_ESCALATION: "human",
            RouterRoute.SECURITY_BLOCK: "security",
            RouterRoute.AMBIGUOUS: "ambiguous",
        }[route]

    @staticmethod
    def _route_after_customer_support(state: OrchestrationState) -> str:
        human = state["request"].human_escalation_request
        if human is not None and human.action is HumanEscalationAction.OFFER:
            return "human"
        if state["routing_decision"].route is RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT:
            return "knowledge"
        return "assembly"

    @staticmethod
    def _route_after_knowledge(state: OrchestrationState) -> str:
        if state["routing_decision"].route is RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT:
            return "cooperative_synthesis"
        if (
            state["routing_decision"].web_search_policy
            is WebSearchPolicy.FALLBACK_IF_RAG_INSUFFICIENT
            and state["knowledge_result"].status is KnowledgeResultStatus.INSUFFICIENT_EVIDENCE
        ):
            return "web_fallback"
        return "assembly"

    async def _knowledge_node(self, state: OrchestrationState) -> dict[str, KnowledgeResult]:
        started_at = perf_counter()
        emit_runtime_event(RuntimeEventKind.CAPABILITY, name="KnowledgeAgent", value="STARTED")
        question = state["request"].message
        if state["routing_decision"].route is RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT:
            formulate = getattr(self._customer_support_agent, "formulate_internal_knowledge_query", None)
            if formulate is not None:
                try:
                    formulated = await formulate(
                        question,
                        state.get("customer_support_result"),
                        **({"conversation_context": state["request"].conversation_context}
                           if state["request"].conversation_context else {}),
                    )
                except Exception:
                    formulated = None
                if isinstance(formulated, str) and formulated.strip():
                    question = formulated
        try:
            result = await self._knowledge_agent.answer(
                KnowledgeRequest(
                    question=question,
                    knowledge_scope=state["knowledge_scope"],
                    conversation_context=state["request"].conversation_context,
                )
            )
        except Exception:
            result = KnowledgeResult(
                question=state["request"].message,
                status=KnowledgeResultStatus.PROVIDER_ERROR,
                reason="KNOWLEDGE_CAPABILITY_UNAVAILABLE",
            )
        emit_runtime_event(
            RuntimeEventKind.CAPABILITY,
            name="KnowledgeAgent",
            value=result.status.value,
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        return {"knowledge_result": result, "persistent_knowledge_result": result}

    async def _cooperative_synthesis_node(self, state: OrchestrationState) -> dict[str, CustomerSupportResult]:
        support = state.get("customer_support_result")
        knowledge = state.get("knowledge_result")
        synthesize = getattr(self._customer_support_agent, "synthesize_cooperative", None)
        if support is not None and knowledge is not None and synthesize is not None:
            try:
                support = await synthesize(
                    state["request"].message, support, knowledge,
                    **({"conversation_context": state["request"].conversation_context}
                       if state["request"].conversation_context else {}),
                )
            except Exception:
                pass
        return {"customer_support_result": support} if support is not None else {}

    async def _conversational_node(self, state: OrchestrationState) -> dict[str, ConversationalResult]:
        started_at = perf_counter()
        emit_runtime_event(RuntimeEventKind.CAPABILITY, name="ConversationalAgent", value="STARTED")
        if self._conversational_agent is None:
            result = bounded_conversational_response()
        else:
            result = await self._conversational_agent.respond(
                state["request"].message,
                conversation_context=state["request"].conversation_context,
            )
        emit_runtime_event(
            RuntimeEventKind.CAPABILITY,
            name="ConversationalAgent",
            value=result.reason,
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        return {"conversational_result": result}

    async def _web_knowledge_node(
        self, state: OrchestrationState
    ) -> dict[str, KnowledgeResult | OrchestrationStatus | str | bool]:
        started_at = perf_counter()
        emit_runtime_event(RuntimeEventKind.CAPABILITY, name="WebKnowledgeAgent", value="STARTED")
        if self._web_knowledge_agent is None:
            return {
                "status": OrchestrationStatus.WEB_FALLBACK_PENDING,
                "reason": "WEB_SEARCH_CAPABILITY_UNAVAILABLE",
                "web_fallback_required": True,
            }
        try:
            retrieval_result = state.get("knowledge_result")
            search_query = retrieval_result.retrieval_query if retrieval_result is not None else None
            if search_query is None:
                result = await self._web_knowledge_agent.answer(
                    state["request"].message,
                    knowledge_scope=state["knowledge_scope"],
                    **({"conversation_context": state["request"].conversation_context}
                       if state["request"].conversation_context else {}),
                )
            else:
                result = await self._web_knowledge_agent.answer(
                    state["request"].message,
                    knowledge_scope=state["knowledge_scope"],
                    search_query=search_query,
                    **({"conversation_context": state["request"].conversation_context}
                       if state["request"].conversation_context else {}),
                )
        except Exception:
            result = KnowledgeResult(
                question=state["request"].message,
                status=KnowledgeResultStatus.PROVIDER_ERROR,
                reason="WEB_KNOWLEDGE_CAPABILITY_UNAVAILABLE",
            )
        emit_runtime_event(
            RuntimeEventKind.CAPABILITY,
            name="WebKnowledgeAgent",
            value=result.status.value,
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        return {
            "knowledge_result": result,
            "web_knowledge_result": result,
            "live_web_evidence_used": result.status is KnowledgeResultStatus.ANSWERED,
        }

    async def _customer_support_node(
        self, state: OrchestrationState
    ) -> dict[str, CustomerSupportResult | OrchestrationStatus | str]:
        context = state["request"].customer_support_context
        authorization = state["request"].ops_access_context
        if authorization is None or not authorization.can_read_operational_facts:
            emit_runtime_event(RuntimeEventKind.OPS_AUTHORIZATION, value="DENIED")
            return {
                "customer_support_result": CustomerSupportResult(
                    status=CustomerSupportStatus.UNAUTHORIZED,
                    reason="OPERATIONAL_ACCESS_DENIED",
                ),
            }
        emit_runtime_event(RuntimeEventKind.OPS_AUTHORIZATION, value="ALLOWED")
        started_at = perf_counter()
        emit_runtime_event(RuntimeEventKind.CAPABILITY, name="CustomerSupportAgent", value="STARTED")
        follow_up_context_applies = (
            context is not None
            and (not context.transient or state["routing_decision"].reason == "AUTHORIZED_PROTOCOL_FOLLOW_UP_CONTEXT")
        )
        try:
            result = await self._customer_support_agent.answer(
                CustomerSupportRequest(
                    question=state["request"].message,
                    protocol_number=context.protocol_number if follow_up_context_applies else None,
                    operation=context.operation if follow_up_context_applies else None,
                    authorization=authorization,
                    run_id=context.run_id if follow_up_context_applies else None,
                    analytics_grain_context=state["request"].analytics_grain_context,
                    conversation_context=state["request"].conversation_context,
                )
            )
        except Exception:
            result = CustomerSupportResult(
                status=CustomerSupportStatus.OPERATIONAL_UNAVAILABLE,
                reason="CUSTOMER_SUPPORT_CAPABILITY_UNAVAILABLE",
            )
        emit_runtime_event(
            RuntimeEventKind.CAPABILITY,
            name="CustomerSupportAgent",
            value=result.status.value,
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        return {"customer_support_result": result}

    async def _security_terminal(
        self, state: OrchestrationState
    ) -> dict[str, OrchestrationStatus | str]:
        if not state["routing_decision"].security_audit_required:
            emit_runtime_event(RuntimeEventKind.SECURITY_AUDIT, value="TAXONOMY_UNAVAILABLE")
            emit_runtime_event(RuntimeEventKind.SECURITY, value="CONTINUATION_INTERRUPTED")
            return {
                "status": OrchestrationStatus.SECURITY_BLOCKED,
                "reason": "SECURITY_AUDIT_CATEGORY_UNAVAILABLE",
            }
        context = state["request"].security_audit_context
        emit_runtime_event(RuntimeEventKind.SECURITY_AUDIT, value="STARTED")
        if self._security_audit_service is None or context is None:
            emit_runtime_event(RuntimeEventKind.SECURITY_AUDIT, value="UNAVAILABLE")
            return {
                "status": OrchestrationStatus.SECURITY_AUDIT_UNAVAILABLE,
                "reason": "SECURITY_AUDIT_UNAVAILABLE",
            }
        audit_kwargs = {
            "message": state["request"].message,
            "context": context,
            "security_semantics": state["routing_decision"].security_semantics,
        }
        if state["routing_decision"].reason == "SEMANTIC_SECURITY_POLICY_BLOCK":
            audit_kwargs["source_component"] = "semantic_security_classifier"
        try:
            result = await self._security_audit_service.record_router_security_block(**audit_kwargs)
        except TypeError:
            # Compatibility for legacy narrow audit doubles; production service
            # accepts the safe source-component label.
            if "source_component" not in audit_kwargs:
                raise
            audit_kwargs.pop("source_component")
            result = await self._security_audit_service.record_router_security_block(**audit_kwargs)
        emit_runtime_event(
            RuntimeEventKind.SECURITY_AUDIT,
            value="RECORDED" if result.status is SecurityAuditStatus.RECORDED else "UNAVAILABLE",
        )
        if result.status is not SecurityAuditStatus.RECORDED:
            return {
                "status": OrchestrationStatus.SECURITY_AUDIT_UNAVAILABLE,
                "reason": "SECURITY_AUDIT_UNAVAILABLE",
            }
        emit_runtime_event(RuntimeEventKind.SECURITY, value="CONTINUATION_INTERRUPTED")
        return {"status": OrchestrationStatus.SECURITY_BLOCKED, "reason": "SECURITY_POLICY_ROUTE"}

    async def _ambiguous_terminal(self, state: OrchestrationState) -> dict[str, OrchestrationStatus | str | ConversationalResult]:
        if state["routing_decision"].reason != "SEMANTIC_AMBIGUOUS":
            return {"status": OrchestrationStatus.AMBIGUOUS, "reason": state["routing_decision"].reason}
        message = state["request"].message
        response = await self._conversational_agent.clarify(
            message,
            conversation_context=state["request"].conversation_context,
        ) if self._conversational_agent is not None else ConversationalResult(answer="Não consegui entender exatamente o que você quer. Pode me dar um pouco mais de contexto?", reason="BOUNDED_CONVERSATIONAL_RESPONSE")
        return {
            "status": OrchestrationStatus.AMBIGUOUS,
            "reason": state["routing_decision"].reason,
            "ambiguous_response": response,
        }

    async def _direct_general_node(self, state: OrchestrationState) -> dict[str, DirectGeneralResult]:
        started_at = perf_counter()
        emit_runtime_event(RuntimeEventKind.CAPABILITY, name="DirectGeneralAgent", value="STARTED")
        if self._conversational_agent is None:
            result = DirectGeneralResult(status="PROVIDER_ERROR")
        else:
            result = await self._conversational_agent.answer_general(
                state["request"].message,
                conversation_context=state["request"].conversation_context,
            )
        emit_runtime_event(RuntimeEventKind.CAPABILITY, name="DirectGeneralAgent", value=result.status, elapsed_ms=int((perf_counter() - started_at) * 1000))
        return {"direct_general_result": result}

    @staticmethod
    def _route_after_direct_general(state: OrchestrationState) -> str:
        result = state.get("direct_general_result")
        return "web" if result is not None and result.status == "REQUIRES_CURRENT_EVIDENCE" else "assembly"

    def _human_escalation_node(
        self, state: OrchestrationState
    ) -> dict[str, HumanEscalationResult | OrchestrationStatus | str | bool]:
        emit_runtime_event(RuntimeEventKind.CAPABILITY, name="HumanEscalationAgent", value="STARTED")
        request = state["request"].human_escalation_request
        if self._human_escalation_agent is None:
            return {
                "status": OrchestrationStatus.HUMAN_ESCALATION_REQUIRED,
                "reason": "HUMAN_ESCALATION_CAPABILITY_OR_TRUSTED_CONTEXT_UNAVAILABLE",
                "human_escalation_required": True,
            }
        if request is None:
            request = HumanEscalationRequest(
                conversation=ConversationReference(
                    conversation_id=state["request"].conversation_id or f"chat-{uuid4().hex}"
                ),
                current_state=HumanEscalationState.BOT,
                action=HumanEscalationAction.OFFER,
                reason=HumanEscalationReason.USER_REQUESTED_HUMAN,
            )
        result = self._human_escalation_agent.transition(request)
        emit_runtime_event(RuntimeEventKind.HUMAN, value=result.state.value)
        if result.status.value == "REJECTED":
            return {
                "human_escalation_result": result,
                "status": OrchestrationStatus.HUMAN_ESCALATION_REJECTED,
                "reason": result.reason,
                "human_escalation_required": True,
            }
        if result.status.value == "AUTOMATION_SUSPENDED":
            return {
                "human_escalation_result": result,
                "status": OrchestrationStatus.HUMAN_OWNERSHIP_ACTIVE,
                "reason": result.reason,
                "human_escalation_required": True,
            }
        return {
            "human_escalation_result": result,
            "human_escalation_required": True,
            "reason": result.reason,
        }

    @staticmethod
    def _assembly_node(state: OrchestrationState) -> dict[str, OrchestrationStatus | str]:
        if "status" in state:
            return {}
        knowledge = state.get("knowledge_result")
        customer_support = state.get("customer_support_result")
        conversational = state.get("conversational_result")
        direct_general = state.get("direct_general_result")
        if conversational is not None:
            return {"status": OrchestrationStatus.COMPLETED, "reason": conversational.reason}
        if direct_general is not None:
            if direct_general.status == "ANSWERED":
                return {"status": OrchestrationStatus.COMPLETED, "reason": "DIRECT_GENERAL_ANSWERED"}
            if direct_general.status == "PROVIDER_ERROR":
                return {"status": OrchestrationStatus.PARTIAL, "reason": "DIRECT_GENERAL_PROVIDER_ERROR"}
        knowledge_ok = knowledge is None or knowledge.status is KnowledgeResultStatus.ANSWERED
        support_ok = customer_support is None or customer_support.status is CustomerSupportStatus.ANSWERED
        if knowledge_ok and support_ok:
            return {"status": OrchestrationStatus.COMPLETED, "reason": "CAPABILITIES_COMPLETED"}
        return {"status": OrchestrationStatus.PARTIAL, "reason": "CAPABILITY_CONTROLLED_FAILURE"}
