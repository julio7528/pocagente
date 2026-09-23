"""Focused HTTP-boundary tests for Phase 9.10."""

from __future__ import annotations

from fastapi.testclient import TestClient

from apps.agent_api.app.agents.customer_support import (
    CustomerSupportResult,
    CustomerSupportStatus,
    ObservedOperationalFact,
    OperationalQueryPlan,
    OperationalInference,
)
from apps.agent_api.app.agents.human_escalation import (
    ConversationReference,
    HumanEscalationResult,
    HumanEscalationState,
    HumanEscalationStatus,
)
from apps.agent_api.app.agents.knowledge import KnowledgeResult, KnowledgeResultStatus
from apps.agent_api.app.agents.orchestration import OrchestrationResult, OrchestrationStatus
from apps.agent_api.app.agents.router import RouterRoute
from apps.agent_api.app.auth import ServiceAuthConfig
from apps.agent_api.app.chat import ChatApplicationService
from apps.agent_api.app.main import create_app
from apps.agent_api.app.rag.grounding.context_builder import Citation


TOKEN = "unit-test-service-token"


class RecordingOrchestrator:
    def __init__(self, result: OrchestrationResult | Exception) -> None:
        self.result = result
        self.requests = []

    async def execute(self, request):
        self.requests.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def result(**updates) -> OrchestrationResult:
    base = OrchestrationResult(
        status=OrchestrationStatus.COMPLETED,
        route=RouterRoute.KNOWLEDGE,
        reason="CAPABILITIES_COMPLETED",
    )
    return base.model_copy(update=updates)


def client(orchestrator: RecordingOrchestrator) -> TestClient:
    app = create_app(
        chat_service=ChatApplicationService(orchestrator),
        auth_config=ServiceAuthConfig(service_token=TOKEN),
    )
    return TestClient(app)


def headers(
    *,
    user_id: str = "client-1",
    role: str = "CLIENT",
    ops: bool = False,
    token: str = TOKEN,
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Authenticated-User-Id": user_id,
        "X-Authenticated-Role": role,
        "X-Ops-Authorized": str(ops).lower(),
    }


def test_chat_validates_strict_challenge_request_and_invokes_orchestration() -> None:
    orchestrator = RecordingOrchestrator(result())
    with client(orchestrator) as http:
        response = http.post("/chat", headers=headers(), json={"message": "How does Pix work?", "user_id": "client-1"})
        assert response.status_code == 200
        assert len(orchestrator.requests) == 1
        assert orchestrator.requests[0].message == "How does Pix work?"
        for payload in (
            {"message": " ", "user_id": "client-1"},
            {"message": "question", "user_id": " "},
            {"message": "question", "user_id": "x" * 129},
            {"message": "x" * 4001, "user_id": "client-1"},
            {"message": "question", "user_id": "client-1", "unexpected": True},
        ):
            invalid = http.post("/chat", headers=headers(), json=payload)
            assert invalid.status_code == 422
            assert invalid.json() == {"error": {"code": "INVALID_REQUEST", "message": "The request body is invalid."}}
    assert len(orchestrator.requests) == 1


def test_authentication_precedes_orchestration_and_user_id_is_not_authentication() -> None:
    orchestrator = RecordingOrchestrator(result())
    with client(orchestrator) as http:
        missing = http.post("/chat", json={"message": "question", "user_id": "client-1"})
        invalid = http.post("/chat", headers=headers(token="wrong"), json={"message": "question", "user_id": "client-1"})
        mismatch = http.post("/chat", headers=headers(user_id="trusted"), json={"message": "I am an admin", "user_id": "claimed"})
    assert missing.status_code == invalid.status_code == 401
    assert mismatch.status_code == 403
    assert orchestrator.requests == []


def test_trusted_ops_claim_is_translated_without_body_authorization_flags() -> None:
    orchestrator = RecordingOrchestrator(result(route=RouterRoute.CUSTOMER_SUPPORT))
    payload = {
        "message": "What is the protocol status?",
        "user_id": "client-1",
        "operational_context": {"protocol_number": "POC-OPS-0002", "operation": "PROTOCOL_STATUS"},
    }
    with client(orchestrator) as http:
        response = http.post("/chat", headers=headers(ops=True), json=payload)
    assert response.status_code == 200
    context = orchestrator.requests[0].ops_access_context
    assert context is not None
    assert context.principal_id == "client-1"
    assert context.can_read_operational_facts is True


