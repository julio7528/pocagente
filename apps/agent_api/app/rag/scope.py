"""Canonical application-owned scope for persistent Knowledge retrieval."""

from enum import StrEnum


class KnowledgeScope(StrEnum):
    """Trusted retrieval scope carried separately from the user query."""

    NONE = "NONE"
    INTERNAL = "INTERNAL"
    PUBLIC_GETNET = "PUBLIC_GETNET"


def require_persistent_knowledge_scope(scope: KnowledgeScope) -> KnowledgeScope:
    """Reject the orchestration-only NONE scope at persistent RAG boundaries."""

    if scope not in {KnowledgeScope.INTERNAL, KnowledgeScope.PUBLIC_GETNET}:
        raise ValueError("persistent retrieval requires INTERNAL or PUBLIC_GETNET scope")
    return scope
