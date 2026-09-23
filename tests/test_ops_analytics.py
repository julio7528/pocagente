from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from apps.agent_api.app.agents.customer_support import (
    CustomerSupportAgent, CustomerSupportRequest, CustomerSupportStatus,
    OperationalInvestigationPlan,
)
from apps.agent_api.app.agents.ops_analytics import (
    AnalyticsGrain, AnalyticsMetric, AnalyticsOrdering, OperationalAnalyticsPlan,
    OperationalTemporalResolver, OperationalTimeExpression, TemporalKind,
)
from apps.agent_api.app.database.models import OperationalAnalyticsResult, OperationalAnalyticsRow
from apps.agent_api.app.llm.models import LLMGenerationResult
from apps.agent_api.app.tools.ops import OpsAccessContext, OpsToolStatus


def _utc(local: datetime, zone: str = "America/Cuiaba") -> datetime:
    return local.replace(tzinfo=ZoneInfo(zone)).astimezone(UTC)


@pytest.mark.parametrize(
    ("now", "kind", "start_local", "end_local"),
    [
        (datetime(2026, 9, 23, 15, tzinfo=UTC), TemporalKind.LAST_WEEK,
         datetime(2026, 9, 14), datetime(2026, 9, 21)),
        (datetime(2026, 9, 21, 12, tzinfo=UTC), TemporalKind.LAST_WEEK,
         datetime(2026, 9, 14), datetime(2026, 9, 21)),
        (datetime(2026, 9, 20, 12, tzinfo=UTC), TemporalKind.THIS_WEEK,
         datetime(2026, 9, 14), datetime(2026, 9, 20, 8)),
    ],
)
def test_calendar_week_resolution_is_local_and_deterministic(now, kind, start_local, end_local):
    resolver = OperationalTemporalResolver(timezone_name="America/Cuiaba", clock=lambda: now)
    result = resolver.resolve(OperationalTimeExpression(kind=kind))
    assert result.start_at == _utc(start_local)
    assert result.end_at == _utc(end_local)


def test_last_week_is_not_rolling_seven_days():
    now = datetime(2026, 9, 23, 15, tzinfo=UTC)
    resolver = OperationalTemporalResolver(timezone_name="America/Cuiaba", clock=lambda: now)
    last_week = resolver.resolve(OperationalTimeExpression(kind=TemporalKind.LAST_WEEK))
    rolling = resolver.resolve(OperationalTimeExpression(kind=TemporalKind.LAST_N_DAYS, days=7))
    assert last_week.start_at != rolling.start_at
    assert last_week.end_at > rolling.start_at


def test_month_resolution_chooses_most_recent_occurrence_without_year():
    resolver = OperationalTemporalResolver(
        timezone_name="America/Cuiaba", clock=lambda: datetime(2026, 1, 12, 12, tzinfo=UTC)
    )
    result = resolver.resolve(OperationalTimeExpression(kind=TemporalKind.CALENDAR_MONTH, month=8))
    assert result.start_at == _utc(datetime(2025, 8, 1))
    assert result.end_at == _utc(datetime(2025, 9, 1))


def test_explicit_month_year_and_leap_year_boundaries():
    resolver = OperationalTemporalResolver(
        timezone_name="America/Cuiaba", clock=lambda: datetime(2026, 9, 23, 12, tzinfo=UTC)
    )
    explicit = resolver.resolve(OperationalTimeExpression(
        kind=TemporalKind.CALENDAR_MONTH, month=8, year=2025
    ))
    assert explicit.start_at == _utc(datetime(2025, 8, 1))
    assert explicit.end_at == _utc(datetime(2025, 9, 1))
    february = resolver.resolve(OperationalTimeExpression(
        kind=TemporalKind.CALENDAR_MONTH, month=2, year=2024
    ))
    assert february.start_at == _utc(datetime(2024, 2, 1))
    assert february.end_at == _utc(datetime(2024, 3, 1))


