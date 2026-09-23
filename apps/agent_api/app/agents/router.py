"""Typed, decision-only Router capability for approved Phase 9 routes."""

from __future__ import annotations

import re
from time import perf_counter
import unicodedata
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from apps.agent_api.app.llm.errors import LLMProviderError

from apps.agent_api.app.security.models import (
    SecurityClassification,
    SecurityEventType,
    SecurityResourceCategory,
)
from apps.agent_api.app.agents.semantic_routing import (
    SemanticClassification,
    SemanticClassifierError,
    SemanticIntentClassifier,
    SemanticIntent,
    SemanticCapabilityNeed,
    SemanticIntentMapper,
    SemanticRoutingContext,
)
from apps.agent_api.app.rag.scope import KnowledgeScope
from apps.agent_api.app.telemetry import RuntimeEventKind, emit_runtime_event
from apps.agent_api.app.security.semantic import (
    SemanticSecurityClassifier,
    SecurityAction as SemanticSecurityAction,
    SecurityCategory,
)


class RouterCapability(StrEnum):
    """Only application capabilities approved by the Phase 9 SDD."""

    KNOWLEDGE = "KNOWLEDGE"
    CUSTOMER_SUPPORT = "CUSTOMER_SUPPORT"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"
    WEB_FALLBACK = "WEB_FALLBACK"
    SECURITY_GUARDRAIL = "SECURITY_GUARDRAIL"
    CONVERSATIONAL = "CONVERSATIONAL"


class RouterRoute(StrEnum):
    """Controlled capability decisions; never tool or agent implementation names."""

    KNOWLEDGE = "KNOWLEDGE"
    CUSTOMER_SUPPORT = "CUSTOMER_SUPPORT"
    KNOWLEDGE_AND_CUSTOMER_SUPPORT = "KNOWLEDGE_AND_CUSTOMER_SUPPORT"
    KNOWLEDGE_WITH_WEB_FALLBACK = "KNOWLEDGE_WITH_WEB_FALLBACK"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"
    SECURITY_BLOCK = "SECURITY_BLOCK"
    AMBIGUOUS = "AMBIGUOUS"
    CONVERSATIONAL = "CONVERSATIONAL"


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
    ops_read_authorized: bool = False


