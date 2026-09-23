"""Application-scoped composition for the Phase 9 runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from apps.agent_api.app.agents.customer_support import CustomerSupportAgent
from apps.agent_api.app.agents.conversational import ConversationalAgent
from apps.agent_api.app.agents.human_escalation import HumanEscalationAgent
from apps.agent_api.app.agents.knowledge import KnowledgeAgent
from apps.agent_api.app.agents.orchestration import LangGraphOrchestrator
from apps.agent_api.app.agents.router import RouterAgent
from apps.agent_api.app.agents.semantic_classifier import ProviderSemanticIntentClassifier
from apps.agent_api.app.agents.web_knowledge import WebKnowledgeAgent
from apps.agent_api.app.chat import ChatApplicationService
from apps.agent_api.app.database.config import load_database_config
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.models import (
    AutomationRunRecord, EmailAttachmentRecord, EstablishmentRecord, ExecutionFailureEvidence,
    ExecutionLogRecord, IncomingEmailRecord, ProtocolStatusFacts, RecentExecutedProtocolRecord, ServiceRequestRecord,
)
from apps.agent_api.app.security.audit import PostgresSecurityAuditSink, SecurityAuditService
from apps.agent_api.app.security.semantic import OutputSecurityGate, SecurityResponseAgent, SemanticSecurityClassifier
from apps.agent_api.app.database.repositories.operational import OperationalRepository
from apps.agent_api.app.llm.errors import LLMConfigurationError, LLMProviderError
from apps.agent_api.app.llm.factory import create_deepseek_provider
from apps.agent_api.app.llm.models import LLMGenerationRequest, LLMGenerationResult, LLMProvider
from apps.agent_api.app.rag.embeddings.fastembed import FastEmbedAdapter
from apps.agent_api.app.rag.grounding.context_builder import ContextBuilder
from apps.agent_api.app.rag.retrieval.hybrid import HybridRetriever
from apps.agent_api.app.rag.retrieval.lexical import LexicalRetriever
from apps.agent_api.app.rag.retrieval.semantic import SemanticRetriever
from apps.agent_api.app.tools.ops import OperationalTools
from apps.agent_api.app.web.errors import WebSearchConfigurationError
from apps.agent_api.app.web.factory import create_tavily_web_search_provider
from apps.agent_api.app.web.models import WebSearchProvider


class _UnavailableLLMProvider:
    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResult:
        del request
        raise LLMConfigurationError()


class _UnusedRetrievalRepository:
    """Constructor-only placeholder; HybridRetriever replaces it inside its DB snapshot."""

    async def search_lexical_candidates(self, query: str, limit: int, knowledge_scope: Any) -> Sequence[Any]:
        del query, limit, knowledge_scope
        raise RuntimeError("repository-bound hybrid retrieval required")

    async def search_semantic_candidates(self, embedding: Sequence[float], limit: int, knowledge_scope: Any) -> Sequence[Any]:
        del embedding, limit, knowledge_scope
        raise RuntimeError("repository-bound hybrid retrieval required")


class _PooledOperationalFactsRepository:
    """Open a scoped read connection for each approved OperationalRepository call."""

    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    async def get_protocol_status_facts(self, protocol_number: str) -> Sequence[ProtocolStatusFacts]:
        async with self._database.connection() as connection:
            return await OperationalRepository(connection).get_protocol_status_facts(protocol_number)

    async def list_recent_service_requests(self, limit: int) -> Sequence[ServiceRequestRecord]:
        async with self._database.connection() as connection:
            return await OperationalRepository(connection).list_recent_service_requests(limit)

    async def list_recent_protocols_by_execution(self, limit: int) -> Sequence[RecentExecutedProtocolRecord]:
        async with self._database.connection() as connection:
            return await OperationalRepository(connection).list_recent_protocols_by_execution(limit)

    async def get_execution_failure_facts(
        self,
        protocol_number: str,
        run_id: int | None = None,
    ) -> Sequence[ExecutionFailureEvidence]:
        async with self._database.connection() as connection:
            return await OperationalRepository(connection).get_execution_failure_facts(
                protocol_number,
                run_id=run_id,
            )

    async def get_service_request_by_protocol(self, protocol_number: str) -> ServiceRequestRecord | None:
        async with self._database.connection() as connection:
            return await OperationalRepository(connection).get_service_request_by_protocol(protocol_number)

    async def get_incoming_email(self, email_id: int) -> IncomingEmailRecord | None:
        async with self._database.connection() as connection:
            return await OperationalRepository(connection).get_incoming_email(email_id)

    async def list_email_attachments(self, email_id: int) -> Sequence[EmailAttachmentRecord]:
        async with self._database.connection() as connection:
            return await OperationalRepository(connection).list_email_attachments(email_id)

    async def list_automation_runs_for_request(self, request_id: int) -> Sequence[AutomationRunRecord]:
        async with self._database.connection() as connection:
            return await OperationalRepository(connection).list_automation_runs_for_request(request_id)

    async def list_establishments_for_request(self, request_id: int) -> Sequence[EstablishmentRecord]:
        async with self._database.connection() as connection:
            return await OperationalRepository(connection).list_establishments_for_request(request_id)

    async def list_execution_timeline_for_request(self, request_id: int, limit: int) -> Sequence[ExecutionLogRecord]:
        async with self._database.connection() as connection:
            return await OperationalRepository(connection).list_execution_timeline_for_request(request_id, limit)


@dataclass(frozen=True)
class RuntimeComposition:
    chat_service: ChatApplicationService
    database: PostgresDatabase
    llm_provider: LLMProvider
    web_search_provider: WebSearchProvider | None = None

    async def close(self) -> None:
        first_error: Exception | None = None
        for resource in (self.llm_provider, self.web_search_provider):
            closer = getattr(resource, "aclose", None) if resource is not None else None
            if closer is None:
                continue
            try:
                await closer()
            except Exception as error:
                first_error = first_error or error
        try:
            await self.database.close()
        except Exception as error:
            first_error = first_error or error
        if first_error is not None:
            raise first_error


async def compose_runtime() -> RuntimeComposition:
    """Create one application-scoped runtime with explicit database lifecycle."""

    database = PostgresDatabase(load_database_config())
    await database.open()
    llm_provider: object | None = None
    web_search_provider: object | None = None
    try:
        try:
            llm_provider = create_deepseek_provider()
        except LLMProviderError:
            llm_provider = _UnavailableLLMProvider()

        placeholder = _UnusedRetrievalRepository()
        retrieval = HybridRetriever(
            LexicalRetriever(placeholder),
            SemanticRetriever(placeholder, FastEmbedAdapter()),
            database=database,
        )
        knowledge = KnowledgeAgent(retrieval, ContextBuilder(), llm_provider)
        tools = OperationalTools(_PooledOperationalFactsRepository(database))
        support = CustomerSupportAgent(tools, llm_provider)

        web_knowledge = None
        try:
            web_search_provider = create_tavily_web_search_provider()
            web_knowledge = WebKnowledgeAgent(web_search_provider, llm_provider)
        except WebSearchConfigurationError:
            pass

        orchestrator = LangGraphOrchestrator(
            RouterAgent(
                ProviderSemanticIntentClassifier(llm_provider),
                SemanticSecurityClassifier(llm_provider),
            ),
            knowledge,
            support,
            web_knowledge,
            HumanEscalationAgent(),
            SecurityAuditService(PostgresSecurityAuditSink(database)),
            ConversationalAgent(llm_provider),
        )
        return RuntimeComposition(
            ChatApplicationService(
                orchestrator,
                SecurityResponseAgent(llm_provider),
                OutputSecurityGate(llm_provider),
            ),
            database,
            llm_provider,
            web_search_provider,
        )
    except Exception:
        for resource in (llm_provider, web_search_provider):
            closer = getattr(resource, "aclose", None) if resource is not None else None
            if closer is not None:
                try:
                    await closer()
                except Exception:
                    pass
        await database.close()
        raise
