"""Validated PostgreSQL runtime configuration."""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


SslMode = Literal[
    "disable",
    "allow",
    "prefer",
    "require",
    "verify-ca",
    "verify-full",
]


class DatabaseConfig(BaseModel):
    """Immutable PostgreSQL connection and pool configuration."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(default="getnet_support", min_length=1)
    user: str = Field(default="getnet_app", min_length=1)
    password: SecretStr
    sslmode: SslMode = "disable"
    connect_timeout_seconds: int = Field(default=5, gt=0)
    pool_min_size: int = Field(default=1, ge=0)
    pool_max_size: int = Field(default=5, ge=1)
    pool_timeout_seconds: int = Field(default=5, gt=0)

    @field_validator("password")
    @classmethod
    def password_must_not_be_blank(cls, value: SecretStr) -> SecretStr:
        """Reject missing-equivalent empty secrets without exposing them."""

        if not value.get_secret_value():
            raise ValueError("password must not be empty")
        return value

    @model_validator(mode="after")
    def pool_max_must_cover_pool_min(self) -> DatabaseConfig:
        """Ensure the configured pool can contain its minimum size."""

        if self.pool_max_size < self.pool_min_size:
            raise ValueError("pool_max_size must be greater than or equal to pool_min_size")
        return self

    def psycopg_connection_kwargs(self) -> dict[str, object]:
        """Return the explicit credential handoff for a Psycopg connection."""

        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.user,
            "password": self.password.get_secret_value(),
            "sslmode": self.sslmode,
            "connect_timeout": self.connect_timeout_seconds,
        }


def load_database_config() -> DatabaseConfig:
    """Load database configuration from the approved environment variables."""

    return DatabaseConfig(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        database=os.getenv("POSTGRES_DB", "getnet_support"),
        user=os.getenv("POSTGRES_USER", "getnet_app"),
        password=os.environ.get("POSTGRES_PASSWORD"),
        sslmode=os.getenv("POSTGRES_SSLMODE", "disable"),
        connect_timeout_seconds=os.getenv("POSTGRES_CONNECT_TIMEOUT_SECONDS", "5"),
        pool_min_size=os.getenv("POSTGRES_POOL_MIN_SIZE", "1"),
        pool_max_size=os.getenv("POSTGRES_POOL_MAX_SIZE", "5"),
        pool_timeout_seconds=os.getenv("POSTGRES_POOL_TIMEOUT_SECONDS", "5"),
    )
