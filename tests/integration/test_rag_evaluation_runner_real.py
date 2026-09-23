"""Opt-in local PostgreSQL/FastEmbed Phase 11.3 boundary validation."""

from __future__ import annotations

import os
from collections import Counter

import pytest

from apps.agent_api.app.agents.router import RouterAgent
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.database.repositories.rag import RAGRepository
from apps.agent_api.app.evaluation.loaders import validate_evaluation_contracts
from apps.agent_api.app.evaluation.adapters import RAGEvaluationClass, classify_rag_case
from apps.agent_api.app.evaluation.rag_results import EvaluationCaseStatus, EvaluationExecutionMode
from apps.agent_api.app.evaluation.rag_runner import (
    RAGEvaluationRunner,
    RecordingAuditSink,
    RouterSecurityEvaluationBoundary,
)
from apps.agent_api.app.evaluation.source_manifest import DATASET_V1_SOURCE_MANIFEST
from apps.agent_api.app.rag.embeddings.fastembed import FastEmbedAdapter
from apps.agent_api.app.rag.grounding.context_builder import ContextBuilder
from apps.agent_api.app.rag.retrieval.hybrid import HybridRetriever
from apps.agent_api.app.rag.retrieval.lexical import LexicalRetriever, normalize_lexical_query
from apps.agent_api.app.rag.retrieval.semantic import SemanticRetriever
from apps.agent_api.app.rag.scope import KnowledgeScope
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL RAG evaluation is opt-in",
)


def test_real_local_rag_boundary_processes_all_cases_without_generation(
    real_database_config, tmp_path
) -> None:
    root = tmp_path  # keeps the test signature explicit without creating artifacts
    del root
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    validated = validate_evaluation_contracts(
        project_root / "evaluation/rag/dataset-v1.yaml",
        project_root / "evaluation/challenge/scenarios-v1.yaml",
        DATASET_V1_SOURCE_MANIFEST,
    )

    async def execute():
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            embed_adapter = FastEmbedAdapter()
            retriever = HybridRetriever(
                LexicalRetriever(None),  # type: ignore[arg-type]
                SemanticRetriever(None, embed_adapter),  # type: ignore[arg-type]
                database=database,
            )
            sink = RecordingAuditSink()
            runner = RAGEvaluationRunner(
                validated.rag,
                mode=EvaluationExecutionMode.LOCAL_RAG,
                retriever=retriever,
                context_builder=ContextBuilder(),
                security_boundary=RouterSecurityEvaluationBoundary(
                    audit_sink=sink
                ),
            )
            results = await runner.run()
            security_results = [item for item in results if item.security is not None]
            assert len(results) == validated.rag.entry_count == 25
            assert tuple(item.case_id for item in results) == tuple(case.id for case in validated.rag.dataset.cases)
            assert Counter(item.case_class for item in results) == Counter({
                RAGEvaluationClass.RETRIEVAL: 22,
                RAGEvaluationClass.RULE_VS_OBSERVED: 1,
                RAGEvaluationClass.SECURITY: 2,
            })
            assert len(security_results) == 2
            assert all(item.retrieval is None for item in security_results)
            assert runner.retrieval_invocation_count == 23
            rule_result = next(item for item in results if item.case_class is RAGEvaluationClass.RULE_VS_OBSERVED)
            assert rule_result.status in {EvaluationCaseStatus.NOT_MEASURABLE, EvaluationCaseStatus.FAIL}
            assert rule_result.retrieval is not None
            assert all(item.document_key and item.source_reference for item in rule_result.retrieval.results)
            counts = {status.value: sum(item.status is status for item in results) for status in EvaluationCaseStatus}
            security_summary = [
                (item.case_id, item.status.value, item.security.blocked if item.security else False)
                for item in security_results
            ]
            source_misses = [
                (item.case_id, item.reason)
                for item in results
                if item.retrieval is not None and not item.retrieval.expected_source_found
            ]
            security_routes = [
                (
                    item.case_id,
                    item.security.router_route.value if item.security else None,
                    item.security.blocked if item.security else False,
                    bool(item.security.event_types) if item.security else False,
                )
                for item in security_results
            ]
            print(f"Phase 11.3 LOCAL_RAG case counts: {counts}")
            print(f"Phase 11.3 LOCAL_RAG security findings: {security_summary}")
            print(f"Phase 11.3 LOCAL_RAG expected-source misses: {source_misses}")
            print(f"Phase 11.3 LOCAL_RAG security routes: {security_routes}")
            for case_id, _ in source_misses:
                case = next(item for item in validated.rag.dataset.cases if item.id == case_id)
                async with database.transaction() as connection:
                    repository = RAGRepository(connection)
                    await repository.begin_read_only_repeatable_read()
                    lexical = await repository.search_lexical_candidates(
                        normalize_lexical_query(case.question), 10, KnowledgeScope.INTERNAL
                    )
                    semantic = await repository.search_semantic_candidates(
                        embed_adapter.embed_query(case.question), 10, KnowledgeScope.INTERNAL
                    )
                final = await retriever.search(case.question, KnowledgeScope.INTERNAL)
                print(
                    "Phase 11.3 retrieval diagnostic:",
                    {
                        "case_id": case_id,
                        "lexical": [
                            (item.channel_rank, item.provenance.document_key, item.chunk.section)
                            for item in lexical
                        ],
                        "semantic": [
                            (item.channel_rank, item.provenance.document_key, item.chunk.section)
                            for item in semantic
                        ],
                        "final": [
                            (
                                item.rank,
                                item.provenance.document_key,
                                item.chunk.section,
                                item.lexical_rank,
                                item.semantic_rank,
                            )
                            for item in final
                        ],
                    },
                )
            return results
        finally:
            await database.close()

    run_async(execute())