def test_explicit_date_range_is_inclusive_and_resolved_to_half_open_interval():
    resolver = OperationalTemporalResolver(
        timezone_name="America/Cuiaba", clock=lambda: datetime(2026, 9, 23, 12, tzinfo=UTC)
    )
    result = resolver.resolve(OperationalTimeExpression(
        kind=TemporalKind.BETWEEN_DATES, start_date="2025-08-01", end_date="2025-08-31"
    ))
    assert result.start_at == _utc(datetime(2025, 8, 1))
    assert result.end_at == _utc(datetime(2025, 9, 1))


def test_before_and_after_dates_resolve_exclusive_day_boundaries():
    resolver = OperationalTemporalResolver(
        timezone_name="America/Cuiaba", clock=lambda: datetime(2026, 9, 23, 12, tzinfo=UTC)
    )
    boundary = date(2025, 8, 10)
    before = resolver.resolve(OperationalTimeExpression(kind=TemporalKind.BEFORE_DATE, start_date=boundary))
    after = resolver.resolve(OperationalTimeExpression(kind=TemporalKind.AFTER_DATE, start_date=boundary))
    assert before.end_at == _utc(datetime(2025, 8, 10))
    assert after.start_at == _utc(datetime(2025, 8, 11))


def test_temporal_contract_rejects_llm_calculated_timestamps_and_invalid_dimensions():
    with pytest.raises(ValidationError):
        OperationalTimeExpression.model_validate({"kind": "LAST_WEEK", "start_at": "2026-09-14T00:00:00Z"})
    with pytest.raises(ValidationError):
        OperationalTimeExpression(kind=TemporalKind.LAST_N_DAYS)
    first = OperationalAnalyticsPlan(grain=AnalyticsGrain.EXECUTION, metric=AnalyticsMetric.FIRST)
    assert first.ordering is AnalyticsOrdering.EARLIEST
    with pytest.raises(ValidationError):
        OperationalAnalyticsPlan(
            grain=AnalyticsGrain.PROTOCOL, metric=AnalyticsMetric.COUNT, robot_filter="R2"
        )


def test_analytics_dimensions_compose_without_phrase_specific_intent():
    plan = OperationalAnalyticsPlan.model_validate({
        "grain": "EXECUTION", "metric": "LIST",
        "time": {"kind": "LAST_WEEK"}, "robot_filter": "R2",
        "outcome_filter": "FAILURE", "ordering": "LATEST", "limit": 3,
    })
    assert plan.grain is AnalyticsGrain.EXECUTION
    assert plan.time.kind is TemporalKind.LAST_WEEK
    assert plan.robot_filter == "R2"
    assert plan.outcome_filter.value == "FAILURE"


def test_exact_event_status_is_distinct_from_normalized_failure_outcome():
    plan = OperationalAnalyticsPlan.model_validate({
        "grain": "EVENT", "metric": "COUNT", "time": {"kind": "TODAY"},
        "status_filter": "ERROR",
    })
    assert plan.status_filter.value == "ERROR"
    with pytest.raises(ValidationError):
        OperationalAnalyticsPlan.model_validate({
            "grain": "PROTOCOL", "metric": "COUNT", "status_filter": "ERROR",
        })