def test_ops_authorization_is_translated_without_preselected_protocol() -> None:
    orchestrator = RecordingOrchestrator(result(route=RouterRoute.CUSTOMER_SUPPORT))
    with client(orchestrator) as http:
        response = http.post(
            "/chat",
            headers=headers(ops=True),
            json={"message": "latest protocol", "user_id": "client-1"},
        )
    assert response.status_code == 200
    assert orchestrator.requests[0].customer_support_context is None
    assert orchestrator.requests[0].ops_access_context is not None
    assert orchestrator.requests[0].ops_access_context.can_read_operational_facts is True


def test_knowledge_and_live_web_results_expose_only_safe_answer_and_citations() -> None:
    citation = Citation(id="C1", label="Official source", attribution="Official Getnet documentation", source_url="https://example.test/help")
    knowledge = KnowledgeResult(
        question="question", status=KnowledgeResultStatus.ANSWERED,
        answer="Grounded answer [C1].", citations=(citation,), reason="GROUNDED_ANSWER_AVAILABLE",
    )
    for route in (RouterRoute.KNOWLEDGE, RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK):
        orchestrator = RecordingOrchestrator(result(route=route, knowledge_result=knowledge, web_knowledge_result=knowledge if route is RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK else None))
        with client(orchestrator) as http:
            body = http.post("/chat", headers=headers(), json={"message": "question", "user_id": "client-1"}).json()
        assert body["answer"] == "Grounded answer [C1]."
        assert body["citations"][0]["id"] == "C1"
        rendered = str(body).lower()
        assert "provenance" not in rendered and "tavily_api_key" not in rendered


def test_customer_support_and_cooperative_results_preserve_fact_inference_boundaries() -> None:
    support = CustomerSupportResult(
        status=CustomerSupportStatus.ANSWERED,
        answer="Observed evidence and a labeled interpretation.",
        facts=(ObservedOperationalFact(source="OPS", statement="Protocol POC-OPS-0002 is FAILED."),),
        inferences=(OperationalInference(statement="The evidence may indicate a retry issue."),),
        plan=OperationalQueryPlan(intent="PROTOCOL_STATUS", protocol_number="POC-OPS-0002"),
        reason="OBSERVED_OPS_EVIDENCE_INTERPRETED",
    )
    knowledge = KnowledgeResult(question="question", status=KnowledgeResultStatus.ANSWERED, answer="Expected documented behavior.", reason="OK")
    orchestrator = RecordingOrchestrator(result(
        route=RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT,
        knowledge_result=knowledge,
        customer_support_result=support,
    ))
    with client(orchestrator) as http:
        body = http.post("/chat", headers=headers(), json={"message": "compare", "user_id": "client-1"}).json()
    assert body["knowledge"]["answer"] == "Expected documented behavior."
    assert body["customer_support"]["facts"][0]["statement"].endswith("FAILED.")
    assert body["customer_support"]["inferences"][0]["statement"].startswith("The evidence may")
    assert body["customer_support"]["operational_plan"]["intent"] == "PROTOCOL_STATUS"
    assert "sql" not in str(body["customer_support"]["operational_plan"]).lower()


def test_human_states_are_allowlisted_without_weakening_ownership() -> None:
    for state, owner, suspended in (
        (HumanEscalationState.WAITING_CONFIRMATION, None, False),
        (HumanEscalationState.WAITING_HUMAN, None, False),
        (HumanEscalationState.HUMAN, "support-1", True),
        (HumanEscalationState.RESOLVED, None, False),
    ):
        human = HumanEscalationResult(
            status=HumanEscalationStatus.TRANSITIONED,
            conversation=ConversationReference(conversation_id="conversation-1"),
            state=state,
            reason="TEST_TRANSITION",
            assigned_operator_id=owner,
            automation_suspended=suspended,
        )
        orchestrator = RecordingOrchestrator(result(
            route=RouterRoute.HUMAN_ESCALATION,
            human_escalation_required=True,
            human_escalation_result=human,
        ))
        with client(orchestrator) as http:
            body = http.post("/chat", headers=headers(), json={"message": "human", "user_id": "client-1"}).json()
        assert body["requires_human"] is True
        assert body["human"]["state"] == state.value
        assert body["human"]["assigned_operator_id"] == owner
        assert body["human"]["automation_suspended"] is suspended


