"""Deterministic Phase 11.4 tests for the dataset-driven Challenge runner."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.agent_api.app.agents.human_escalation import HumanEscalationState
from apps.agent_api.app.agents.router import RouterCapability, RouterRoute, WebSearchPolicy
from apps.agent_api.app.evaluation.challenge_results import (
    ConditionalFallbackObservation,
    ChallengeInvocationCounts,
    ChallengeScenarioStatus,
    ChallengeSecurityObservation,
    ChallengeToolObservation,
)
from apps.agent_api.app.evaluation.adapters import adapt_challenge_scenario
from apps.agent_api.app.evaluation.challenge_runner import (
    ChallengeEvaluationRunner,
    ChallengeInvocationObserver,
    DeterministicChallengeRuntime,
)
from apps.agent_api.app.evaluation.loaders import load_challenge_suite
from apps.agent_api.app.security.models import SecurityAction


_SUITE_PATH = Path(__file__).resolve().parents[1] / "evaluation" / "challenge" / "scenarios-v1.yaml"


@pytest.fixture()
def suite():
    return load_challenge_suite(_SUITE_PATH)


def _by_semantics(suite, *, freshness: str | None = None, tools: tuple[str, ...] = (), route: str | None = None):
    for scenario in suite.suite.scenarios:
        if freshness is not None and scenario.freshness_requirement != freshness:
            continue
        if tools and scenario.expected_tools != tools:
            continue
        if route is not None and scenario.expected_route != route:
            continue
        return scenario
    raise AssertionError("semantic scenario fixture was not found")


def test_runner_executes_loaded_suite_in_declared_order_and_returns_frozen_results(suite) -> None:
    results = ChallengeEvaluationRunner(suite).run()
    assert len(results) == suite.entry_count == 14
    assert tuple(result.scenario_id for result in results) == tuple(item.id for item in suite.suite.scenarios)
    assert all(result.execution_mode.value == "DETERMINISTIC_E2E" for result in results)
    with pytest.raises(Exception):
        results[0].status = ChallengeScenarioStatus.FAIL


def test_adapter_policy_is_independent_of_scenario_identifier(suite) -> None:
    scenario = _by_semantics(suite, freshness="required")
    renamed = scenario.model_copy(update={"id": "challenge-902"})
    result = ChallengeEvaluationRunner(suite).run_scenario(renamed)
    assert result.status is ChallengeScenarioStatus.PASS
    assert result.observed_route is RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK
    assert result.invocation_counts.web == 1
    assert result.web_search_policy is WebSearchPolicy.REQUIRED


def test_required_web_scenarios_are_observed_through_web_boundary(suite) -> None:
    results = ChallengeEvaluationRunner(suite).run()
    web_results = [item for item in results if item.web_search_policy is WebSearchPolicy.REQUIRED]
    assert len(web_results) == 2
    assert all(item.observed_route is RouterRoute.KNOWLEDGE_WITH_WEB_FALLBACK for item in web_results)
    assert all(item.invocation_counts.web == 1 and item.invocation_counts.knowledge == 0 for item in web_results)
    assert all(item.invocation_counts.ops_lookup_protocol_status == 0 for item in web_results)


def test_conditional_web_fallback_records_primary_and_insufficient_evidence_branches(suite) -> None:
    result = next(
        item for item in ChallengeEvaluationRunner(suite).run()
        if item.web_search_policy is WebSearchPolicy.FALLBACK_IF_RAG_INSUFFICIENT
    )
    assert result.status is ChallengeScenarioStatus.PASS
    assert result.conditional_fallback is not None
    assert result.conditional_fallback.primary_knowledge_called
    assert not result.conditional_fallback.primary_web_called
    assert result.conditional_fallback.fallback_knowledge_called
    assert result.conditional_fallback.fallback_web_called
    assert result.conditional_fallback.fallback_after_knowledge
    assert result.conditional_fallback.primary_events == ("knowledge",)
    assert result.conditional_fallback.fallback_events == ("knowledge", "web")
    assert not result.conditional_fallback.persistent_write_boundary_available


def test_conditional_fallback_order_requires_knowledge_before_web() -> None:
    assert ChallengeEvaluationRunner._knowledge_before_web(("knowledge", "web"))
    assert not ChallengeEvaluationRunner._knowledge_before_web(("web", "knowledge"))
    assert not ChallengeEvaluationRunner._knowledge_before_web(("knowledge",))


def test_conditional_fallback_pass_gate_requires_measured_primary_and_ordered_supporting_branches(suite) -> None:
    scenario = next(
        item for item in suite.suite.scenarios
        if "web_search_if_rag_insufficient" in item.expected_capabilities
    )
    expectation = adapt_challenge_scenario(scenario)
    primary_knowledge_observed = True
    primary_web_observed = False
    valid = ConditionalFallbackObservation(
        primary_knowledge_called=primary_knowledge_observed,
        primary_web_called=primary_web_observed,
        fallback_knowledge_called=True, fallback_web_called=True,
        fallback_after_knowledge=True,
    )
    premature_web = valid.model_copy(update={"primary_web_called": True})
    missing_primary_knowledge = valid.model_copy(update={"primary_knowledge_called": False})
    reversed_order = valid.model_copy(update={"fallback_after_knowledge": False})
    total = ChallengeInvocationCounts(
        knowledge=2, web=1, customer_support=0, ops_lookup_protocol_status=0,
        ops_inspect_execution_failure=0, interpretation_provider=0, human_escalation=0,
    )
    assert ChallengeEvaluationRunner._capabilities_ok(scenario, expectation, total, None, valid)
    assert not ChallengeEvaluationRunner._capabilities_ok(scenario, expectation, total, None, premature_web)
    assert not ChallengeEvaluationRunner._capabilities_ok(scenario, expectation, total, None, missing_primary_knowledge)
    assert not ChallengeEvaluationRunner._capabilities_ok(scenario, expectation, total, None, reversed_order)


def test_authorized_ops_and_fact_inference_separation_are_observed(suite) -> None:
    results = ChallengeEvaluationRunner(suite).run()
    protocol = next(item for item in results if item.observed_tool_calls == ("lookup_protocol_status",))
    cooperative = next(item for item in results if item.expected_route is RouterRoute.KNOWLEDGE_AND_CUSTOMER_SUPPORT and item.invocation_counts.ops_lookup_protocol_status == 1)
    assert protocol.status is ChallengeScenarioStatus.PASS
    # Scenario total includes the supporting denied authorization journey; the
    # primary tool observation remains the exact authorized execution evidence.
    assert protocol.invocation_counts.customer_support >= 1
    assert protocol.invocation_counts.web == 0
    assert protocol.authorization.respected is True
    assert protocol.fact_inference.separated is True
    assert cooperative.invocation_counts.knowledge == 1
    assert cooperative.invocation_counts.customer_support == 1
    assert cooperative.authorization.respected is True
    assert cooperative.fact_inference.separated is True


def test_missing_ops_authorization_never_reaches_synthetic_repository(suite) -> None:
    scenario = _by_semantics(suite, tools=("lookup_protocol_status",))
    runtime = DeterministicChallengeRuntime()
    with TestClient(runtime.app) as client:
        response = client.post("/chat", headers=runtime.headers(user_id=suite.suite.defaults.user_id, ops=False), json={
            "message": scenario.message, "user_id": suite.suite.defaults.user_id,
            "operational_context": {"protocol_number": "POC-OPS-0002", "operation": "PROTOCOL_STATUS", "run_id": 31},
        })
    assert response.status_code == 200
    assert response.json()["customer_support"]["status"] == "UNAUTHORIZED"
    assert runtime.observer.snapshot()["ops_lookup_protocol_status"] == 0


def test_expected_tools_and_fact_inference_are_pass_gates(suite) -> None:
    scenario = _by_semantics(suite, tools=("lookup_protocol_status",))
    none = ChallengeInvocationCounts(
        knowledge=0, web=0, customer_support=0, ops_lookup_protocol_status=0,
        ops_inspect_execution_failure=0, interpretation_provider=0, human_escalation=0,
    )
    missing = ChallengeEvaluationRunner._tool_observation(scenario, none)
    assert not missing.expected_tools_satisfied
    extra = ChallengeInvocationCounts(
        knowledge=0, web=0, customer_support=1, ops_lookup_protocol_status=1,
        ops_inspect_execution_failure=1, interpretation_provider=1, human_escalation=0,
    )
    unexpected = ChallengeEvaluationRunner._tool_observation(scenario, extra)
    assert not unexpected.unexpected_tools_absent
    malformed = ChallengeEvaluationRunner._fact_inference_observation(
        {"customer_support": {"facts": [], "inferences": []}}, extra
    )
    assert malformed.applicable and malformed.separated is False
    assert ChallengeEvaluationRunner._single_status(
        route_ok=True, capabilities_ok=True, tools=missing, forbidden_ok=True,
        authorization_ok=True, fact_inference_ok=True, security_ok=True, public_safe=True,
    ) is ChallengeScenarioStatus.FAIL
    assert ChallengeEvaluationRunner._single_status(
        route_ok=True, capabilities_ok=True,
        tools=ChallengeToolObservation(expected_tools=(), observed_tools=(), expected_tools_satisfied=True, unexpected_tools_absent=True),
        forbidden_ok=True, authorization_ok=True, fact_inference_ok=False, security_ok=True, public_safe=True,
    ) is ChallengeScenarioStatus.FAIL


def test_security_terminal_uses_direct_audit_events_and_has_no_forbidden_continuation(suite) -> None:
    scenario = _by_semantics(suite, route="security_block")
    result = ChallengeEvaluationRunner(suite).run_scenario(scenario)
    assert result.status is ChallengeScenarioStatus.PASS
    assert result.security is not None
    assert result.security.blocked and result.security.sanitized and result.security.public_response_safe
    assert result.security.audit_recorded and result.security.protective_action_observed
    assert result.security.forbidden_continuation_absent
    assert result.security.event_types and result.security.audit_actions
    assert result.invocation_counts.knowledge == result.invocation_counts.web == 0
    assert result.invocation_counts.customer_support == result.invocation_counts.ops_lookup_protocol_status == 0
    assert result.invocation_counts.human_escalation == result.invocation_counts.interpretation_provider == 0


def test_security_pass_requires_direct_audit_block_and_no_continuation() -> None:
    zero = ChallengeInvocationCounts(
        knowledge=0, web=0, customer_support=0, ops_lookup_protocol_status=0,
        ops_inspect_execution_failure=0, interpretation_provider=0, human_escalation=0,
    )
    no_event = ChallengeSecurityObservation(
        blocked=True, sanitized=False, public_response_safe=True, audit_recorded=False,
        protective_action_observed=False, forbidden_continuation_absent=True,
    )
    assert not ChallengeEvaluationRunner._security_ok(no_event, zero)
    wrong_action = ChallengeSecurityObservation(
        blocked=True, sanitized=True, public_response_safe=True, audit_recorded=True,
        protective_action_observed=True, forbidden_continuation_absent=True,
        audit_actions=(SecurityAction.DENY_ACCESS,),
    )
    assert not ChallengeEvaluationRunner._security_ok(wrong_action, zero)
    continued = zero.model_copy(update={"human_escalation": 1})
    event = ChallengeSecurityObservation(
        blocked=True, sanitized=True, public_response_safe=True, audit_recorded=True,
        protective_action_observed=True, forbidden_continuation_absent=False,
        audit_actions=(SecurityAction.BLOCK,),
    )
    assert not ChallengeEvaluationRunner._security_ok(event, continued)


def test_authorization_is_typed_measured_evidence_not_a_legacy_plain_flag(suite) -> None:
    scenario = _by_semantics(suite, tools=("lookup_protocol_status",))
    result = ChallengeEvaluationRunner(suite).run_scenario(scenario)
    assert not hasattr(result, "authorization_respected")
    assert result.authorization.applicable
    assert result.authorization.authorized_request_succeeded is True
    assert result.authorization.unauthorized_request_checked
    assert result.authorization.unauthorized_repository_calls == 0
    assert result.authorization.unauthorized_access_blocked is True
    assert result.authorization.respected is True


def test_every_declared_forbidden_capability_has_explicit_observation(suite) -> None:
    results = ChallengeEvaluationRunner(suite).run()
    declared = {item for scenario in suite.suite.scenarios for item in scenario.forbidden_capabilities}
    observed = {
        item
        for result in results
        for item in (*result.forbidden.checked, *result.forbidden.architectural_prohibitions)
    }
    assert observed == declared


def test_scenario_invocation_deltas_do_not_leak_across_requests() -> None:
    observer = ChallengeInvocationObserver()
    before = observer.snapshot()
    observer.increment("knowledge")
    first = ChallengeInvocationObserver.delta(before, observer.snapshot())
    second_before = observer.snapshot()
    second = ChallengeInvocationObserver.delta(second_before, observer.snapshot())
    assert first.knowledge == 1
    assert second.knowledge == 0
    assert observer.snapshot()["knowledge"] == 1


def test_multi_turn_handoff_preserves_waiting_then_human_ownership(suite) -> None:
    scenario = next(item for item in suite.suite.scenarios if item.turns)
    result = ChallengeEvaluationRunner(suite).run_scenario(scenario)
    assert result.status is ChallengeScenarioStatus.PASS
    assert result.human is not None
    assert result.human.states[:3] == (
        HumanEscalationState.WAITING_CONFIRMATION,
        HumanEscalationState.WAITING_HUMAN,
        HumanEscalationState.HUMAN,
    )
    assert result.turns[0].tool_calls == ("lookup_protocol_status", "inspect_execution_failure")
    assert result.turns[1].human_state is HumanEscalationState.WAITING_HUMAN
    assert not result.turns[1].assigned_operator_present and not result.turns[1].automation_suspended
    assert result.turns[2].assigned_operator_present and result.turns[2].automation_suspended
    assert result.turns[3].status == "HUMAN_OWNERSHIP_ACTIVE"
    assert result.turns[3].invocation_counts.knowledge == 0
    assert result.human.operator_authorization_rejected
    assert result.human.wrong_operator_ownership_preserved
    assert result.human.assigned_operator_resolution_succeeded
    assert result.human.handoff_context_safe
    assert result.authorization.respected is True
    assert result.authorization.operator_acceptance_succeeded is True
    assert result.authorization.wrong_operator_rejected is True
    assert result.authorization.ownership_preserved is True
    assert result.fact_inference.separated is True
