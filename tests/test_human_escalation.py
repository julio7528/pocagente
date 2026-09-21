import pytest
from pydantic import ValidationError

from apps.agent_api.app.agents.customer_support import (
    CustomerSupportResult,
    CustomerSupportStatus,
    ObservedOperationalFact,
    OperationalInference,
)
from apps.agent_api.app.agents.human_escalation import (
    ConversationReference,
    HandoffFact,
    HandoffInference,
    HandoffPackage,
    HumanEscalationAction,
    HumanEscalationAgent,
    HumanEscalationReason,
    HumanEscalationRequest,
    HumanEscalationState,
    HumanEscalationStatus,
    SupportOperatorAuthorization,
    build_handoff_package,
)


def _conversation():
    return ConversationReference(conversation_id="conversation-014")


def _package():
    support = CustomerSupportResult(
        status=CustomerSupportStatus.ANSWERED,
        answer="Observed evidence is available.",
        reason="OBSERVED_OPS_EVIDENCE_INTERPRETED",
        facts=(ObservedOperationalFact(source="OPS", statement="Run 8 failed."),),
        inferences=(OperationalInference(statement="The evidence may indicate a retry issue."),),
    )
    return build_handoff_package(
        conversation=_conversation(),
        reason=HumanEscalationReason.UNRESOLVED_REQUEST,
        problem_summary="Why did the cancellation fail?",
        protocol_reference="POC-OPS-0002",
        run_reference=8,
        customer_support_result=support,
    )


def test_explicit_human_state_machine_requires_confirmation_and_authorized_acceptance():
    agent = HumanEscalationAgent()
    offered = agent.transition(HumanEscalationRequest(
        conversation=_conversation(), current_state=HumanEscalationState.BOT,
        action=HumanEscalationAction.OFFER, reason=HumanEscalationReason.USER_REQUESTED_HUMAN,
    ))
    assert offered.state is HumanEscalationState.WAITING_CONFIRMATION
    assert offered.handoff_package is None

    waiting = agent.transition(HumanEscalationRequest(
        conversation=_conversation(), current_state=offered.state,
        action=HumanEscalationAction.CONFIRM, explicit_user_confirmation=True,
        handoff_package=_package(),
    ))
    assert waiting.state is HumanEscalationState.WAITING_HUMAN
    assert waiting.assigned_operator_id is None
    assert waiting.automation_suspended is False
    assert waiting.handoff_package and waiting.handoff_package.user_confirmation

    rejected = agent.transition(HumanEscalationRequest(
        conversation=_conversation(), current_state=waiting.state,
        action=HumanEscalationAction.ACCEPT, handoff_package=waiting.handoff_package,
        operator=SupportOperatorAuthorization(operator_id="client", is_support_agent=False),
    ))
    assert rejected.status is HumanEscalationStatus.REJECTED
    assert rejected.state is HumanEscalationState.WAITING_HUMAN

    accepted = agent.transition(HumanEscalationRequest(
        conversation=_conversation(), current_state=waiting.state,
        action=HumanEscalationAction.ACCEPT, handoff_package=waiting.handoff_package,
        operator=SupportOperatorAuthorization(operator_id="support-1", is_support_agent=True),
    ))
    assert accepted.state is HumanEscalationState.HUMAN
    assert accepted.automation_suspended is True
    assert accepted.assigned_operator_id == "support-1"

    returned = agent.transition(HumanEscalationRequest(
        conversation=_conversation(), current_state=accepted.state,
        action=HumanEscalationAction.RETURN_TO_AUTOMATION,
        operator=SupportOperatorAuthorization(operator_id="support-1", is_support_agent=True),
        active_operator_id="support-1",
    ))
    assert returned.state is HumanEscalationState.BOT


def test_invalid_transitions_fail_closed_and_models_are_strict_immutable():
    agent = HumanEscalationAgent()
    result = agent.transition(HumanEscalationRequest(
        conversation=_conversation(), current_state=HumanEscalationState.BOT,
        action=HumanEscalationAction.ACCEPT, handoff_package=_package(),
        operator=SupportOperatorAuthorization(operator_id="support-1", is_support_agent=True),
    ))
    assert result.status is HumanEscalationStatus.REJECTED
    with pytest.raises(ValidationError):
        ConversationReference(conversation_id="x", password="not-allowed")
    with pytest.raises(ValidationError):
        _conversation().conversation_id = "changed"


