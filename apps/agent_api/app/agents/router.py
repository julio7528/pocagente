"""Typed, decision-only Router capability for approved Phase 9 routes."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RouterCapability(StrEnum):
    """Only application capabilities approved by the Phase 9 SDD."""

    KNOWLEDGE = "KNOWLEDGE"
    CUSTOMER_SUPPORT = "CUSTOMER_SUPPORT"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"
    WEB_FALLBACK = "WEB_FALLBACK"
    SECURITY_GUARDRAIL = "SECURITY_GUARDRAIL"


class RouterRoute(StrEnum):
    """Controlled capability decisions; never tool or agent implementation names."""

    KNOWLEDGE = "KNOWLEDGE"
    CUSTOMER_SUPPORT = "CUSTOMER_SUPPORT"
    KNOWLEDGE_AND_CUSTOMER_SUPPORT = "KNOWLEDGE_AND_CUSTOMER_SUPPORT"
    KNOWLEDGE_WITH_WEB_FALLBACK = "KNOWLEDGE_WITH_WEB_FALLBACK"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"
    SECURITY_BLOCK = "SECURITY_BLOCK"
    AMBIGUOUS = "AMBIGUOUS"


class RouterStatus(StrEnum):
    """Observable safe outcomes of one primary capability decision."""

    ROUTED = "ROUTED"
    SECURITY_BLOCKED = "SECURITY_BLOCKED"
    AMBIGUOUS = "AMBIGUOUS"


class WebSearchPolicy(StrEnum):
    """Trusted routing metadata; graph edges never rediscover this from user text."""

    NONE = "NONE"
    REQUIRED = "REQUIRED"
    FALLBACK_IF_RAG_INSUFFICIENT = "FALLBACK_IF_RAG_INSUFFICIENT"


class RouterRequest(BaseModel):
    """Narrow routing input without OPS facts, repositories, or user-selected tools."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message: str
    has_authorized_protocol_context: bool = False