class RouterDecision(BaseModel):
    """Immutable decision for future orchestration; it contains no business answer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: RouterStatus
    route: RouterRoute
    capabilities: tuple[RouterCapability, ...] = ()
    web_search_policy: WebSearchPolicy = WebSearchPolicy.NONE
    knowledge_scope: KnowledgeScope = KnowledgeScope.NONE
    reason: str = Field(min_length=1)
    security_semantics: tuple[SecurityClassification, ...] = ()
    semantic_intent: SemanticIntent | None = None
    semantic_capability_needs: tuple[SemanticCapabilityNeed, ...] = ()
    security_audit_required: bool = True

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
            RouterRoute.CONVERSATIONAL: (RouterStatus.ROUTED, (RouterCapability.CONVERSATIONAL,)),
        }
        status, capabilities = expected[self.route]
        if self.status is not status or self.capabilities != capabilities:
            raise ValueError("router decision fields do not match the approved route")
        if self.route is RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK:
            if self.web_search_policy is not WebSearchPolicy.REQUIRED:
                raise ValueError("current-information route requires live web search")
            if self.knowledge_scope is not KnowledgeScope.NONE:
                raise ValueError("current-information route cannot carry a retrieval scope")
        elif self.web_search_policy is WebSearchPolicy.REQUIRED:
            raise ValueError("only the approved current-information route requires live web search")
        if self.route is RouterRoute.SECURITY_BLOCK and not self.security_semantics and self.security_audit_required:
            raise ValueError("security blocks require typed security semantics")
        if self.route is not RouterRoute.SECURITY_BLOCK and self.security_semantics:
            raise ValueError("only security blocks may carry security semantics")
        knowledge_routes = {
            RouterRoute.KNOWLEDGE,
            RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT,
        }
        if self.route is RouterRoute.KNOWLEDGE:
            expected_scope = (
                KnowledgeScope.PUBLIC_GETNET
                if self.web_search_policy is WebSearchPolicy.FALLBACK_IF_RAG_INSUFFICIENT
                else KnowledgeScope.INTERNAL
                if self.web_search_policy is WebSearchPolicy.NONE
                else None
            )
            if expected_scope is None or self.knowledge_scope is not expected_scope:
                raise ValueError("knowledge route policy and scope are incompatible")
        elif self.route is RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT:
            if self.web_search_policy is not WebSearchPolicy.NONE or self.knowledge_scope is not KnowledgeScope.INTERNAL:
                raise ValueError("cooperative knowledge policy requires internal scope and no Web")
        elif self.route not in knowledge_routes and self.knowledge_scope is not KnowledgeScope.NONE:
            raise ValueError("non-knowledge routes cannot carry a retrieval scope")
        if self.route not in {RouterRoute.KNOWLEDGE, RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK} and self.web_search_policy is not WebSearchPolicy.NONE:
            raise ValueError("this route cannot carry a Web policy")
        semantic_keys = tuple((item.event_type, item.resource_category) for item in self.security_semantics)
        if len(set(semantic_keys)) != len(semantic_keys):
            raise ValueError("security semantics must be deduplicated")
        return self


class RouterAgent:
    """Classify only approved capabilities; never execute agents, tools, or SQL."""

    _OVERRIDE_ACTIONS = frozenset(
        {
            "ignore", "disregard", "desconsidere", "forget", "esqueça", "esqueca",
            "override", "supersede", "bypass", "circumvent", "contorne", "burlar",
        }
    )
    _INSTRUCTION_TARGETS = frozenset(
        {
            "instruction", "instructions", "instrução", "instrucoes", "instruções",
            "rule", "rules", "regra", "regras", "policy", "policies", "politica",
            "politicas", "política", "políticas", "system", "prompt", "previous", "prior",
            "security", "seguranca", "segurança",
        }
    )
    _AUTHORIZATION_BYPASS_PATTERN = re.compile(
        r"bypass (?:authentication|authorization|the authorization check|security controls?)|"
        r"get around (?:the )?authorization|access (?:it|the database) without permission|"
        r"(?:burlar|contornar|ignorar) (?:a )?(?:autenticacao|autorizacao|controle de acesso)|"
        r"acessar (?:o )?(?:banco|sistema) sem (?:permissao|autorizacao)",
        re.IGNORECASE,
    )
    _SECURITY_PROBE_PATTERN = re.compile(
        r"(?:do not|don't) (?:log|register) (?:this|it|the request)|show (?:the )?secret only once|"
        r"nao (?:registre|grave|audite) (?:isto|isso|esta solicitacao|o pedido)",
        re.IGNORECASE,
    )
    _DATABASE_CREDENTIAL_PATTERN = re.compile(
        r"(?:database|db|retaguarda|internal system|sistema interno|banco(?: de dados)?).{0,60}"
        r"(?:password|username|user name|credential|credentials|senha|usuario|credenciais?)|"
        r"(?:password|username|user name|credential|credentials|senha|usuario|credenciais?).{0,60}"
        r"(?:database|db|retaguarda|internal system|sistema interno|banco(?: de dados)?)",
        re.IGNORECASE,
    )
    _API_KEY_PATTERN = re.compile(r"(?:api[_ -]?key|deepseek[_ -]?api[_ -]?key|chave de api)", re.IGNORECASE)
    _TOKEN_PATTERN = re.compile(r"(?:access|refresh|bearer|session) token|\bbearer\b|token de acesso", re.IGNORECASE)
    _PRIVATE_KEY_PATTERN = re.compile(r"private key|chave privada", re.IGNORECASE)
    _COOKIE_PATTERN = re.compile(r"(?:session )?cookie", re.IGNORECASE)
    _CONNECTION_STRING_PATTERN = re.compile(r"connection string|string de conexao|DSN|postgres(?:ql)?://", re.IGNORECASE)
    _PASSWORD_PATTERN = re.compile(r"\b(?:password|passphrase|senha)\b", re.IGNORECASE)
    _GENERIC_CREDENTIAL_PATTERN = re.compile(r"\b(?:credentials?|credenciais?)\b", re.IGNORECASE)
    _GENERIC_SECRET_PATTERN = re.compile(r"\b(?:secrets?|segredos?)\b", re.IGNORECASE)
    _DATABASE_ACCESS_PATTERN = re.compile(
        r"(?:connect|query|access|how to use|steps to access).{0,60}(?:directly\s+to\s+)?(?:the\s+)?(?:internal\s+|production\s+)?database|"
        r"(?:database|sqlagent|select\s+.+\s+from).{0,60}(?:direct access|directly|query|execute)|"
        r"(?:conectar|consultar|acessar|como usar|passos para acessar).{0,80}(?:diretamente )?(?:o )?(?:banco(?: de dados)?|sistema interno)|"
        r"(?:banco(?: de dados)?|sistema interno).{0,80}(?:acesso direto|diretamente|consultar|executar)",
        re.IGNORECASE,
    )
    _SECRET_LOCATION_PATTERN = re.compile(
        r"(?:where|location|located|stored|store).{0,60}(?:api key|secret|credential|password|token)|"
        r"(?:onde|localizacao|armazenad[oa]s?|guardad[oa]s?).{0,80}"
        r"(?:chave de api|secret|segredo|credencial|senha|token)",
        re.IGNORECASE,
    )
    _PROTECTED_PATH_PATTERN = re.compile(
        r"(?:where|location|located).{0,60}(?:protected )?(?:RAG )?(?:files?|paths?)|"
        r"protected (?:RAG )?(?:files?|paths?)|"
        r"(?:onde|localizacao|armazenad[oa]s?).{0,80}(?:arquivos?|caminhos?) (?:internos? |protegidos? )?(?:do )?rag|"
        r"(?:arquivos?|caminhos?) (?:internos? |protegidos? )?(?:do )?rag",
        re.IGNORECASE,
    )
    _INFRASTRUCTURE_PATTERN = re.compile(
        r"(?:internal|protected|production) infrastructure|internal database details|"
        r"secret locations?|infraestrutura (?:interna|protegida|de producao)|"
        r"detalhes internos (?:do banco|da infraestrutura)|localizacao de segredos?",
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

    def __init__(
        self,
        semantic_classifier: SemanticIntentClassifier | None = None,
        semantic_security_classifier: SemanticSecurityClassifier | None = None,
    ) -> None:
        self._semantic_classifier = semantic_classifier
        self._semantic_security_classifier = semantic_security_classifier

    def route(self, request: RouterRequest) -> RouterDecision:
        """Return a controlled decision without running the selected capability."""

        message = request.message.strip()
        if not message:
            return self._decision(RouterRoute.AMBIGUOUS, "ROUTER_MESSAGE_BLANK")
        security_semantics = self._classify_security_semantics(message)
        if security_semantics:
            return self._decision(
                RouterRoute.SECURITY_BLOCK,
                "SECURITY_POLICY_ROUTE",
                security_semantics=security_semantics,
            )
        return self._route_legacy_after_security(request, message)

    def _route_legacy_after_security(self, request: RouterRequest, message: str) -> RouterDecision:
        """Legacy ordinary routing path; caller has already run security preflight."""

        if self._HUMAN_PATTERN.search(message):
            return self._decision(RouterRoute.HUMAN_ESCALATION, "EXPLICIT_HUMAN_REQUEST")
        expected_vs_observed = re.search(
            r"\bdelayed\b|\batrasado\b|deveria ter acontecido|what should have happened",
            message,
            re.IGNORECASE,
        )
        if request.ops_read_authorized and expected_vs_observed:
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

    async def route_async(self, request: RouterRequest) -> RouterDecision:
        """Run security first, then await the configured semantic classifier.

        Production composition injects the provider-backed classifier. An absent
        classifier is a compatibility seam for bounded tests/evaluation only and
        safely degrades without selecting a capability.
        """

        started_at = perf_counter()
        message = request.message.strip()
        emit_runtime_event(RuntimeEventKind.SECURITY, value="PREFLIGHT_STARTED")
        if not message:
            decision = self._decision(RouterRoute.AMBIGUOUS, "ROUTER_MESSAGE_BLANK")
            emit_runtime_event(
                RuntimeEventKind.SECURITY,
                value="ALLOWED",
                elapsed_ms=int((perf_counter() - started_at) * 1000),
            )
            return decision
        security_semantics = self._classify_security_semantics(message)
        if security_semantics:
            decision = self._decision(
                RouterRoute.SECURITY_BLOCK,
                "SECURITY_POLICY_ROUTE",
                security_semantics=security_semantics,
            )
            emit_runtime_event(
                RuntimeEventKind.SECURITY,
                value="SECURITY_BLOCK",
                elapsed_ms=int((perf_counter() - started_at) * 1000),
            )
            return decision
        emit_runtime_event(
            RuntimeEventKind.SECURITY,
            value="ALLOWED",
            elapsed_ms=int((perf_counter() - started_at) * 1000),
        )
        if self._semantic_security_classifier is not None:
            emit_runtime_event(RuntimeEventKind.SECURITY_SEMANTIC, value="STARTED")
            try:
                security_decision = await self._semantic_security_classifier.classify(message)
            except Exception:
                # No business capability is selected when the additional security
                # boundary cannot provide a validated decision.
                emit_runtime_event(RuntimeEventKind.SECURITY_SEMANTIC, value="CONTROLLED_ERROR")
                return self._decision(RouterRoute.AMBIGUOUS, "SEMANTIC_SECURITY_UNAVAILABLE")
            if security_decision.action is SemanticSecurityAction.BLOCK:
                semantics = self._semantic_security_audit_semantics(security_decision.category)
                if not semantics and security_decision.category is not SecurityCategory.INAPPROPRIATE_CONTENT:
                    return self._decision(RouterRoute.AMBIGUOUS, "SECURITY_AUDIT_CATEGORY_UNAVAILABLE")
                emit_runtime_event(RuntimeEventKind.SECURITY_SEMANTIC, value="BLOCKED")
                emit_runtime_event(RuntimeEventKind.SECURITY, value="SECURITY_BLOCK")
                decision = self._decision(
                    RouterRoute.SECURITY_BLOCK, "SEMANTIC_SECURITY_POLICY_BLOCK",
                    security_semantics=semantics,
                    security_audit_required=bool(semantics),
                )
                return decision
            emit_runtime_event(RuntimeEventKind.SECURITY_SEMANTIC, value="ALLOWED")
        if self._semantic_classifier is None:
            emit_runtime_event(RuntimeEventKind.CLASSIFIER, value="NOT_CONFIGURED")
            decision = SemanticIntentMapper.safe_failure("SEMANTIC_CLASSIFIER_UNAVAILABLE")
            return decision
        classifier_started_at = perf_counter()
        emit_runtime_event(RuntimeEventKind.CLASSIFIER, value="STARTED")
        try:
            classification = await self._semantic_classifier.classify(message)
            classification = SemanticClassification.model_validate(classification)
        except (TimeoutError, LLMProviderError, SemanticClassifierError, ValidationError, TypeError):
            emit_runtime_event(
                RuntimeEventKind.CLASSIFIER,
                value="CONTROLLED_ERROR",
                elapsed_ms=int((perf_counter() - classifier_started_at) * 1000),
            )
            decision = SemanticIntentMapper.safe_failure()
            return decision
        emit_runtime_event(
            RuntimeEventKind.CLASSIFIER,
            value="COMPLETED",
            elapsed_ms=int((perf_counter() - classifier_started_at) * 1000),
        )
        emit_runtime_event(RuntimeEventKind.INTENT, value=classification.intent.value)
        decision = SemanticIntentMapper.map(
            classification,
            SemanticRoutingContext(
                ops_read_authorized=request.ops_read_authorized
            )
        )
        decision = decision.model_copy(update={
            "semantic_intent": classification.intent,
            "semantic_capability_needs": classification.capability_needs or SemanticClassification.default_needs(classification.intent),
        })
        return decision

    @staticmethod
    def _semantic_security_audit_semantics(category: SecurityCategory) -> tuple[SecurityClassification, ...]:
        mapping = {
            SecurityCategory.CREDENTIAL_REQUEST: SecurityClassification(event_type=SecurityEventType.CREDENTIAL_REQUEST, resource_category=SecurityResourceCategory.OTHER_PROTECTED_RESOURCE),
            SecurityCategory.SECRET_REQUEST: SecurityClassification(event_type=SecurityEventType.SECRET_REQUEST, resource_category=SecurityResourceCategory.OTHER_PROTECTED_RESOURCE),
            SecurityCategory.DATABASE_ACCESS: SecurityClassification(event_type=SecurityEventType.DATABASE_ACCESS_REQUEST, resource_category=SecurityResourceCategory.INTERNAL_INFRASTRUCTURE),
            SecurityCategory.SENSITIVE_INFRASTRUCTURE: SecurityClassification(event_type=SecurityEventType.SENSITIVE_INFRASTRUCTURE_REQUEST, resource_category=SecurityResourceCategory.INTERNAL_INFRASTRUCTURE),
            SecurityCategory.PROTECTED_IMPLEMENTATION: SecurityClassification(event_type=SecurityEventType.SENSITIVE_INFRASTRUCTURE_REQUEST, resource_category=SecurityResourceCategory.INTERNAL_INFRASTRUCTURE),
            SecurityCategory.PROMPT_INJECTION: SecurityClassification(event_type=SecurityEventType.PROMPT_INJECTION),
            SecurityCategory.AUTHORIZATION_BYPASS: SecurityClassification(event_type=SecurityEventType.AUTHORIZATION_BYPASS_ATTEMPT, resource_category=SecurityResourceCategory.AUTHENTICATION_CONTROL),
            SecurityCategory.PROTECTED_PATH: SecurityClassification(event_type=SecurityEventType.SENSITIVE_INFRASTRUCTURE_REQUEST, resource_category=SecurityResourceCategory.PROTECTED_PATH),
        }
        value = mapping.get(category)
        return (value,) if value is not None else ()

    @staticmethod
    def _decision(
        route: RouterRoute,
        reason: str,
        web_search_policy: WebSearchPolicy = WebSearchPolicy.NONE,
        security_semantics: tuple[SecurityClassification, ...] = (),
        security_audit_required: bool = True,
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
            RouterRoute.CONVERSATIONAL: (RouterStatus.ROUTED, (RouterCapability.CONVERSATIONAL,)),
        }
        status, capabilities = routes[route]
        if route is RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK:
            web_search_policy = WebSearchPolicy.REQUIRED
        if route is RouterRoute.KNOWLEDGE:
            knowledge_scope = (
                KnowledgeScope.PUBLIC_GETNET
                if web_search_policy is WebSearchPolicy.FALLBACK_IF_RAG_INSUFFICIENT
                else KnowledgeScope.INTERNAL
            )
        elif route is RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT:
            knowledge_scope = KnowledgeScope.INTERNAL
        else:
            knowledge_scope = KnowledgeScope.NONE
        return RouterDecision(
            status=status,
            route=route,
            capabilities=capabilities,
            web_search_policy=web_search_policy,
            knowledge_scope=knowledge_scope,
            reason=reason,
            security_semantics=security_semantics,
            security_audit_required=security_audit_required,
        )

    @classmethod
    def _classify_security_semantics(cls, message: str) -> tuple[SecurityClassification, ...]:
        """Return Router-owned, specific, deduplicated security semantics."""

        original_message = message
        message = cls._normalize_security_text(message)
        tokens = frozenset(re.findall(r"[a-z0-9]+", message))

        semantics: list[SecurityClassification] = []

        def add(event_type: SecurityEventType, resource: SecurityResourceCategory | None = None) -> None:
            semantic = SecurityClassification(event_type=event_type, resource_category=resource)
            if semantic not in semantics:
                semantics.append(semantic)

        if cls._has_composed_prompt_injection_robust(original_message, tokens):
            add(SecurityEventType.PROMPT_INJECTION)
        if cls._AUTHORIZATION_BYPASS_PATTERN.search(message):
            add(SecurityEventType.AUTHORIZATION_BYPASS_ATTEMPT, SecurityResourceCategory.AUTHENTICATION_CONTROL)
        if cls._SECRET_LOCATION_PATTERN.search(message):
            add(SecurityEventType.SENSITIVE_INFRASTRUCTURE_REQUEST, SecurityResourceCategory.SECRET_LOCATION)
        elif cls._PROTECTED_PATH_PATTERN.search(message):
            add(SecurityEventType.SENSITIVE_INFRASTRUCTURE_REQUEST, SecurityResourceCategory.PROTECTED_PATH)
        elif cls._INFRASTRUCTURE_PATTERN.search(message):
            add(SecurityEventType.SENSITIVE_INFRASTRUCTURE_REQUEST, SecurityResourceCategory.INTERNAL_INFRASTRUCTURE)

        credential_resource: SecurityResourceCategory | None = None
        if cls._DATABASE_CREDENTIAL_PATTERN.search(message):
            credential_resource = SecurityResourceCategory.DATABASE_CREDENTIAL
        elif cls._API_KEY_PATTERN.search(message) and not cls._SECRET_LOCATION_PATTERN.search(message):
            credential_resource = SecurityResourceCategory.API_KEY
        elif cls._TOKEN_PATTERN.search(message) and not cls._SECRET_LOCATION_PATTERN.search(message):
            credential_resource = SecurityResourceCategory.ACCESS_TOKEN
        elif cls._PRIVATE_KEY_PATTERN.search(message) and not cls._SECRET_LOCATION_PATTERN.search(message):
            credential_resource = SecurityResourceCategory.PRIVATE_KEY
        elif cls._COOKIE_PATTERN.search(message) and not cls._SECRET_LOCATION_PATTERN.search(message):
            credential_resource = SecurityResourceCategory.COOKIE
        elif cls._CONNECTION_STRING_PATTERN.search(message) and not cls._SECRET_LOCATION_PATTERN.search(message):
            credential_resource = SecurityResourceCategory.CONNECTION_STRING
        elif cls._PASSWORD_PATTERN.search(message) and not cls._SECRET_LOCATION_PATTERN.search(message):
            credential_resource = SecurityResourceCategory.PASSWORD
        elif cls._GENERIC_CREDENTIAL_PATTERN.search(message) and not cls._SECRET_LOCATION_PATTERN.search(message):
            credential_resource = SecurityResourceCategory.OTHER_PROTECTED_RESOURCE

        if credential_resource is not None:
            add(SecurityEventType.CREDENTIAL_REQUEST, credential_resource)
        elif cls._GENERIC_SECRET_PATTERN.search(message) and not cls._SECRET_LOCATION_PATTERN.search(message):
            add(SecurityEventType.SECRET_REQUEST, SecurityResourceCategory.OTHER_PROTECTED_RESOURCE)

        if cls._DATABASE_ACCESS_PATTERN.search(message):
            add(SecurityEventType.DATABASE_ACCESS_REQUEST, SecurityResourceCategory.INTERNAL_INFRASTRUCTURE)

        if cls._SECURITY_PROBE_PATTERN.search(message) and not cls._has_composed_prompt_injection(message, tokens) and not cls._AUTHORIZATION_BYPASS_PATTERN.search(message):
            add(SecurityEventType.SECURITY_POLICY_PROBE)

        canonical_order = {
            SecurityEventType.PROMPT_INJECTION: 0,
            SecurityEventType.AUTHORIZATION_BYPASS_ATTEMPT: 1,
            SecurityEventType.CREDENTIAL_REQUEST: 2,
            SecurityEventType.SECRET_REQUEST: 3,
            SecurityEventType.DATABASE_ACCESS_REQUEST: 4,
            SecurityEventType.SENSITIVE_INFRASTRUCTURE_REQUEST: 5,
            SecurityEventType.SECURITY_POLICY_PROBE: 6,
        }
        return tuple(sorted(semantics, key=lambda item: canonical_order[item.event_type]))

    @staticmethod
    def _normalize_security_text(message: str) -> str:
        """Normalize only the classification view; retain the original for AUDIT."""

        # Some clients may present UTF-8 bytes decoded once as Latin-1. Repair
        # that representation only when it round-trips cleanly; normal Unicode
        # input continues through the same deterministic path below.
        try:
            repaired = message.encode("latin-1").decode("utf-8")
            message = repaired
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        decomposed = unicodedata.normalize("NFKD", message.casefold())
        without_diacritics = "".join(
            character for character in decomposed if not unicodedata.combining(character)
        )
        separated = "".join(
            character if character.isalnum() else " " for character in without_diacritics
        )
        return " ".join(separated.split())

    @classmethod
    def _has_composed_prompt_injection_robust(cls, message: str, tokens: frozenset[str]) -> bool:
        """Apply compositional override detection without encoding-sensitive literals."""

        normalized = cls._normalize_security_text(message)
        normalized_tokens = frozenset(re.findall(r"[a-z0-9]+", normalized))
        actions = normalized_tokens & {
            "ignore", "disregard", "desconsidere", "forget", "esqueca",
            "override", "supersede", "bypass", "circumvent", "contorne", "burlar",
        }
        target = bool(
            re.search(
                r"\b(?:instruction(?:s)?|instrucoes|instrua\s+a\s+ces|rule(?:s)?|regra(?:s)?|policy|policies|politica(?:s)?|security|seguranca|system|prompt)\b",
                normalized,
                re.IGNORECASE,
            )
            or re.search(
                r"\b(?:instruction(?:s)?|instru\u00e7\u00f5es|rule(?:s)?|regra(?:s)?|policy|policies|pol\u00edtica(?:s)?|seguran\u00e7a|system|prompt)\b",
                message,
                re.IGNORECASE,
            )
        )
        phrase = bool(
            re.search(r"\b(?:do not|dont) follow\b", normalized)
            or re.search(r"\bnao siga\b", normalized)
            or re.search(r"\bna\s+o siga\b", normalized)
            or re.search(r"\b(?:nao|n\u00e3o|na\s+o) siga\b", message, re.IGNORECASE)
            or re.search(r"\b(?:leave aside|deixe de lado)\b", normalized)
        )
        return target and (bool(actions) or phrase)

    @classmethod
    def _has_composed_prompt_injection(cls, message: str, tokens: frozenset[str]) -> bool:
        """Recognize override action + instruction/policy target composition."""

        has_action = bool(tokens & {item.casefold() for item in cls._OVERRIDE_ACTIONS})
        target_tokens = {item.casefold() for item in cls._INSTRUCTION_TARGETS} - {"previous", "prior"}
        has_target = bool(tokens & target_tokens) or bool(
            re.search(
                r"\b(?:instruction(?:s)?|instrucoes|rule(?:s)?|regra(?:s)?|policy|policies|politica(?:s)?|security|seguranca|system|prompt)\b",
                message,
            )
        )
        phrase_action = bool(
            re.search(r"\b(?:do not|dont) follow\b", message)
            or re.search(r"\b(?:nao|não) siga\b", message, re.IGNORECASE)
            or re.search(r"\b(?:leave aside|deixe de lado)\b", message)
        )
        explicit_target = bool(
            re.search(
                r"\b(?:instruction(?:s)?|instrucoes|instruções|rule(?:s)?|regra(?:s)?|policy|policies|politica(?:s)?|política(?:s)?|security|seguranca|segurança|system|prompt)\b",
                message,
                re.IGNORECASE,
            )
        )
        original_target = bool(
            re.search(
                r"\b(?:instruction(?:s)?|instrucoes|instruções|rule(?:s)?|regra(?:s)?|policy|policies|politica(?:s)?|política(?:s)?|security|seguranca|segurança|system|prompt)\b",
                message,
                re.IGNORECASE,
            )
        )
        return (has_action and (has_target or original_target)) or (phrase_action and original_target)
