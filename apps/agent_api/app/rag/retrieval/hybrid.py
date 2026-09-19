"""Orchestration boundary for lexical and semantic candidate retrieval."""

from ..config import DEFAULT_RAG_CONFIG, RAGConfig
from ..models import SearchCandidate
from .lexical import LexicalRetriever
from .semantic import SemanticRetriever


class HybridRetriever:
    """Coordinate bounded lexical and semantic retrieval channels."""

    def __init__(
        self,
        lexical: LexicalRetriever,
        semantic: SemanticRetriever,
        config: RAGConfig | None = None,
    ) -> None:
        self._lexical = lexical
        self._semantic = semantic
        self._config = config or DEFAULT_RAG_CONFIG

    def search(self, query: str) -> list[SearchCandidate]:
        """Request bounded candidates from both channels in the future."""

        raise NotImplementedError("Hybrid retrieval orchestration is not implemented yet.")