class RouterDecision(BaseModel):
    """Immutable decision for future orchestration; it contains no business answer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: RouterStatus
    route: RouterRoute
    capabilities: tuple[RouterCapability, ...] = ()
    web_search_policy: WebSearchPolicy = WebSearchPolicy.NONE
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def fields_match_route(self) -> RouterDecision:
        expected = {
            RouterRoute.KNOWLEDGE: (RouterStatus.ROUTED, (RouterCapability.KNOWLEDGE,)),
            RouterRoute.CUSTOMER_SUPPORT: (RouterStatus.ROUTED, (RouterCapability.CUSTOMER_SUPPORT,)),
            RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT: (
                RouterStatus.ROUTED,
                (RouterCapability.KNOWLEDGE, RouterCapability.CUSTOMER_SUPPORT),
            ),
            RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK: (
                RouterStatus.ROUTED,
                (RouterCapability.KNOWLEDGE, RouterCapability.WEB_FALLBACK),
            ),
            RouterRoute.HUMAN_ESCALATION: (
                RouterStatus.ROUTED,
                (RouterCapability.HUMAN_ESCALATION,),
            ),
            RouterRoute.SECURITY_BLOCK: (
                RouterStatus.SECURITY_BLOCKED,
                (RouterCapability.SECURITY_GUARDRAIL,),
            ),
            RouterRoute.AMBIGUOUS: (RouterStatus.AMBIGUOUS, ()),
        }
        status, capabilities = expected[self.route]
        if self.status is not status or self.capabilities != capabilities:
            raise ValueError("router decision fields do not match the approved route")
        if self.route is RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK and self.web_search_policy is not WebSearchPolicy.REQUIRED:
            raise ValueError("current-information route requires live web search")
        if self.route is not RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK and self.web_search_policy is WebSearchPolicy.REQUIRED:
            raise ValueError("only the approved current-information route requires live web search")
        return self


class RouterAgent:
    """Classify only approved capabilities; never execute agents, tools, or SQL."""

    _SECURITY_PATTERN = re.compile(
        r"password|api[_ -]?key|deepseek[_ -]?api[_ -]?key|connection string|"
        r"database connection|credential|secret|bypass authentication|sqlagent|"
        r"secretagent|rootaccessagent|select\s+.+\s+from",
        re.IGNORECASE,
    )
    _HUMAN_PATTERN = re.compile(
        r"talk to (?:a )?(?:person|human)|human support|transfer me to (?:a )?human|"
        r"falar com (?:uma )?(?:pessoa|humano)|atendente humano",
        re.IGNORECASE,
    )
    _CURRENT_PATTERN = re.compile(
        r"weather|forecast|exchange rate|today(?:'s)? news|\btoday\b|\btomorrow\b|"
        r"previs[aã]o do tempo|taxa de c[aâ]mbio|not[ií]cias de hoje|\bhoje\b|\bamanh[aã]\b",
        re.IGNORECASE,
    )
    _SUPPORT_PATTERN = re.compile(
        r"\bprotocol\b|\bprotocolo\b|\bexecution\b|\bexecu[cç][aã]o\b|\brun\b|"
        r"cancelamento|cancellation|falha|failed|failure|delayed|atrasado",
        re.IGNORECASE,
    )
    _CONDITIONAL_SUPPORT_PATTERN = re.compile(
        r"yesterday'?s sales|vendas de ontem|card machine|maquininha|transaction decline|"
        r"recusa de transa[cç][aã]o|decline error|n[aã]o conecta",
        re.IGNORECASE,
    )
    _KNOWLEDGE_PATTERN = re.compile(
        r"how does|what'?s the difference|"
        r"get cl[aá]ssica|get smart|\bpix\b|receivables|antecipa[cç][aã]o|credi[aá]rio|"
        r"payment link|whatsapp|produto|processo|regra|como funciona|diferen[cç]a",
        re.IGNORECASE,
    )
    _DOCUMENTED_KNOWLEDGE_PATTERN = re.compile(
        r"approved .{0,80}(?:process|rule)|documented .{0,80}(?:process|rule)|business rule|"
        r"processo documentado|regra documentada|regra de neg[oó]cio",
        re.IGNORECASE,
    )

    def route(self, request: RouterRequest) -> RouterDecision:
        """Return a controlled decision without running the selected capability."""

        message = request.message.strip()
        if not message:
            return self._decision(RouterRoute.AMBIGUOUS, "ROUTER_MESSAGE_BLANK")
        if self._SECURITY_PATTERN.search(message):
            return self._decision(RouterRoute.SECURITY_BLOCK, "SECURITY_POLICY_ROUTE")
        if self._HUMAN_PATTERN.search(message):
            return self._decision(RouterRoute.HUMAN_ESCALATION, "EXPLICIT_HUMAN_REQUEST")
        expected_vs_observed = re.search(
            r"\bdelayed\b|\batrasado\b|deveria ter acontecido|what should have happened",
            message,
            re.IGNORECASE,
        )
        if request.has_authorized_protocol_context and expected_vs_observed:
            return self._decision(
                RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT,
                "EXPECTED_AND_OBSERVED_OPERATIONAL_STATE",
            )
        if expected_vs_observed and re.search(r"\bprotocol\b|\bprotocolo\b", message, re.IGNORECASE):
            return self._decision(RouterRoute.AMBIGUOUS, "AUTHORIZED_PROTOCOL_CONTEXT_REQUIRED")
        if self._CURRENT_PATTERN.search(message):
            return self._decision(RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK, "CURRENT_PUBLIC_INFORMATION")
        if self._DOCUMENTED_KNOWLEDGE_PATTERN.search(message):
            return self._decision(RouterRoute.KNOWLEDGE, "DOCUMENTED_OR_PRODUCT_KNOWLEDGE")
        if self._SUPPORT_PATTERN.search(message):
            return self._decision(RouterRoute.CUSTOMER_SUPPORT, "CONTROLLED_OPERATIONAL_EVIDENCE_REQUIRED")
        if self._CONDITIONAL_SUPPORT_PATTERN.search(message):
            return self._decision(
                RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT,
                "KNOWLEDGE_WITH_CONDITIONAL_CUSTOMER_SUPPORT",
            )
        if self._KNOWLEDGE_PATTERN.search(message):
            policy = (
                WebSearchPolicy.FALLBACK_IF_RAG_INSUFFICIENT
                if re.search(r"payment link|whatsapp", message, re.IGNORECASE)
                else WebSearchPolicy.NONE
            )
            return self._decision(RouterRoute.KNOWLEDGE, "DOCUMENTED_OR_PRODUCT_KNOWLEDGE", policy)
        return self._decision(RouterRoute.AMBIGUOUS, "ROUTER_ROUTE_UNDETERMINED")

    @staticmethod
    def _decision(
        route: RouterRoute,
        reason: str,
        web_search_policy: WebSearchPolicy = WebSearchPolicy.NONE,
    ) -> RouterDecision:
        routes = {
            RouterRoute.KNOWLEDGE: (RouterStatus.ROUTED, (RouterCapability.KNOWLEDGE,)),
            RouterRoute.CUSTOMER_SUPPORT: (RouterStatus.ROUTED, (RouterCapability.CUSTOMER_SUPPORT,)),
            RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT: (
                RouterStatus.ROUTED,
                (RouterCapability.KNOWLEDGE, RouterCapability.CUSTOMER_SUPPORT),
            ),
            RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK: (
                RouterStatus.ROUTED,
                (RouterCapability.KNOWLEDGE, RouterCapability.WEB_FALLBACK),
            ),
            RouterRoute.HUMAN_ESCALATION: (
                RouterStatus.ROUTED,
                (RouterCapability.HUMAN_ESCALATION,),
            ),
            RouterRoute.SECURITY_BLOCK: (
                RouterStatus.SECURITY_BLOCKED,
                (RouterCapability.SECURITY_GUARDRAIL,),
            ),
            RouterRoute.AMBIGUOUS: (RouterStatus.AMBIGUOUS, ()),
        }
        status, capabilities = routes[route]
        if route is RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK:
            web_search_policy = WebSearchPolicy.REQUIRED
        return RouterDecision(
            status=status,
            route=route,
            capabilities=capabilities,
            web_search_policy=web_search_policy,
            reason=reason,
        )
