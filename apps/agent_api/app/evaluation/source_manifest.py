"""Versioned exact source identity adapter for dataset-v1 expectations."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.agent_api.app.rag.models import RetrievalProvenance

from .contracts import EvaluationDatasetContractError, LoadedRAGDataset
from .adapters import RAGEvaluationClass, classify_rag_case


def normalize_dataset_path(value: str) -> str:
    candidate = value.strip().replace("\\", "/")
    if not candidate or "?" in candidate or "#" in candidate:
        raise EvaluationDatasetContractError("Dataset source path must be nonblank and have no query or fragment")
    if re.match(r"^[A-Za-z]:/", candidate):
        raise EvaluationDatasetContractError("Dataset source path must be repository-relative without traversal")
    path = PurePosixPath(candidate)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise EvaluationDatasetContractError("Dataset source path must be repository-relative without traversal")
    normalized = str(path)
    if normalized in {"", "."}:
        raise EvaluationDatasetContractError("Dataset source path must be a file path")
    return normalized


class EvaluationSourceManifestEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    dataset_path: str = Field(min_length=1)
    document_key: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)

    @model_validator(mode="after")
    def path_is_normalized(self) -> EvaluationSourceManifestEntry:
        if self.dataset_path != normalize_dataset_path(self.dataset_path):
            raise ValueError("Manifest dataset_path must be normalized")
        return self


class EvaluationSourceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_version: Literal["1.0", "1.1"]
    entries: tuple[EvaluationSourceManifestEntry, ...]

    @model_validator(mode="after")
    def entries_are_unambiguous(self) -> EvaluationSourceManifest:
        paths = tuple(entry.dataset_path for entry in self.entries)
        identities = tuple((entry.document_key, entry.source_reference) for entry in self.entries)
        if len(paths) != len(set(paths)):
            raise ValueError("Evaluation Source Manifest dataset paths must be unique")
        if len(identities) != len(set(identities)):
            raise ValueError("Evaluation Source Manifest runtime identities must be unambiguous")
        return self


DATASET_V1_SOURCE_MANIFEST = EvaluationSourceManifest(
    dataset_version="1.0",
    entries=(
        EvaluationSourceManifestEntry(
            dataset_path="knowledge/internal/cancellation-process/robot_01_r1/pdd-cancelamento.md",
            document_key="robot_01_r1/pdd-cancelamento",
            source_reference="knowledge/internal/cancellation-process/robot_01_r1",
        ),
        EvaluationSourceManifestEntry(
            dataset_path="knowledge/internal/cancellation-process/robot_01_r1/sdd-cancelamento.md",
            document_key="robot_01_r1/sdd-cancelamento",
            source_reference="knowledge/internal/cancellation-process/robot_01_r1",
        ),
        EvaluationSourceManifestEntry(
            dataset_path="knowledge/internal/cancellation-process/robot_01_r1/technical-overview.md",
            document_key="robot_01_r1/technical-overview",
            source_reference="knowledge/internal/cancellation-process/robot_01_r1",
        ),
        EvaluationSourceManifestEntry(
            dataset_path="knowledge/internal/cancellation-process/robot_02_r2/pdd-cancelamento.md",
            document_key="robot_02_r2/pdd-cancelamento",
            source_reference="knowledge/internal/cancellation-process/robot_02_r2",
        ),
        EvaluationSourceManifestEntry(
            dataset_path="knowledge/internal/cancellation-process/robot_02_r2/sdd-cancelamento.md",
            document_key="robot_02_r2/sdd-cancelamento",
            source_reference="knowledge/internal/cancellation-process/robot_02_r2",
        ),
        EvaluationSourceManifestEntry(
            dataset_path="knowledge/internal/cancellation-process/robot_02_r2/technical-overview.md",
            document_key="robot_02_r2/technical-overview",
            source_reference="knowledge/internal/cancellation-process/robot_02_r2",
        ),
    ),
)

DATASET_V11_SOURCE_MANIFEST = DATASET_V1_SOURCE_MANIFEST.model_copy(
    update={"dataset_version": "1.1"}
)


def source_manifest_for_version(version: str) -> EvaluationSourceManifest:
    manifests = {
        "1.0": DATASET_V1_SOURCE_MANIFEST,
        "1.1": DATASET_V11_SOURCE_MANIFEST,
    }
    try:
        return manifests[version]
    except KeyError as error:
        raise EvaluationDatasetContractError("Unsupported RAG manifest version") from error


def all_declared_dataset_paths(dataset: LoadedRAGDataset) -> frozenset[str]:
    return frozenset(
        normalize_dataset_path(path)
        for case in dataset.dataset.cases
        for path in case.expected_sources
    )


def required_retrieval_dataset_paths(dataset: LoadedRAGDataset) -> frozenset[str]:
    """Return only paths applicable to official retrieval-quality evaluation."""

    return frozenset(
        normalize_dataset_path(path)
        for case in dataset.dataset.cases
        if case.expects_evidence and classify_rag_case(case) in {
            RAGEvaluationClass.RETRIEVAL,
            RAGEvaluationClass.RULE_VS_OBSERVED,
        }
        for path in case.expected_sources
    )


def validate_manifest_coverage(dataset: LoadedRAGDataset, manifest: EvaluationSourceManifest) -> None:
    if manifest.dataset_version != dataset.version:
        raise EvaluationDatasetContractError("Manifest dataset version does not match loaded RAG dataset")
    required = required_retrieval_dataset_paths(dataset)
    mapped = frozenset(entry.dataset_path for entry in manifest.entries)
    if mapped != required:
        missing = len(required - mapped)
        extras = len(mapped - required)
        raise EvaluationDatasetContractError(f"Evaluation Source Manifest coverage is incomplete or has extras: missing={missing}, extras={extras}")


def expected_source_matches(
    dataset_path: str,
    provenance: RetrievalProvenance,
    manifest: EvaluationSourceManifest,
) -> bool:
    normalized = normalize_dataset_path(dataset_path)
    entry = next((item for item in manifest.entries if item.dataset_path == normalized), None)
    if entry is None:
        raise EvaluationDatasetContractError("Expected source path is absent from Evaluation Source Manifest")
    return provenance.document_key == entry.document_key and provenance.source_reference == entry.source_reference
