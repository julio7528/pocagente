"""Secret-safe PostgreSQL infrastructure error translation."""

from __future__ import annotations

from psycopg import (
    DataError,
    Error,
    IntegrityError,
    InterfaceError,
    InternalError,
    NotSupportedError,
    OperationalError,
    ProgrammingError,
)
from psycopg_pool import PoolClosed, PoolTimeout


class SafeDatabaseError(Exception):
    """A stable database failure that never incorporates driver details."""

    error_code = "database_error"
    retryable = False
    default_message = "A database operation could not be completed."

    def __init__(self, *, retryable: bool | None = None) -> None:
        super().__init__(self.default_message)
        if retryable is not None:
            self.retryable = retryable


class SafeConnectionError(SafeDatabaseError):
    """A transient database infrastructure availability failure."""

    error_code = "database_connection_unavailable"
    retryable = False
    default_message = "Database connectivity is temporarily unavailable."


class SafeIntegrityError(SafeDatabaseError):
    """A database integrity rule rejected an operation."""

    error_code = "database_integrity_error"
    default_message = "The operation conflicts with a database integrity rule."


class SafeQueryError(SafeDatabaseError):
    """A database statement could not be processed."""

    error_code = "database_query_error"
    default_message = "The database could not process the requested operation."


def translate_database_error(error: Exception) -> SafeDatabaseError | None:
    """Return a safe error for recognised driver failures, otherwise ``None``.

    Deliberately ignoring driver text prevents DSNs, SQL, values, diagnostics, and
    credential material from entering public exception messages.
    """

    if isinstance(error, SafeDatabaseError):
        return error
    if isinstance(error, PoolTimeout):
        return SafeConnectionError(retryable=True)
    if isinstance(error, (PoolClosed, OperationalError)):
        return SafeConnectionError(retryable=False)
    if isinstance(error, IntegrityError):
        return SafeIntegrityError()
    if isinstance(
        error,
        (ProgrammingError, DataError, InternalError, NotSupportedError),
    ):
        return SafeQueryError()
    if isinstance(error, (InterfaceError, Error)):
        return SafeDatabaseError()
    return None
