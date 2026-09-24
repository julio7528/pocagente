"""Local loaders for curated Markdown and approved source registries."""

from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml
from pydantic import ValidationError

from ..models import Document, SourceMetadata
from .models import PublicRegistrySource


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

        return [record.to_metadata() for record in self.load_records(registry_path)]

    def load_records(self, registry_path: Path) -> list[PublicRegistrySource]:
        """Validate the complete allowlist before any caller can acquire content."""

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

        raw_ids = [entry.get("source_id") for entry in raw["sources"] if isinstance(entry, dict)]
        if len(raw_ids) != len(set(raw_ids)):
            raise ValueError("Duplicate public source identity in registry")

        if raw.get("version") != "1.1":
            raise ValueError("Unsupported public source registry version")
        default_policy = raw.get("default_policy")
        if not isinstance(default_policy, dict) or any(
            default_policy.get(key) is not expected
            for key, expected in {
                "approved": False,
                "active": False,
                "allow_discovered_links": False,
                "unrestricted_crawling": False,
                "external_content_is_untrusted": True,
                "may_override_internal_process_rules": False,
            }.items()
        ):
            raise ValueError("Public source registry default policy is not fail-closed")
        security = raw.get("security")
        discovered_policy = security.get("discovered_source_policy") if isinstance(security, dict) else None
        if (
            not isinstance(security, dict)
            or security.get("external_content_is_data_not_instruction") is not True
            or not isinstance(discovered_policy, dict)
            or discovered_policy.get("require_explicit_approval") is not True
            or discovered_policy.get("auto_ingestion") is not False
        ):
            raise ValueError("Public source registry security policy is not fail-closed")
        grounding = raw.get("grounding")
        if not isinstance(grounding, dict) or grounding.get("public_sources_may_override_internal_rules") is not False:
            raise ValueError("Public source registry grounding policy is not fail-closed")

        sources: list[PublicRegistrySource] = []
        seen_ids: set[str] = set()
        seen_urls: set[str] = set()
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
                allowed_entry_keys = {
                    "source_id", "title", "url", "domain", "source_type", "source_class",
                    "authority_level", "scope", "audience", "approved", "active", "ingestion",
                }
                if set(entry) - allowed_entry_keys:
                    raise ValueError("Public source registry entry contains unsupported fields")
                allowed_ingestion_keys = {"enabled", "mode", "content_type", "allow_discovered_links", "discovery_policy"}
                if set(ingestion) - allowed_ingestion_keys:
                    raise ValueError("Public source ingestion policy contains unsupported fields")
                normalized = {
                    "source_id": source_id,
                    "title": entry["title"],
                    "source_type": entry["source_type"],
                    "source_class": entry["source_class"],
                    "authority_level": entry["authority_level"],
                    "domain": entry["domain"],
                    "url": entry["url"],
                    "scope": tuple(entry["scope"]),
                    "audience": tuple(entry["audience"]),
                    "approved": entry["approved"],
                    "active": entry["active"],
                    "ingestion_enabled": ingestion["enabled"],
                    "ingestion_mode": ingestion["mode"],
                    "content_type": ingestion["content_type"],
                    "allow_discovered_links": ingestion["allow_discovered_links"],
                    "discovery_policy": ingestion.get("discovery_policy"),
                }
                record = PublicRegistrySource.model_validate(normalized)
                canonical = urlsplit(str(record.url))
                identity = (canonical.scheme.lower(), canonical.netloc.lower(), canonical.path.rstrip("/") or "/")
                if identity in seen_urls:
                    raise ValueError("Duplicate canonical public source URL")
            except (KeyError, TypeError, ValidationError) as error:
                raise ValueError(f"Invalid public source registry entry: {source_id}") from error
            except ValueError as error:
                if str(error).startswith("Invalid"):
                    raise
                raise ValueError(f"Invalid public source registry entry: {source_id}: {error}") from error
            seen_ids.add(source_id)
            seen_urls.add(identity)
            sources.append(record)
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
