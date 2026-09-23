"""LangGraph coordination over the approved Router and specialized agents."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.agent_api.app.agents.customer_support import (
    CustomerSupportOperation,
    CustomerSupportRequest,
    CustomerSupportResult,
    CustomerSupportStatus,
)
from apps.agent_api.app.agents.conversational import ConversationalResult, bounded_conversational_response
from apps.agent_api.app.agents.knowledge import KnowledgeRequest, KnowledgeResult, KnowledgeResultStatus
from apps.agent_api.app.agents.human_escalation import (
    HumanEscalationAction,
    HumanEscalationAgent,
    HumanEscalationRequest,
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
from apps.agent_api.app.rag.scope import KnowledgeScope
from apps.agent_api.app.tools.ops import OpsAccessContext
from apps.agent_api.app.security.models import (
    SecurityAuditContext,
    SecurityAuditResult,
    SecurityAuditStatus,
    SecurityClassification,
)


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

    async def answer(self, question: str) -> KnowledgeResult:
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
    ) -> SecurityAuditResult: ...


class CustomerSupportContext(BaseModel):
    """Trusted application context needed before Customer Support can run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_number: str = Field(min_length=1)
    operation: CustomerSupportOperation
    authorization: OpsAccessContext
    run_id: int | None = Field(default=None, gt=0)


