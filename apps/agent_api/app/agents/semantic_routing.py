"""Typed semantic-routing contracts and deterministic policy mapping.

This module deliberately contains no provider implementation, tool execution,
repository access, or security classification.  It is the contract seam for a
later async semantic classifier.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from apps.agent_api.app.rag.scope import KnowledgeScope


class SemanticIntent(StrEnum):
    """Closed vocabulary understood by the future semantic classifier."""

    CONVERSATIONAL = "CONVERSATIONAL"
    INTERNAL_KNOWLEDGE = "INTERNAL_KNOWLEDGE"
    PUBLIC_GETNET_KNOWLEDGE = "PUBLIC_GETNET_KNOWLEDGE"
    CUSTOMER_SUPPORT = "CUSTOMER_SUPPORT"
    EXPECTED_VS_OBSERVED = "EXPECTED_VS_OBSERVED"
    GENERAL_PUBLIC_INFORMATION = "GENERAL_PUBLIC_INFORMATION"
    CURRENT_PUBLIC_INFORMATION = "CURRENT_PUBLIC_INFORMATION"
    HUMAN_REQUEST = "HUMAN_REQUEST"
    AMBIGUOUS = "AMBIGUOUS"


class SemanticClassification(BaseModel):
    """Strict provider-neutral semantic result with no policy authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    intent: SemanticIntent


class SemanticRoutingContext(BaseModel):
    """Trusted application context available to the deterministic mapper."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    has_authorized_protocol_context: bool = False


class SemanticIntentClassifier(Protocol):
    """Async semantic-only boundary for a future provider adapter."""

    async def classify(self, message: str) -> SemanticClassification:
        """Return one validated semantic intent without policy fields or tools."""


class SemanticClassifierError(RuntimeError):
    """Controlled classifier failure that must degrade without privilege."""


class SemanticIntentMapper:
    """Map validated intent plus trusted context to an approved RouterDecision."""

    @staticmethod
    def map(
        classification: SemanticClassification,
        context: SemanticRoutingContext | None = None,
    ):
        # Local imports keep the contract module independent from RouterAgent
        # and avoid a module cycle.  The mapper constructs policy, it never
        # calls the Router or executes any capability.
        from apps.agent_api.app.agents.router import (
            RouterCapability,
            RouterDecision,
            RouterRoute,
            RouterStatus,
            WebSearchPolicy,
        )

        trusted = context or SemanticRoutingContext()
        intent = classification.intent
        if intent is SemanticIntent.CONVERSATIONAL:
            return RouterDecision(
                status=RouterStatus.ROUTED,
                route=RouterRoute.CONVERSATIONAL,
                capabilities=(RouterCapability.CONVERSATIONAL,),
                knowledge_scope=KnowledgeScope.NONE,
                reason="SEMANTIC_CONVERSATIONAL",
            )
        if intent is SemanticIntent.INTERNAL_KNOWLEDGE:
            return RouterDecision(
                status=RouterStatus.ROUTED,
                route=RouterRoute.KNOWLEDGE,
                capabilities=(RouterCapability.KNOWLEDGE,),
                knowledge_scope=KnowledgeScope.INTERNAL,
                reason="SEMANTIC_INTERNAL_KNOWLEDGE",
            )
        if intent is SemanticIntent.PUBLIC_GETNET_KNOWLEDGE:
            return RouterDecision(
                status=RouterStatus.ROUTED,
                route=RouterRoute.KNOWLEDGE,
                capabilities=(RouterCapability.KNOWLEDGE,),
                web_search_policy=WebSearchPolicy.FALLBACK_IF_RAG_INSUFFICIENT,
                knowledge_scope=KnowledgeScope.PUBLIC_GETNET,
                reason="SEMANTIC_PUBLIC_GETNET_KNOWLEDGE",
            )
        if intent is SemanticIntent.CUSTOMER_SUPPORT:
            return RouterDecision(
                status=RouterStatus.ROUTED,
                route=RouterRoute.CUSTOMER_SUPPORT,
                capabilities=(RouterCapability.CUSTOMER_SUPPORT,),
                knowledge_scope=KnowledgeScope.NONE,
                reason="SEMANTIC_CUSTOMER_SUPPORT",
            )
        if intent is SemanticIntent.EXPECTED_VS_OBSERVED:
            if not trusted.has_authorized_protocol_context:
                return SemanticIntentMapper.safe_failure("AUTHORIZED_PROTOCOL_CONTEXT_REQUIRED")
            return RouterDecision(
                status=RouterStatus.ROUTED,
                route=RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT,
                capabilities=(RouterCapability.KNOWLEDGE, RouterCapability.CUSTOMER_SUPPORT),
                knowledge_scope=KnowledgeScope.INTERNAL,
                reason="SEMANTIC_EXPECTED_AND_OBSERVED",
            )
        if intent in {
            SemanticIntent.GENERAL_PUBLIC_INFORMATION,
            SemanticIntent.CURRENT_PUBLIC_INFORMATION,
        }:
            return RouterDecision(
                status=RouterStatus.ROUTED,
                route=RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK,
                capabilities=(RouterCapability.KNOWLEDGE, RouterCapability.WEB_FALLBACK),
                web_search_policy=WebSearchPolicy.REQUIRED,
                knowledge_scope=KnowledgeScope.NONE,
                reason=(
                    "SEMANTIC_CURRENT_PUBLIC_INFORMATION"
                    if intent is SemanticIntent.CURRENT_PUBLIC_INFORMATION
                    else "SEMANTIC_GENERAL_PUBLIC_INFORMATION"
                ),
            )
        if intent is SemanticIntent.HUMAN_REQUEST:
            return RouterDecision(
                status=RouterStatus.ROUTED,
                route=RouterRoute.HUMAN_ESCALATION,
                capabilities=(RouterCapability.HUMAN_ESCALATION,),
                knowledge_scope=KnowledgeScope.NONE,
                reason="SEMANTIC_HUMAN_REQUEST",
            )
        if intent is SemanticIntent.AMBIGUOUS:
            return SemanticIntentMapper.safe_failure("SEMANTIC_AMBIGUOUS")
        raise SemanticClassifierError("unsupported semantic intent")

    @staticmethod
    def safe_failure(reason: str = "SEMANTIC_CLASSIFIER_UNAVAILABLE"):
        """Return a non-escalating decision for provider/schema failure."""

        from apps.agent_api.app.agents.router import RouterDecision, RouterRoute, RouterStatus

        return RouterDecision(
            status=RouterStatus.AMBIGUOUS,
            route=RouterRoute.AMBIGUOUS,
            knowledge_scope=KnowledgeScope.NONE,
            reason=reason,
        )
