"""Opt-in official Phase 11 closure-remediation evidence for RAG dataset v1.1."""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

import pytest

from apps.agent_api.app.agents.router import RouterAgent
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.evaluation.adapters import RAGEvaluationClass
from apps.agent_api.app.evaluation.challenge_runner import ChallengeEvaluationRunner
from apps.agent_api.app.evaluation.loaders import validate_evaluation_contracts
from apps.agent_api.app.evaluation.metrics import MetricOutcome
from apps.agent_api.app.evaluation.rag_results import EvaluationExecutionMode
from apps.agent_api.app.evaluation.rag_runner import (
    RAGEvaluationRunner,
    RecordingAuditSink,
    RouterSecurityEvaluationBoundary,
)
from apps.agent_api.app.evaluation.reporting import build_phase11_report, serialize_report, write_report
from apps.agent_api.app.evaluation.report_results import OverallEvaluationOutcome
from apps.agent_api.app.evaluation.source_manifest import DATASET_V11_SOURCE_MANIFEST
from apps.agent_api.app.rag.embeddings.fastembed import FastEmbedAdapter
from apps.agent_api.app.rag.grounding.context_builder import ContextBuilder
from apps.agent_api.app.rag.retrieval.hybrid import HybridRetriever
from apps.agent_api.app.rag.retrieval.lexical import LexicalRetriever
from apps.agent_api.app.rag.retrieval.semantic import SemanticRetriever
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL Phase 11 closure evidence is opt-in",
)


def test_phase11_v11_closure_evidence_uses_real_local_rag(
    real_database_config,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    validated = validate_evaluation_contracts(
        project_root / "evaluation/rag/dataset-v1.1.yaml",
        project_root / "evaluation/challenge/scenarios-v1.yaml",
        DATASET_V11_SOURCE_MANIFEST,
    )

    async def execute() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            retriever = HybridRetriever(
                LexicalRetriever(None),  # type: ignore[arg-type]
                SemanticRetriever(None, FastEmbedAdapter()),  # type: ignore[arg-type]
                database=database,
            )
            rag_runner = RAGEvaluationRunner(
                validated.rag,
                mode=EvaluationExecutionMode.LOCAL_RAG,
                retriever=retriever,
                context_builder=ContextBuilder(),
                security_boundary=RouterSecurityEvaluationBoundary(
                    router=RouterAgent(), audit_sink=RecordingAuditSink()
                ),
                manifest=DATASET_V11_SOURCE_MANIFEST,
            )
            rag_results = await rag_runner.run()
            challenge_results = ChallengeEvaluationRunner(validated.challenge).run()
            report = build_phase11_report(
                validated.rag, rag_results, validated.challenge, challenge_results
            )
            rendered = serialize_report(report)
            synthetic_fragment = "sk-" + "PHASE11SYNTHETIC0001"

            assert len(rag_results) == validated.rag.entry_count == 27
            assert rag_runner.retrieval_invocation_count == 24
            assert Counter(item.case_class for item in rag_results) == Counter(
                {
                    RAGEvaluationClass.RETRIEVAL: 22,
                    RAGEvaluationClass.RULE_VS_OBSERVED: 1,
                    RAGEvaluationClass.SECURITY: 3,
                    RAGEvaluationClass.INSUFFICIENT_EVIDENCE: 1,
                }
            )
            assert tuple(item.case_id for item in rag_results) == tuple(
                case.id for case in validated.rag.dataset.cases
            )
            assert len(challenge_results) == validated.challenge.entry_count == 14
            assert synthetic_fragment not in rendered

            metrics = {metric.metric_id: metric for metric in report.metrics}
            print(
                "Phase 11 v1.1 closure metrics:",
                {
                    metric_id: (
                        item.numerator,
                        item.denominator,
                        str(item.rate),
                        item.outcome.value,
                    )
                    for metric_id, item in metrics.items()
                },
            )
            print("Phase 11 v1.1 overall:", report.overall_outcome.value)
            print(
                "Phase 11 v1.1 RAG statuses:",
                Counter(item.status.value for item in rag_results),
            )
            print(
                "Phase 11 v1.1 expected-source misses:",
                tuple(
                    (item.case_id, item.reason)
                    for item in rag_results
                    if item.retrieval is not None
                    and not item.retrieval.expected_source_found
                    and item.case_class is not RAGEvaluationClass.INSUFFICIENT_EVIDENCE
                ),
            )
            print(
                "Phase 11 v1.1 security evidence:",
                tuple(
                    (
                        item.case_id,
                        item.security.router_route.value,
                        item.security.blocked,
                        bool(item.security.event_types),
                    )
                    for item in rag_results
                    if item.security is not None
                ),
            )

            if os.getenv("GETNET_WRITE_PHASE11_V11_REPORT") == "1":
                write_report(
                    report,
                    project_root
                    / "evaluation"
                    / "reports"
                    / "phase11-evaluation-v1.1.json",
                )

            assert all(metric.outcome is MetricOutcome.PASS for metric in metrics.values())
            assert report.overall_outcome is OverallEvaluationOutcome.PASS
        finally:
            await database.close()

    run_async(execute())