def test_handoff_package_allowlists_and_redacts_sensitive_text_without_mixing_fact_and_inference():
    support = CustomerSupportResult(
        status=CustomerSupportStatus.ANSWERED, answer="answer", reason="safe",
        facts=(ObservedOperationalFact(source="OPS", statement="password=bad"),),
        inferences=(OperationalInference(statement="token abc"),),
    )
    package = build_handoff_package(
        conversation=_conversation(), reason=HumanEscalationReason.UNRESOLVED_REQUEST,
        problem_summary="API key sk-not-shared", customer_support_result=support,
        sanitized_error="Traceback database connection", timeline=("normal event",),
    )
    rendered = package.model_dump_json()
    assert "sk-not-shared" not in rendered and "password=bad" not in rendered
    assert package.facts[0].source == "OPS"
    assert package.inferences[0].statement == "Sensitive content withheld."
    assert "history" not in HandoffPackage.model_fields


def test_acceptance_requires_same_conversation_confirmed_package_and_support_operator():
    agent = HumanEscalationAgent()
    package = _package().model_copy(update={"user_confirmation": True})
    authorized = SupportOperatorAuthorization(operator_id="support-1", is_support_agent=True)
    accepted = agent.transition(HumanEscalationRequest(
        conversation=_conversation(), current_state=HumanEscalationState.WAITING_HUMAN,
        action=HumanEscalationAction.ACCEPT, handoff_package=package, operator=authorized,
    ))
    assert accepted.state is HumanEscalationState.HUMAN

    wrong_conversation = agent.transition(HumanEscalationRequest(
        conversation=ConversationReference(conversation_id="conversation-other"),
        current_state=HumanEscalationState.WAITING_HUMAN,
        action=HumanEscalationAction.ACCEPT, handoff_package=package, operator=authorized,
    ))
    unconfirmed = agent.transition(HumanEscalationRequest(
        conversation=_conversation(), current_state=HumanEscalationState.WAITING_HUMAN,
        action=HumanEscalationAction.ACCEPT, handoff_package=_package(), operator=authorized,
    ))
    assert wrong_conversation.status is unconfirmed.status is HumanEscalationStatus.REJECTED


def test_only_active_owner_can_return_or_resolve():
    agent = HumanEscalationAgent()
    owner = SupportOperatorAuthorization(operator_id="support-1", is_support_agent=True)
    other = SupportOperatorAuthorization(operator_id="support-2", is_support_agent=True)
    for action, target in ((HumanEscalationAction.RETURN_TO_AUTOMATION, HumanEscalationState.BOT), (HumanEscalationAction.RESOLVE, HumanEscalationState.RESOLVED)):
        succeeded = agent.transition(HumanEscalationRequest(
            conversation=_conversation(), current_state=HumanEscalationState.HUMAN,
            action=action, operator=owner, active_operator_id="support-1",
        ))
        rejected = agent.transition(HumanEscalationRequest(
            conversation=_conversation(), current_state=HumanEscalationState.HUMAN,
            action=action, operator=other, active_operator_id="support-1",
        ))
        missing_owner = agent.transition(HumanEscalationRequest(
            conversation=_conversation(), current_state=HumanEscalationState.HUMAN,
            action=action, operator=owner,
        ))
        assert succeeded.state is target
        assert rejected.reason == missing_owner.reason == "ACTIVE_HUMAN_OWNER_MATCH_REQUIRED"


def test_credential_shapes_are_fully_redacted_but_operational_literals_survive():
    uuid = "123e4567-e89b-12d3-a456-426614174000"
    package = HandoffPackage(
        conversation=_conversation(), reason=HumanEscalationReason.UNRESOLVED_REQUEST,
        problem_summary="sk-proj-abcdefghijklmnopqrstuvwxyz123456",
        protocol_reference="POC-OPS-0002",
        observed_operational_state=f"run {uuid} completed stage VALIDATE",
        sanitized_error="Bearer abc.def-ghi_jkl",
        timeline=("password=super-secret", "stage COMPLETE"),
        facts=(HandoffFact(source="OPS", statement="eyJabc.eyJdef.signature"),),
        inferences=(HandoffInference(statement="Normal error text: timeout at stage VALIDATE"),),
    )
    rendered = package.model_dump_json()
    for forbidden in ("sk-proj-", "abc.def", "password=", "eyJabc"):
        assert forbidden not in rendered
    assert "POC-OPS-0002" in rendered
    assert uuid in rendered
    assert "VALIDATE" in rendered