class OrchestrationRequest(BaseModel):
    """Narrow graph input; authorization is supplied only by trusted application code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message: str = Field(min_length=1)
    has_authorized_protocol_context: bool = False
    customer_support_context: CustomerSupportContext | None = None
    human_escalation_request: HumanEscalationRequest | None = None
    security_audit_context: SecurityAuditContext | None = None


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
    knowledge_scope: KnowledgeScope = KnowledgeScope.NONE
    conversational_result: ConversationalResult | None = None
    knowledge_result: KnowledgeResult | None = None
    persistent_knowledge_result: KnowledgeResult | None = None
    web_knowledge_result: KnowledgeResult | None = None
    customer_support_result: CustomerSupportResult | None = None
    web_fallback_required: bool = False
    live_web_evidence_used: bool = False
    human_escalation_required: bool = False
    human_escalation_result: HumanEscalationResult | None = None
    reason: str = Field(min_length=1)

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
    ) -> None:
        self._router = router
        self._knowledge_agent = knowledge_agent
        self._customer_support_agent = customer_support_agent
        self._web_knowledge_agent = web_knowledge_agent
        self._human_escalation_agent = human_escalation_agent
        self._security_audit_service = security_audit_service
        self._graph = self._build_graph()

    async def execute(self, request: OrchestrationRequest) -> OrchestrationResult:
        """Run one bounded graph execution and return a framework-independent result."""

        try:
            state = await self._graph.ainvoke({"request": request})
        except Exception:
            return OrchestrationResult(
                status=OrchestrationStatus.ORCHESTRATION_ERROR,
                route=RouterRoute.AMBIGUOUS,
                reason="ORCHESTRATION_UNAVAILABLE",
            )
        return OrchestrationResult(
            status=state["status"],
            route=state["routing_decision"].route,
            knowledge_scope=state["knowledge_scope"],
            conversational_result=state.get("conversational_result"),
            knowledge_result=state.get("knowledge_result"),
            persistent_knowledge_result=state.get("persistent_knowledge_result"),
            web_knowledge_result=state.get("web_knowledge_result"),
            customer_support_result=state.get("customer_support_result"),
            web_fallback_required=state.get("web_fallback_required", False),
            live_web_evidence_used=state.get("live_web_evidence_used", False),
            human_escalation_required=state.get("human_escalation_required", False),
            human_escalation_result=state.get("human_escalation_result"),
            reason=state["reason"],
        )

    def _build_graph(self):
        graph = StateGraph(OrchestrationState)
        graph.add_node("router", self._router_node)
        graph.add_node("conversational", self._conversational_node)
        graph.add_node("knowledge", self._knowledge_node)
        graph.add_node("customer_support", self._customer_support_node)
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
                "customer_support": "customer_support",
                "cooperative": "knowledge",
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
                "assembly": "assembly",
            },
        )
        graph.add_conditional_edges(
            "customer_support",
            self._route_after_customer_support,
            {"human": "human_escalation", "assembly": "assembly"},
        )
        graph.add_edge("web_knowledge", "assembly")
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
            has_authorized_protocol_context=request.has_authorized_protocol_context,
        )
        route_async = getattr(self._router, "route_async", None)
        if route_async is None:
            # Compatibility for narrow deterministic test doubles.  The real
            # RouterAgent always exposes the native async seam.
            decision = self._router.route(router_request)
        else:
            decision = await route_async(router_request)
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
        return "human" if human is not None and human.action is HumanEscalationAction.OFFER else "assembly"

    @staticmethod
    def _route_after_knowledge(state: OrchestrationState) -> str:
        if state["routing_decision"].route is RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT:
            return "customer_support"
        if (
            state["routing_decision"].web_search_policy
            is WebSearchPolicy.FALLBACK_IF_RAG_INSUFFICIENT
            and state["knowledge_result"].status is KnowledgeResultStatus.INSUFFICIENT_EVIDENCE
        ):
            return "web_fallback"
        return "assembly"

    async def _knowledge_node(self, state: OrchestrationState) -> dict[str, KnowledgeResult]:
        try:
            result = await self._knowledge_agent.answer(
                KnowledgeRequest(
                    question=state["request"].message,
                    knowledge_scope=state["knowledge_scope"],
                )
            )
        except Exception:
            result = KnowledgeResult(
                question=state["request"].message,
                status=KnowledgeResultStatus.PROVIDER_ERROR,
                reason="KNOWLEDGE_CAPABILITY_UNAVAILABLE",
            )
        return {"knowledge_result": result, "persistent_knowledge_result": result}

    @staticmethod
    def _conversational_node(state: OrchestrationState) -> dict[str, ConversationalResult]:
        del state
        return {"conversational_result": bounded_conversational_response()}

    async def _web_knowledge_node(
        self, state: OrchestrationState
    ) -> dict[str, KnowledgeResult | OrchestrationStatus | str | bool]:
        if self._web_knowledge_agent is None:
            return {
                "status": OrchestrationStatus.WEB_FALLBACK_PENDING,
                "reason": "WEB_SEARCH_CAPABILITY_UNAVAILABLE",
                "web_fallback_required": True,
            }
        try:
            result = await self._web_knowledge_agent.answer(state["request"].message)
        except Exception:
            result = KnowledgeResult(
                question=state["request"].message,
                status=KnowledgeResultStatus.PROVIDER_ERROR,
                reason="WEB_KNOWLEDGE_CAPABILITY_UNAVAILABLE",
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
        if context is None:
            return {
                "customer_support_result": CustomerSupportResult(
                    status=CustomerSupportStatus.INVALID_INPUT,
                    reason="MISSING_TRUSTED_OPERATIONAL_CONTEXT",
                ),
                "status": OrchestrationStatus.MISSING_OPERATIONAL_CONTEXT,
                "reason": "MISSING_TRUSTED_OPERATIONAL_CONTEXT",
            }
        try:
            result = await self._customer_support_agent.answer(
                CustomerSupportRequest(
                    question=state["request"].message,
                    protocol_number=context.protocol_number,
                    operation=context.operation,
                    authorization=context.authorization,
                    run_id=context.run_id,
                )
            )
        except Exception:
            result = CustomerSupportResult(
                status=CustomerSupportStatus.OPERATIONAL_UNAVAILABLE,
                reason="CUSTOMER_SUPPORT_CAPABILITY_UNAVAILABLE",
            )
        return {"customer_support_result": result}

    async def _security_terminal(
        self, state: OrchestrationState
    ) -> dict[str, OrchestrationStatus | str]:
        context = state["request"].security_audit_context
        if self._security_audit_service is None or context is None:
            return {
                "status": OrchestrationStatus.SECURITY_AUDIT_UNAVAILABLE,
                "reason": "SECURITY_AUDIT_UNAVAILABLE",
            }
        result = await self._security_audit_service.record_router_security_block(
            message=state["request"].message,
            context=context,
            security_semantics=state["routing_decision"].security_semantics,
        )
        if result.status is not SecurityAuditStatus.RECORDED:
            return {
                "status": OrchestrationStatus.SECURITY_AUDIT_UNAVAILABLE,
                "reason": "SECURITY_AUDIT_UNAVAILABLE",
            }
        return {"status": OrchestrationStatus.SECURITY_BLOCKED, "reason": "SECURITY_POLICY_ROUTE"}

    @staticmethod
    def _ambiguous_terminal(state: OrchestrationState) -> dict[str, OrchestrationStatus | str]:
        return {
            "status": OrchestrationStatus.AMBIGUOUS,
            "reason": state["routing_decision"].reason,
        }

    def _human_escalation_node(
        self, state: OrchestrationState
    ) -> dict[str, HumanEscalationResult | OrchestrationStatus | str | bool]:
        request = state["request"].human_escalation_request
        if self._human_escalation_agent is None or request is None:
            return {
                "status": OrchestrationStatus.HUMAN_ESCALATION_REQUIRED,
                "reason": "HUMAN_ESCALATION_CAPABILITY_OR_TRUSTED_CONTEXT_UNAVAILABLE",
                "human_escalation_required": True,
            }
        result = self._human_escalation_agent.transition(request)
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
        if conversational is not None:
            return {"status": OrchestrationStatus.COMPLETED, "reason": conversational.reason}
        knowledge_ok = knowledge is None or knowledge.status is KnowledgeResultStatus.ANSWERED
        support_ok = customer_support is None or customer_support.status is CustomerSupportStatus.ANSWERED
        if knowledge_ok and support_ok:
            return {"status": OrchestrationStatus.COMPLETED, "reason": "CAPABILITIES_COMPLETED"}
        return {"status": OrchestrationStatus.PARTIAL, "reason": "CAPABILITY_CONTROLLED_FAILURE"}
