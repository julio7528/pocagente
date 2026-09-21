"""Local loaders for curated Markdown and approved source registries."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ..models import Document, SourceMetadata


class InternalMarkdownLoader:
    """Load curated internal Markdown without modifying source artifacts."""

    def __init__(self, approved_root: Path | None = None) -> None:
        repository_root = Path(__file__).resolve().parents[5]
        self._approved_root = (approved_root or repository_root / "knowledge" / "internal").resolve()

    def load(self, path: Path, metadata: SourceMetadata) -> Document:
        """Load one curated UTF-8 Markdown file without side effects."""

        resolved_path = path.resolve()
        if not resolved_path.is_relative_to(self._approved_root):
            raise ValueError("Internal source is outside the approved knowledge/internal tree")
        if not resolved_path.is_file():
            raise ValueError(f"Internal source must be an existing regular file: {path}")
        if resolved_path.suffix.lower() not in {".md", ".markdown"}:
            raise ValueError("Internal source must be a Markdown file")
        try:
            content = resolved_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("Internal source must be valid UTF-8") from error
        return Document(
            document_id=metadata.document_id or metadata.source_id,
            content=content,
            metadata=metadata,
        )



class PublicSourceRegistryLoader:
    """Load approved public-source metadata without network access."""

    def load(self, registry_path: Path) -> list[SourceMetadata]:
        """Load approved public registrations only; never fetch their URLs."""

        if not registry_path.is_file():
            raise ValueError("Public source registry must be an existing regular file")
        try:
            raw: Any = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        except UnicodeDecodeError as error:
            raise ValueError("Public source registry must be valid UTF-8") from error
        except yaml.YAMLError as error:
            raise ValueError("Malformed public source registry") from error
        if not isinstance(raw, dict) or not isinstance(raw.get("sources"), list):
            raise ValueError("Public source registry requires a sources list")

        sources: list[SourceMetadata] = []
        seen_ids: set[str] = set()
        for entry in raw["sources"]:
            if not isinstance(entry, dict):
                raise ValueError("Public source registry entries must be mappings")
            source_id = entry.get("source_id")
            ingestion = entry.get("ingestion")
            if not isinstance(source_id, str) or not source_id.strip():
                raise ValueError("Public source registry entry requires source_id")
            if source_id in seen_ids:
                raise ValueError(f"Duplicate public source identity: {source_id}")
            if not isinstance(ingestion, dict):
                raise ValueError("Public source registry entry requires ingestion metadata")
            try:
                metadata = SourceMetadata(
                    source_id=source_id,
                    title=entry["title"],
                    source_type=entry["source_type"],
                    source_class=entry.get("source_class"),
                    domain=entry.get("domain"),
                    url=entry["url"],
                    approved=bool(entry.get("approved", False)),
                    active=bool(entry.get("active", False)),
                    ingestion_enabled=bool(ingestion.get("enabled", False)),
                )
            except (KeyError, ValidationError) as error:
                raise ValueError(f"Invalid public source registry entry: {source_id}") from error
            seen_ids.add(source_id)
            sources.append(metadata)
        return sorted(sources, key=lambda source: source.source_id)


def approved_active_public_domains(registry_path: Path) -> frozenset[str]:
    """Return approved active public domains from the authoritative registry only."""

    return frozenset(
        source.domain.lower()
        for source in PublicSourceRegistryLoader().load(registry_path)
        if source.approved
        and source.active
        and source.source_type == "public_getnet"
        and source.domain
    )
