"""Deterministic redaction used before an AUDIT write is attempted."""

from __future__ import annotations

import re


_REDACTED = "[REDACTED]"
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"postgres(?:ql)?://[^\s'\"]+", re.IGNORECASE), _REDACTED),
    (
        re.compile(
            r"-----BEGIN(?: [A-Z]+)? PRIVATE KEY-----[\s\S]*?-----END(?: [A-Z]+)? PRIVATE KEY-----",
            re.IGNORECASE,
        ),
        _REDACTED,
    ),
    (re.compile(r"\bsk-[A-Za-z0-9_-]+\b", re.IGNORECASE), _REDACTED),
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
        _REDACTED,
    ),
    (
        re.compile(
            r"\b(?:Authorization\s*:\s*|authorization\s*=\s*)?Bearer\s+[^\s,;]+",
            re.IGNORECASE,
        ),
        _REDACTED,
    ),
    (
        re.compile(
            r"\b(?:password|passphrase|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|token|secret|cookie)"
            r"\s*(?:=|:|\bis\b)\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)",
            re.IGNORECASE,
        ),
        _REDACTED,
    ),
    (re.compile(r"\bSELECT\b[\s\S]*?(?:;|$)", re.IGNORECASE), _REDACTED),
    (re.compile(r"\bTraceback\b[\s\S]*", re.IGNORECASE), _REDACTED),
    (
        re.compile(r"(?:[A-Za-z]:\\|/)(?:[^\s]*?(?:secret|credential|\.env)[^\s]*)", re.IGNORECASE),
        _REDACTED,
    ),
)


def sanitize_security_content(value: str | None) -> str | None:
    """Return bounded safe event text, or ``None`` when it is unusable."""

    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    original = text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    if text == original:
        # A protected message that contains no concrete credential-shaped value
        # is still never persisted as a raw request body.
        return "Protected request detected; sensitive content withheld."
    return text[:4000] or None
