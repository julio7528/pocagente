"""Typed, bounded contracts for the read-only security dashboard."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.agent_api.app.security.models import (
    SecurityAction,
    SecurityEventType,
    SecurityResourceCategory,
    SecurityResult,
    SecurityReviewStatus,
)


class SecurityDashboardFilters(BaseModel):
    """The one canonical filter shared by every dashboard read operation."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    date_from: date | None = None
    date_to: date | None = None
    event_type: SecurityEventType | None = None
    source_component: str | None = Field(default=None, max_length=128)
    user_identifier: str | None = Field(default=None, max_length=128)

    @field_validator("source_component", "user_identifier")
    @classmethod
    def nonblank_optional_filter(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("optional filters must not be blank")
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def normalize_and_bound_dates(self) -> SecurityDashboardFilters:
        today = datetime.now(UTC).date()
        end = self.date_to or today
        start = self.date_from or (end - timedelta(days=29))
        if start > end:
            raise ValueError("date_from must not be after date_to")
        if (end - start).days + 1 > 90:
            raise ValueError("date range must not exceed 90 inclusive UTC days")
        object.__setattr__(self, "date_from", start)
        object.__setattr__(self, "date_to", end)
        return self

    @property
    def start_at(self) -> datetime:
        assert self.date_from is not None
        return datetime.combine(self.date_from, time.min, tzinfo=UTC)

    @property
    def end_before(self) -> datetime:
        assert self.date_to is not None
        return datetime.combine(self.date_to + timedelta(days=1), time.min, tzinfo=UTC)


class SecurityDashboardPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    page: int = Field(default=1, ge=1, le=1000)
    page_size: int = Field(default=25, ge=1, le=100)


class SecurityDashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    total_events: int = Field(ge=0)
    distinct_users: int = Field(ge=0)
    distinct_event_types: int = Field(ge=0)
    distinct_source_components: int = Field(ge=0)


class SecurityDashboardDay(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    date: date
    count: int = Field(ge=0)


class SecurityDashboardBreakdownRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str = Field(min_length=1, max_length=256)
    count: int = Field(ge=0)


class SecurityDashboardBreakdowns(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_types: tuple[SecurityDashboardBreakdownRow, ...]
    source_components: tuple[SecurityDashboardBreakdownRow, ...]
    users: tuple[SecurityDashboardBreakdownRow, ...]


class SecurityDashboardEventRow(BaseModel):
    """Allowlisted event-list row; no content or request payload is selected."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: int = Field(ge=1)
    occurred_at: datetime
    event_type: SecurityEventType
    source_component: str = Field(min_length=1, max_length=256)
    user_identifier: str | None = Field(default=None, max_length=128)
    resource_category: SecurityResourceCategory | None = None
    action_taken: SecurityAction
    result: SecurityResult
    review_status: SecurityReviewStatus


class SecurityDashboardEventPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    page: int = Field(ge=1, le=1000)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    items: tuple[SecurityDashboardEventRow, ...]


class SecurityDashboardEventDetail(SecurityDashboardEventRow):
    """Explicit safe event detail; review notes and raw payloads are omitted."""

    request_reference: str | None = Field(default=None, max_length=128)
    sanitized_content: str | None = Field(default=None, max_length=4000)
    reviewed_at: datetime | None = None
    created_at: datetime
