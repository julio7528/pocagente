"""Closed OPS analytics planning and deterministic temporal resolution."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnalyticsGrain(StrEnum):
    PROTOCOL = "PROTOCOL"
    EXECUTION = "EXECUTION"
    EVENT = "EVENT"


class AnalyticsMetric(StrEnum):
    EXISTS = "EXISTS"
    COUNT = "COUNT"
    LIST = "LIST"
    FIRST = "FIRST"
    LAST = "LAST"
    SUMMARY = "SUMMARY"


class TemporalKind(StrEnum):
    ALL_TIME = "ALL_TIME"
    TODAY = "TODAY"
    YESTERDAY = "YESTERDAY"
    THIS_WEEK = "THIS_WEEK"
    LAST_WEEK = "LAST_WEEK"
    LAST_N_DAYS = "LAST_N_DAYS"
    THIS_MONTH = "THIS_MONTH"
    LAST_MONTH = "LAST_MONTH"
    CALENDAR_MONTH = "CALENDAR_MONTH"
    BETWEEN_DATES = "BETWEEN_DATES"
    BEFORE_DATE = "BEFORE_DATE"
    AFTER_DATE = "AFTER_DATE"


class AnalyticsTimeBasis(StrEnum):
    PROTOCOL_CREATED = "PROTOCOL_CREATED"
    PROTOCOL_OUTCOME_AT = "PROTOCOL_OUTCOME_AT"
    FIRST_EXECUTION = "FIRST_EXECUTION"
    LAST_EXECUTION = "LAST_EXECUTION"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_FINISHED = "EXECUTION_FINISHED"
    EVENT_OCCURRED = "EVENT_OCCURRED"


class AnalyticsOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    OTHER = "OTHER"


class AnalyticsRawStatus(StrEnum):
    """Exact approved physical status values, distinct from normalized outcomes."""

    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    WAITING_RESULT = "WAITING_RESULT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    ERROR = "ERROR"
    EXCEPTION = "EXCEPTION"


class AnalyticsGrouping(StrEnum):
    OUTCOME = "OUTCOME"
    ROBOT = "ROBOT"


class AnalyticsOrdering(StrEnum):
    EARLIEST = "EARLIEST"
    LATEST = "LATEST"


class OperationalTimeExpression(BaseModel):
    """Natural-time vocabulary; deliberately has no timestamp fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: TemporalKind
    days: int | None = Field(default=None, ge=1, le=3650, strict=True)
    month: int | None = Field(default=None, ge=1, le=12, strict=True)
    year: int | None = Field(default=None, ge=2000, le=2200, strict=True)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_components(self) -> OperationalTimeExpression:
        if (self.kind is TemporalKind.LAST_N_DAYS) != (self.days is not None):
            raise ValueError("LAST_N_DAYS requires only a bounded days value")
        if self.kind is TemporalKind.CALENDAR_MONTH:
            if self.month is None:
                raise ValueError("CALENDAR_MONTH requires a month")
        elif self.month is not None:
            raise ValueError("month is allowed only for CALENDAR_MONTH")
        if self.kind is TemporalKind.BETWEEN_DATES:
            if self.start_date is None or self.end_date is None or self.end_date < self.start_date:
                raise ValueError("BETWEEN_DATES requires an ordered inclusive date range")
        elif self.kind is TemporalKind.BEFORE_DATE or self.kind is TemporalKind.AFTER_DATE:
            if self.start_date is None or self.end_date is not None:
                raise ValueError("BEFORE/AFTER_DATE requires start_date only")
        elif self.start_date is not None or self.end_date is not None:
            raise ValueError("dates are supported only by explicit date expressions")
        if self.year is not None and self.kind not in {TemporalKind.CALENDAR_MONTH, TemporalKind.BETWEEN_DATES}:
            raise ValueError("year is supported only for calendar month or explicit range")
        return self


