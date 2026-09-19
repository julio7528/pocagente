"""Overridable configuration for retrieval and ranking boundaries."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EmbeddingProvider(StrEnum):
    """Supported embedding provider identifiers."""

    FASTEMBED = "fastembed"


class RetrievalStrategy(StrEnum):
    """Supported retrieval strategy identifiers."""

    HYBRID = "hybrid"


class RankingStrategy(StrEnum):
    """Supported ranking strategy identifiers."""

    RRF = "rrf"


class RAGConfig(BaseModel):
    """Application-injectable RAG defaults with no credential fields."""

    model_config = ConfigDict(frozen=True)

    lexical_candidate_limit: int = Field(default=10, ge=1)
    semantic_candidate_limit: int = Field(default=10, ge=1)
    final_top_k: int = Field(default=5, ge=1)
    embedding_provider: EmbeddingProvider = EmbeddingProvider.FASTEMBED
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    ranking_strategy: RankingStrategy = RankingStrategy.RRF


DEFAULT_RAG_CONFIG = RAGConfig()

