"""Immutable, sanitized contracts for the approved security audit boundary."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SecurityEventType(StrEnum):
    """Approved physical-model security-event values."""

    CREDENTIAL_REQUEST = "CREDENTIAL_REQUEST"
    SECRET_REQUEST = "SECRET_REQUEST"
    DATABASE_ACCESS_REQUEST = "DATABASE_ACCESS_REQUEST"
    SENSITIVE_INFRASTRUCTURE_REQUEST = "SENSITIVE_INFRASTRUCTURE_REQUEST"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    AUTHORIZATION_BYPASS_ATTEMPT = "AUTHORIZATION_BYPASS_ATTEMPT"
    SECURITY_POLICY_PROBE = "SECURITY_POLICY_PROBE"


class SecurityAuditStatus(StrEnum):
    RECORDED = "RECORDED"
    UNAVAILABLE = "UNAVAILABLE"


class SecurityAction(StrEnum):
    BLOCK = "BLOCK"
    DENY_ACCESS = "DENY_ACCESS"
    REDACT = "REDACT"
    SAFE_RESPONSE = "SAFE_RESPONSE"
    ESCALATE = "ESCALATE"


class SecurityResult(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    ERROR = "ERROR"


class SecurityReviewStatus(StrEnum):
    UNREVIEWED = "UNREVIEWED"
    REVIEWED = "REVIEWED"


class SecurityResourceCategory(StrEnum):
    """Approved protected-resource values from the AUDIT physical model."""

    DATABASE_CREDENTIAL = "DATABASE_CREDENTIAL"
    API_KEY = "API_KEY"
    PASSWORD = "PASSWORD"
    ACCESS_TOKEN = "ACCESS_TOKEN"
    PRIVATE_KEY = "PRIVATE_KEY"
    COOKIE = "COOKIE"
    CONNECTION_STRING = "CONNECTION_STRING"
    SECRET_LOCATION = "SECRET_LOCATION"
    PROTECTED_PATH = "PROTECTED_PATH"
    AUTHENTICATION_CONTROL = "AUTHENTICATION_CONTROL"
    INTERNAL_INFRASTRUCTURE = "INTERNAL_INFRASTRUCTURE"
    OTHER_PROTECTED_RESOURCE = "OTHER_PROTECTED_RESOURCE"


class SecurityClassification(BaseModel):
    """One deterministic, deduplicated security semantic owned by the Router."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: SecurityEventType
    resource_category: SecurityResourceCategory | None = None


class SecurityAuditContext(BaseModel):
    """Trusted request correlation supplied by the authenticated HTTP boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    user_identifier: str = Field(min_length=1, max_length=128)
    request_reference: str = Field(min_length=1, max_length=128)


class SanitizedSecurityEvent(BaseModel):
    """Allowlisted data accepted by the AUDIT repository; never raw request content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    occurred_at: datetime
    event_type: SecurityEventType
    source_component: Literal["router_security_guardrail"] = "router_security_guardrail"
    user_identifier: str | None = Field(default=None, min_length=1, max_length=128)
    request_reference: str | None = Field(default=None, min_length=1, max_length=128)
    resource_category: SecurityResourceCategory | None = None
    sanitized_content: str | None = Field(default=None, min_length=1, max_length=4000)
    action_taken: SecurityAction = SecurityAction.BLOCK
    result: SecurityResult = SecurityResult.SUCCESS
    review_status: SecurityReviewStatus = SecurityReviewStatus.UNREVIEWED

    def as_repository_record(self) -> dict[str, object]:
        """Return only the columns approved by ``AuditRepository``."""

        return self.model_dump(mode="python", exclude_none=True)


class SecurityAuditResult(BaseModel):
    """Safe result for a persistence attempt; no database diagnostics escape."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: SecurityAuditStatus
    event_ids: tuple[int, ...] = ()
    reason: str = Field(min_length=1, max_length=128)

    @property
    def event_id(self) -> int | None:
        """Phase 9 compatibility accessor for a single recorded event."""

        return self.event_ids[0] if len(self.event_ids) == 1 else None
