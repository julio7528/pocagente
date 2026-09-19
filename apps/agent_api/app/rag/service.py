"""Primary provider-neutral RAG interface for future agents."""

from collections.abc import Sequence
from pathlib import Path

from .config import DEFAULT_RAG_CONFIG, RAGConfig
from .models import RAGResult


class RAGService:
    """Facade that shields agents from storage and provider implementations."""

    def __init__(self, config: RAGConfig | None = None) -> None:
        self._config = config or DEFAULT_RAG_CONFIG

    def search(self, query: str, top_k: int | None = None) -> RAGResult:
        """Search indexed knowledge through the future hybrid pipeline."""

        raise NotImplementedError("Hybrid RAG search is not implemented yet.")

    def ingest_internal(self, paths: Sequence[Path]) -> None:
        """Ingest curated internal documents through the future pipeline."""

        raise NotImplementedError("Internal document ingestion is not implemented yet.")

    def ingest_public(self, registry_path: Path) -> None:
        """Ingest approved public registry sources through the future pipeline."""

        raise NotImplementedError("Public source ingestion is not implemented yet.")

