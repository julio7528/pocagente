"""Phase 9.8 scenario policy tests over the actual Router and LangGraph boundary."""

from __future__ import annotations

import asyncio

from apps.agent_api.app.agents.customer_support import CustomerSupportOperation, CustomerSupportResult, CustomerSupportStatus
from apps.agent_api.app.agents.knowledge import KnowledgeRequest, KnowledgeResult, KnowledgeResultStatus
from apps.agent_api.app.agents.orchestration import CustomerSupportContext, LangGraphOrchestrator, OrchestrationRequest, OrchestrationStatus
from apps.agent_api.app.agents.router import RouterAgent
from apps.agent_api.app.agents.semantic_routing import SemanticClassification, SemanticIntent
from apps.agent_api.app.tools.ops import OpsAccessContext


class StaticClassifier:
    def __init__(self, intent: SemanticIntent) -> None:
        self.intent = intent

    async def classify(self, message: str) -> SemanticClassification:
        del message
        return SemanticClassification(schema_version="1.0", intent=self.intent)


class Knowledge:
    def __init__(self, status: KnowledgeResultStatus = KnowledgeResultStatus.ANSWERED) -> None:
        self.status = status
        self.questions: list[str] = []
    async def answer(self, request: KnowledgeRequest) -> KnowledgeResult:
        question = request.question
        self.questions.append(question)
        return KnowledgeResult(question=question, status=self.status, answer="RAG [C1]." if self.status is KnowledgeResultStatus.ANSWERED else None, reason="RAG")


class WebKnowledge(Knowledge):
    async def answer(self, question: str, **kwargs) -> KnowledgeResult:
        self.questions.append(question)
        return KnowledgeResult(question=question, status=KnowledgeResultStatus.ANSWERED, answer="Live [C1].", reason="WEB")


class Support:
    def __init__(self) -> None:
        self.requests = []
    async def answer(self, request) -> CustomerSupportResult:
        self.requests.append(request)
        return CustomerSupportResult(status=CustomerSupportStatus.ANSWERED, answer="OPS", reason="OPS")


def graph(rag: Knowledge | None = None, intent: SemanticIntent = SemanticIntent.PUBLIC_GETNET_KNOWLEDGE):
    return LangGraphOrchestrator(RouterAgent(StaticClassifier(intent)), rag or Knowledge(), Support(), WebKnowledge())


def test_current_weather_and_exchange_rate_use_live_web_without_rag_or_ops() -> None:
    for message in ("What's the weather forecast in Porto Alegre tomorrow?", "What's the euro exchange rate today?"):
        rag, support, web = Knowledge(), Support(), WebKnowledge()
        result = asyncio.run(LangGraphOrchestrator(RouterAgent(StaticClassifier(SemanticIntent.CURRENT_PUBLIC_INFORMATION)), rag, support, web).execute(OrchestrationRequest(message=message)))
        assert result.status is OrchestrationStatus.COMPLETED
        assert result.live_web_evidence_used is True
        assert rag.questions == []
        assert len(web.questions) == 1
        assert support.requests == []


def test_payment_link_is_rag_first_and_web_is_only_conditional() -> None:
    sufficient_rag, support, web = Knowledge(), Support(), WebKnowledge()
    result = asyncio.run(LangGraphOrchestrator(RouterAgent(StaticClassifier(SemanticIntent.PUBLIC_GETNET_KNOWLEDGE)), sufficient_rag, support, web).execute(OrchestrationRequest(message="Can I sell through WhatsApp using the Payment Link?")))
    assert result.status is OrchestrationStatus.COMPLETED
    assert sufficient_rag.questions
    assert web.questions == []
    insufficient_rag, support, web = Knowledge(KnowledgeResultStatus.INSUFFICIENT_EVIDENCE), Support(), WebKnowledge()
    result = asyncio.run(LangGraphOrchestrator(RouterAgent(StaticClassifier(SemanticIntent.PUBLIC_GETNET_KNOWLEDGE)), insufficient_rag, support, web).execute(OrchestrationRequest(message="Can I sell through WhatsApp using the Payment Link?")))
    assert result.live_web_evidence_used is True
    assert web.questions


def test_private_ops_security_and_human_paths_never_call_web() -> None:
    authorization = OpsAccessContext(principal_id="test", can_read_operational_facts=True)
    support_context = CustomerSupportContext(protocol_number="POC-OPS-0002", operation=CustomerSupportOperation.PROTOCOL_STATUS)
    cases = (
        (SemanticIntent.CUSTOMER_SUPPORT, OrchestrationRequest(message="What is the current status of protocol 123456?", ops_access_context=authorization, customer_support_context=support_context)),
        (SemanticIntent.CUSTOMER_SUPPORT, OrchestrationRequest(message="Is this protocol delayed?", ops_access_context=authorization, customer_support_context=support_context)),
        (SemanticIntent.PUBLIC_GETNET_KNOWLEDGE, OrchestrationRequest(message="What is the database password?")),
        (SemanticIntent.CUSTOMER_SUPPORT, OrchestrationRequest(message="Why did my cancellation protocol 123456 fail to process?", ops_access_context=authorization, customer_support_context=support_context)),
    )
    for intent, request in cases:
        rag, support, web = Knowledge(), Support(), WebKnowledge()
        asyncio.run(LangGraphOrchestrator(RouterAgent(StaticClassifier(intent)), rag, support, web).execute(request))
        assert web.questions == []