class OperationalAnalyticsPlan(BaseModel):
    """Unresolved semantic dimensions selected by the planner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    grain: AnalyticsGrain
    metric: AnalyticsMetric
    time: OperationalTimeExpression = OperationalTimeExpression(kind=TemporalKind.ALL_TIME)
    time_basis: AnalyticsTimeBasis | None = None
    outcome_filter: AnalyticsOutcome | None = None
    status_filter: AnalyticsRawStatus | None = None
    robot_filter: str | None = Field(default=None, pattern=r"^(R1|R2)$")
    ordering: AnalyticsOrdering | None = None
    group_by: tuple[AnalyticsGrouping, ...] = Field(default=(), max_length=2)
    limit: int = Field(default=5, ge=1, le=50, strict=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_empty_grouping(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            if value.get("group_by", ()) is None:
                value["group_by"] = ()
            metric = value.get("metric")
            if value.get("ordering") is None and metric in {AnalyticsMetric.FIRST, AnalyticsMetric.FIRST.value}:
                value["ordering"] = AnalyticsOrdering.EARLIEST
            elif value.get("ordering") is None and metric in {AnalyticsMetric.LAST, AnalyticsMetric.LAST.value}:
                value["ordering"] = AnalyticsOrdering.LATEST
        return value

    @model_validator(mode="after")
    def validate_analytics_semantics(self) -> OperationalAnalyticsPlan:
        if len(set(self.group_by)) != len(self.group_by):
            raise ValueError("grouping dimensions must be unique")
        if AnalyticsGrouping.ROBOT in self.group_by and self.grain is AnalyticsGrain.PROTOCOL:
            raise ValueError("protocol analytics cannot group by execution robot")
        if self.grain is AnalyticsGrain.PROTOCOL and self.robot_filter is not None:
            raise ValueError("robot filter requires execution or event grain")
        allowed_statuses = {
            AnalyticsGrain.PROTOCOL: {AnalyticsRawStatus.CREATED, AnalyticsRawStatus.PROCESSING, AnalyticsRawStatus.WAITING_RESULT, AnalyticsRawStatus.COMPLETED, AnalyticsRawStatus.FAILED},
            AnalyticsGrain.EXECUTION: {AnalyticsRawStatus.RUNNING, AnalyticsRawStatus.SUCCESS, AnalyticsRawStatus.PARTIAL, AnalyticsRawStatus.ERROR},
            AnalyticsGrain.EVENT: {AnalyticsRawStatus.SUCCESS, AnalyticsRawStatus.ERROR, AnalyticsRawStatus.EXCEPTION},
        }
        if self.status_filter is not None and self.status_filter not in allowed_statuses[self.grain]:
            raise ValueError("exact status filter does not match analytical grain")
        if self.metric in {AnalyticsMetric.FIRST, AnalyticsMetric.LAST} and self.ordering is None:
            raise ValueError("first/last requires explicit ordering")
        if self.metric not in {AnalyticsMetric.LIST, AnalyticsMetric.FIRST, AnalyticsMetric.LAST} and self.ordering is not None:
            raise ValueError("ordering is supported only for list/first/last analytics")
        if self.metric is AnalyticsMetric.FIRST and self.ordering is not AnalyticsOrdering.EARLIEST:
            raise ValueError("FIRST must use EARLIEST ordering")
        if self.metric is AnalyticsMetric.LAST and self.ordering is not AnalyticsOrdering.LATEST:
            raise ValueError("LAST must use LATEST ordering")
        if self.time_basis is not None:
            allowed = {
                AnalyticsGrain.PROTOCOL: {AnalyticsTimeBasis.PROTOCOL_CREATED, AnalyticsTimeBasis.PROTOCOL_OUTCOME_AT, AnalyticsTimeBasis.FIRST_EXECUTION, AnalyticsTimeBasis.LAST_EXECUTION},
                AnalyticsGrain.EXECUTION: {AnalyticsTimeBasis.EXECUTION_STARTED, AnalyticsTimeBasis.EXECUTION_FINISHED},
                AnalyticsGrain.EVENT: {AnalyticsTimeBasis.EVENT_OCCURRED},
            }
            if self.time_basis not in allowed[self.grain]:
                raise ValueError("time basis does not match analytical grain")
        if self.time.kind is TemporalKind.CALENDAR_MONTH and self.time.year is not None and self.time.year < 2000:
            raise ValueError("calendar year is outside the approved range")
        return self


class ResolvedTimeWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start_at: datetime | None = None
    end_at: datetime | None = None
    timezone: str

    @model_validator(mode="after")
    def aware_and_ordered(self) -> ResolvedTimeWindow:
        for value in (self.start_at, self.end_at):
            if value is not None and value.utcoffset() is None:
                raise ValueError("resolved analytics bounds must be timezone-aware")
        if self.start_at is not None and self.end_at is not None and self.end_at <= self.start_at:
            raise ValueError("resolved analytics interval must be non-empty")
        return self


class OperationalTemporalResolver:
    """Resolve natural-time expressions using one configured business zone and clock."""

    DEFAULT_TIMEZONE = "America/Cuiaba"

    def __init__(self, *, timezone_name: str | None = None, clock=None) -> None:
        self.timezone_name = timezone_name or os.getenv("OPERATIONAL_TIMEZONE", self.DEFAULT_TIMEZONE)
        try:
            self.zone = ZoneInfo(self.timezone_name)
        except ZoneInfoNotFoundError as error:
            raise ValueError("OPERATIONAL_TIMEZONE must be a valid IANA timezone") from error
        self._clock = clock or (lambda: datetime.now(UTC))

    def resolve(self, expression: OperationalTimeExpression) -> ResolvedTimeWindow:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("temporal resolver clock must return an aware datetime")
        local_now = now.astimezone(self.zone)
        today = local_now.date()
        midnight = lambda value: datetime.combine(value, time.min, self.zone)
        kind = expression.kind
        start: datetime | None = None
        end: datetime | None = None
        if kind is TemporalKind.ALL_TIME:
            pass
        elif kind is TemporalKind.TODAY:
            start, end = midnight(today), local_now
        elif kind is TemporalKind.YESTERDAY:
            start = midnight(today - timedelta(days=1))
            end = midnight(today)
        elif kind is TemporalKind.THIS_WEEK:
            start = midnight(today - timedelta(days=today.weekday()))
            end = local_now
        elif kind is TemporalKind.LAST_WEEK:
            this_monday = today - timedelta(days=today.weekday())
            start, end = midnight(this_monday - timedelta(days=7)), midnight(this_monday)
        elif kind is TemporalKind.LAST_N_DAYS:
            start, end = local_now - timedelta(days=expression.days or 1), local_now
        elif kind is TemporalKind.THIS_MONTH:
            start, end = midnight(today.replace(day=1)), local_now
        elif kind is TemporalKind.LAST_MONTH:
            this_month = today.replace(day=1)
            end = midnight(this_month)
            start = midnight((this_month - timedelta(days=1)).replace(day=1))
        elif kind is TemporalKind.CALENDAR_MONTH:
            month = expression.month or today.month
            year = expression.year
            if year is None:
                year = today.year if month <= today.month else today.year - 1
            start = midnight(date(year, month, 1))
            end = midnight(date(year + (month == 12), month % 12 + 1, 1))
        elif kind is TemporalKind.BETWEEN_DATES:
            start = midnight(expression.start_date)  # type: ignore[arg-type]
            end = midnight(expression.end_date + timedelta(days=1))  # inclusive end date
        elif kind is TemporalKind.BEFORE_DATE:
            end = midnight(expression.start_date)  # type: ignore[arg-type]
        elif kind is TemporalKind.AFTER_DATE:
            start, end = midnight(expression.start_date + timedelta(days=1)), local_now  # type: ignore[operator]
        return ResolvedTimeWindow(
            start_at=start.astimezone(UTC) if start else None,
            end_at=end.astimezone(UTC) if end else None,
            timezone=self.timezone_name,
        )