def test_planned_temporal_execution_reaches_authorized_analytics_tool_without_clarification():
    class Provider:
        def __init__(self):
            self.responses = [
                LLMGenerationResult(content=(
                    '{"intent":"ANALYTICS","analytics":{"grain":"EXECUTION",'
                    '"metric":"EXISTS","time":{"kind":"LAST_WEEK"},'
                    '"time_basis":"EXECUTION_STARTED","group_by":["OUTCOME"]}}'
                )),
                LLMGenerationResult(content='{"answer":"Sim, houve execuções no período.","inferences":[]}'),
            ]

        async def generate(self, _request):
            return self.responses.pop(0)

    class Tools:
        def __init__(self):
            self.calls = []

        async def query_analytics(self, query, authorization):
            self.calls.append((query, authorization))
            return OpsToolStatus.SUCCESS, OperationalAnalyticsResult(
                exists=True, total_count=2,
                groups=({"outcome": "SUCCESS", "count": 1}, {"outcome": "FAILURE", "count": 1}),
            ), "OPERATIONAL_ANALYTICS_COMPLETED"

    tools = Tools()
    auth = OpsAccessContext(principal_id="support", can_read_operational_facts=True)
    agent = CustomerSupportAgent(
        tools, Provider(), temporal_resolver=OperationalTemporalResolver(
            timezone_name="America/Cuiaba", clock=lambda: datetime(2026, 9, 23, 15, tzinfo=UTC)
        ),
    )
    result = __import__("asyncio").run(agent.answer(CustomerSupportRequest(
        question="Tem registro de execução do processo semana passada?", authorization=auth,
    )))
    assert result.status is CustomerSupportStatus.ANSWERED
    assert result.plan is not None and result.plan.intent.value == "ANALYTICS"
    assert len(tools.calls) == 1
    query, passed_auth = tools.calls[0]
    assert query.grain == "EXECUTION"
    assert query.start_at == _utc(datetime(2026, 9, 14))
    assert query.end_at == _utc(datetime(2026, 9, 21))
    assert passed_auth is auth
    assert any("total_count=2" in fact.statement for fact in result.facts)


def test_analytics_never_calls_repository_for_unauthorized_principal():
    class Provider:
        async def generate(self, _request):
            raise AssertionError("planner must not run for unauthorized support")

    class Tools:
        calls = 0

        async def query_analytics(self, *_args):
            self.calls += 1

    tools = Tools()
    agent = CustomerSupportAgent(tools, Provider())
    result = __import__("asyncio").run(agent.answer(CustomerSupportRequest(
        question="quantas execuções hoje?",
        authorization=OpsAccessContext(principal_id="client", can_read_operational_facts=False),
    )))
    assert result.status is CustomerSupportStatus.UNAUTHORIZED
    assert tools.calls == 0


def test_unique_protocol_analytics_result_exposes_typed_follow_up_selector():
    class Provider:
        def __init__(self):
            self.responses = [
                LLMGenerationResult(content=(
                    '{"intent":"ANALYTICS","analytics":{"grain":"PROTOCOL","metric":"FIRST",'
                    '"time_basis":"FIRST_EXECUTION","ordering":"EARLIEST","limit":1}}'
                )),
                LLMGenerationResult(content='{"answer":"POC-OPS-0001 foi o primeiro.","inferences":[]}'),
            ]

        async def generate(self, _request):
            return self.responses.pop(0)

    class Tools:
        async def query_analytics(self, _query, _authorization):
            row = OperationalAnalyticsRow(
                protocol_number="POC-OPS-0001", status="COMPLETED", outcome="SUCCESS",
                occurred_at=datetime(2026, 9, 1, 13, tzinfo=UTC),
            )
            return OpsToolStatus.SUCCESS, OperationalAnalyticsResult(
                exists=True, total_count=1, rows=(row,),
            ), "OPERATIONAL_ANALYTICS_COMPLETED"

    result = __import__("asyncio").run(CustomerSupportAgent(
        Tools(), Provider(), temporal_resolver=OperationalTemporalResolver(
            timezone_name="America/Cuiaba", clock=lambda: datetime(2026, 9, 23, 15, tzinfo=UTC)
        ),
    ).answer(CustomerSupportRequest(
        question="qual foi o primeiro protocolo executado?",
        authorization=OpsAccessContext(principal_id="support", can_read_operational_facts=True),
    )))
    assert result.status is CustomerSupportStatus.ANSWERED
    assert result.selected_protocol_number == "POC-OPS-0001"
