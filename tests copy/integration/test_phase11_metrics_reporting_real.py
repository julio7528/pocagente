"""Opt-in official Phase 11.5 aggregation over real local RAG evidence."""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

import pytest

from apps.agent_api.app.agents.router import RouterAgent
from apps.agent_api.app.database.connection import PostgresDatabase
from apps.agent_api.app.evaluation.challenge_runner import ChallengeEvaluationRunner
from apps.agent_api.app.evaluation.loaders import validate_evaluation_contracts
from apps.agent_api.app.evaluation.metrics import MetricOutcome
from apps.agent_api.app.evaluation.rag_results import EvaluationExecutionMode
from apps.agent_api.app.evaluation.reporting import build_phase11_report, write_report
from apps.agent_api.app.evaluation.rag_runner import (
    RAGEvaluationRunner,
    RecordingAuditSink,
    RouterSecurityEvaluationBoundary,
)
from apps.agent_api.app.evaluation.source_manifest import DATASET_V1_SOURCE_MANIFEST
from apps.agent_api.app.rag.embeddings.fastembed import FastEmbedAdapter
from apps.agent_api.app.rag.grounding.context_builder import ContextBuilder
from apps.agent_api.app.rag.retrieval.hybrid import HybridRetriever
from apps.agent_api.app.rag.retrieval.lexical import LexicalRetriever
from apps.agent_api.app.rag.retrieval.semantic import SemanticRetriever
from tests.integration.support import run_async


pytestmark = pytest.mark.skipif(
    os.getenv("GETNET_RUN_DB_INTEGRATION") != "1",
    reason="real PostgreSQL metrics evidence is opt-in",
)


def test_phase11_metrics_report_aggregates_real_local_rag_and_challenge(
    real_database_config,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    validated = validate_evaluation_contracts(
        project_root / "evaluation/rag/dataset-v1.yaml",
        project_root / "evaluation/challenge/scenarios-v1.yaml",
        DATASET_V1_SOURCE_MANIFEST,
    )

    async def execute() -> None:
        database = PostgresDatabase(real_database_config)
        await database.open()
        try:
            retriever = HybridRetriever(
                LexicalRetriever(None),
                SemanticRetriever(None, FastEmbedAdapter()),
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
            )
            rag_results = await rag_runner.run()
            challenge_results = ChallengeEvaluationRunner(validated.challenge).run()
            report = build_phase11_report(
                validated.rag, rag_results, validated.challenge, challenge_results
            )
            if os.getenv("GETNET_WRITE_PHASE11_REPORT") == "1":
                write_report(
                    report,
                    project_root / "evaluation" / "reports" / "phase11-evaluation-v1.json",
                )
            metrics = {metric.metric_id: metric for metric in report.metrics}
            print("Phase 11.5 metrics:", {
                metric_id: (item.numerator, item.denominator, str(item.rate), item.outcome.value)
                for metric_id, item in metrics.items()
            })
            print("Phase 11.5 overall:", report.overall_outcome.value)
            assert report.rag_case_count == validated.rag.entry_count == 25
            assert report.challenge_scenario_count == validated.challenge.entry_count == 14
            assert sum(Counter(item.status.value for item in rag_results).values()) == 25
            assert metrics["expected_source_top5_rate"].denominator == 23
            assert metrics["provenance_success_rate"].denominator == 23
            assert metrics["challenge_scenario_gate"].outcome is MetricOutcome.PASS
            assert report.overall_outcome.value in {
                "FAIL", "INCOMPLETE_NOT_MEASURABLE", "PASS",
            }
        finally:
            await database.close()

    run_async(execute())
