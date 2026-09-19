"""Local loaders for curated Markdown and approved source registries."""

from pathlib import Path

from ..models import Document, SourceMetadata


class InternalMarkdownLoader:
    """Load curated internal Markdown without modifying source artifacts."""

    def load(self, path: Path, metadata: SourceMetadata) -> Document:
        """Load one local Markdown document in a future implementation."""

        raise NotImplementedError("Internal Markdown loading is not implemented yet.")


class PublicSourceRegistryLoader:
    """Load approved public-source metadata without network access."""

    def load(self, registry_path: Path) -> list[SourceMetadata]:
        """Load registry entries in a future implementation."""

        raise NotImplementedError("Public source registry loading is not implemented yet.")

