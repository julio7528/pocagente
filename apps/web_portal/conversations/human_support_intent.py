"""Recognition of explicit human-support requests written in the client chat."""

from __future__ import annotations

import re
import unicodedata


_HUMAN_SUPPORT_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\b(?:quero|gostaria|preciso|desejo)\s+"
        r"(?:falar|falr|conversar)\s+com\s+"
        r"(?:um\s+|uma\s+)?(?:humano|atendente|pessoa)\b",
        r"\b(?:quero|gostaria|preciso|desejo)\s+(?:de\s+)?"
        r"(?:um\s+|uma\s+)?atendimento\s+humano\b",
        r"\b(?:quero|gostaria|preciso|desejo)\s+(?:de\s+)?"
        r"(?:um\s+|uma\s+)?atendente\b",
        r"\b(?:me\s+)?"
        r"(?:direciona|direcione|encaminha|encaminhe|transfere|transfira)"
        r"(?:\s+me)?\s+(?:para|pra|pro|ao)\s+(?:o\s+)?"
        r"atendimento(?:\s+humano)?\b",
        r"\b(?:alguma|uma)\s+pessoa\s+(?:pode|poderia|consegue)\s+me\s+ajudar\b",
    )
)


def requests_human_support(message: str) -> bool:
    """Return whether the client explicitly asked to continue with a person."""

    if not isinstance(message, str):
        return False
    normalized = unicodedata.normalize("NFKD", message.casefold())
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    return any(pattern.search(normalized) for pattern in _HUMAN_SUPPORT_PATTERNS)