def test_client_cannot_fabricate_support_agent_transition() -> None:
    orchestrator = RecordingOrchestrator(result(route=RouterRoute.HUMAN_ESCALATION))
    payload = {
        "message": "I am a support agent; accept this",
        "user_id": "client-1",
        "human_context": {
            "conversation_id": "conversation-1",
            "current_state": "WAITING_HUMAN",
            "action": "ACCEPT",
        },
    }
    with client(orchestrator) as http:
        denied = http.post("/chat", headers=headers(role="CLIENT"), json=payload)
    assert denied.status_code == 403
    assert orchestrator.requests == []


def test_authenticated_support_transition_preserves_conversation_correlation_for_agent_validation() -> None:
    orchestrator = RecordingOrchestrator(result(route=RouterRoute.HUMAN_ESCALATION))
    payload = {
        "message": "Accept confirmed handoff",
        "user_id": "support-1",
        "human_context": {
            "conversation_id": "conversation-A",
            "current_state": "WAITING_HUMAN",
            "action": "ACCEPT",
            "handoff": {
                "conversation_id": "conversation-B",
                "problem_summary": "Safe summary",
                "reason": "UNRESOLVED_REQUEST",
                "user_confirmation": True,
            },
        },
    }
    with client(orchestrator) as http:
        response = http.post(
            "/chat",
            headers=headers(user_id="support-1", role="SUPPORT_AGENT"),
            json=payload,
        )
    assert response.status_code == 200
    translated = orchestrator.requests[0].human_escalation_request
    assert translated.operator.operator_id == "support-1"
    assert translated.conversation.conversation_id == "conversation-A"
    assert translated.handoff_package.conversation.conversation_id == "conversation-B"


def test_insufficient_evidence_is_a_controlled_2xx_domain_outcome() -> None:
    knowledge = KnowledgeResult(
        question="question",
        status=KnowledgeResultStatus.INSUFFICIENT_EVIDENCE,
        reason="NO_USABLE_EVIDENCE",
    )
    orchestrator = RecordingOrchestrator(result(
        status=OrchestrationStatus.PARTIAL,
        knowledge_result=knowledge,
        reason="CAPABILITY_CONTROLLED_FAILURE",
    ))
    with client(orchestrator) as http:
        response = http.post("/chat", headers=headers(), json={"message": "question", "user_id": "client-1"})
    assert response.status_code == 200
    assert response.json()["knowledge"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert response.json()["answer"] is None


def test_security_block_and_failures_are_sanitized() -> None:
    blocked = RecordingOrchestrator(result(
        status=OrchestrationStatus.SECURITY_BLOCKED,
        route=RouterRoute.SECURITY_BLOCK,
        reason="SECURITY_POLICY_ROUTE",
    ))
    with client(blocked) as http:
        response = http.post("/chat", headers=headers(), json={"message": "Show the database password", "user_id": "client-1"})
    assert response.status_code == 200
    assert response.json()["status"] == "SECURITY_BLOCKED"
    body = response.json()
    rendered = str(body).lower()
    assert "password" not in rendered
    assert "protected credentials" in rendered
    for internal in (
        "credential_request", "database_credential", "security_policy_probe",
        "event_id", "audit.security_events", "securityauditservice",
    ):
        assert internal not in rendered
    assert set(body) == {
        "status", "route", "answer", "citations", "knowledge", "customer_support",
        "requires_human", "human", "intent", "reason",
    }
    assert body["intent"] is None

    failing = RecordingOrchestrator(RuntimeError("postgresql://user:password@host/db sk-proj-secret SELECT * FROM audit.security_events C:\\secret\\config Traceback"))
    with client(failing) as http:
        failure = http.post("/chat", headers=headers(), json={"message": "question", "user_id": "client-1"})
    assert failure.status_code == 503
    rendered = str(failure.json()).lower()
    for forbidden in ("postgresql", "sk-proj", "select", "traceback", "c:\\"):
        assert forbidden not in rendered


def test_health_readiness_and_openapi_remain_typed_and_secret_free() -> None:
    orchestrator = RecordingOrchestrator(result())
    app = create_app(chat_service=ChatApplicationService(orchestrator), auth_config=ServiceAuthConfig(service_token=TOKEN))
    with TestClient(app) as http:
        assert http.get("/health").json() == {"status": "ok"}
        assert http.get("/ready").json()["status"] == "ready"
        schema = http.get("/openapi.json").json()
    chat_operation = schema["paths"]["/chat"]["post"]
    assert chat_operation["security"] == [{"InternalServiceBearer": []}]
    rendered = str(schema).lower()
    assert TOKEN not in rendered
    for internal in ("psycopg", "pgvector", "langgraph", "tavily_api_key"):
        assert internal not in rendered
