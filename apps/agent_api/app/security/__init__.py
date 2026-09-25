"""Typed security-audit application boundary for protected requests.

Exports are lazy so persistence contracts can refer to security DTOs without
importing the application service back through ``AuditRepository``.
"""

__all__ = [
    "PostgresSecurityAuditSink",
    "SanitizedSecurityEvent",
    "SecurityClassification",
    "SecurityAuditContext",
    "SecurityAuditResult",
    "SecurityAuditService",
    "SecurityAuditSink",
    "SecurityAuditStatus",
    "SecurityEventType",
    "SecurityResourceCategory",
]


def __getattr__(name: str):
    if name in {"PostgresSecurityAuditSink", "SecurityAuditService", "SecurityAuditSink"}:
        from . import audit

        return getattr(audit, name)
    if name in {
        "SanitizedSecurityEvent",
        "SecurityClassification",
        "SecurityAuditContext",
        "SecurityAuditResult",
        "SecurityAuditStatus",
        "SecurityEventType",
        "SecurityResourceCategory",
    }:
        from . import models

        return getattr(models, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
