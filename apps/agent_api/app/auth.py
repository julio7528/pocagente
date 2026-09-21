"""Trusted service-to-service authentication for the internal FastAPI boundary."""

from __future__ import annotations

import hmac
import os
from enum import StrEnum

from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator


class PrincipalRole(StrEnum):
    CLIENT = "CLIENT"
    SUPPORT_AGENT = "SUPPORT_AGENT"


class ServiceAuthConfig(BaseModel):
    """Immutable secret-safe internal service authentication configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    service_token: SecretStr

    @field_validator("service_token")
    @classmethod
    def token_must_not_be_blank(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("service token must not be blank")
        return value


class AuthenticatedPrincipal(BaseModel):
    """Claims supplied by the authenticated future-Django service caller."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    user_id: str = Field(min_length=1, max_length=128)
    role: PrincipalRole
    can_read_operational_facts: bool = False


def load_service_auth_config() -> ServiceAuthConfig:
    """Load only the approved service token without exposing it."""

    try:
        return ServiceAuthConfig(service_token=os.environ.get("AGENT_API_SERVICE_TOKEN"))
    except ValidationError as error:
        raise RuntimeError("SERVICE_AUTHENTICATION_UNAVAILABLE") from error


_bearer = HTTPBearer(auto_error=False, scheme_name="InternalServiceBearer")


async def authenticate_internal_service(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> AuthenticatedPrincipal:
    """Authenticate the service before trusting identity or role headers."""

    config: ServiceAuthConfig | None = getattr(request.app.state, "auth_config", None)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SERVICE_AUTHENTICATION_UNAVAILABLE",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AUTHENTICATION_REQUIRED")
    expected = config.service_token.get_secret_value()
    if not hmac.compare_digest(credentials.credentials, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AUTHENTICATION_INVALID")

    user_id = request.headers.get("x-authenticated-user-id", "").strip()
    role_value = request.headers.get("x-authenticated-role", "").strip().upper()
    ops_value = request.headers.get("x-ops-authorized", "false").strip().lower()
    if not user_id or role_value not in {role.value for role in PrincipalRole}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AUTHENTICATED_PRINCIPAL_REQUIRED")
    if ops_value not in {"true", "false"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AUTHENTICATED_PRINCIPAL_INVALID")
    return AuthenticatedPrincipal(
        user_id=user_id,
        role=PrincipalRole(role_value),
        can_read_operational_facts=ops_value == "true",
    )
