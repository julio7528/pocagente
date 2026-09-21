"""Structural chunking boundary for semantic document units."""

from enum import StrEnum
from hashlib import sha256

from ..models import Chunk, Document


class ChunkBoundary(StrEnum):
    """Approved semantic boundaries for future chunking."""

    SECTION = "section"
    BUSINESS_RULE = "business_rule"
    TECHNICAL_SYMBOL = "technical_symbol"


class StructuralChunker:
    """Split documents by meaning and structure, not only fixed size."""

    max_safeguard_chars = 4_000

    def chunk(self, document: Document) -> list[Chunk]:
        """Create deterministic Markdown structural units without semantic rewriting."""

        lines = document.content.splitlines()
        groups: list[tuple[str | None, list[str]]] = []
        section: str | None = None
        current: list[str] = []
        for line in lines:
            if line.startswith("#") and line.lstrip("#").startswith(" "):
                if current and "\n".join(current).strip():
                    groups.append((section, current))
                section = line.lstrip("#").strip()
                current = [line]
            else:
                current.append(line)
        if current and "\n".join(current).strip():
            groups.append((section, current))
        if not groups:
            groups = [(None, lines)]

        chunks: list[Chunk] = []
        for heading, group in groups:
            for content in self._safeguard_split("\n".join(group).strip()):
                order = len(chunks)
                boundary = self._boundary(content)
                digest = sha256(f"{document.document_id}:{order}:{content}".encode()).hexdigest()[:16]
                chunks.append(
                    Chunk(
                        chunk_id=f"{document.document_id}:{order}:{digest}",
                        document_id=document.document_id,
                        content=content,
                        metadata=document.metadata.model_copy(update={"section": heading}),
                        boundary_type=boundary,
                    )
                )
        return chunks

    def _safeguard_split(self, content: str) -> list[str]:
        """Split only exceptional blocks at paragraph boundaries."""

        if len(content) <= self.max_safeguard_chars:
            return [content]
        parts: list[str] = []
        current = ""
        for paragraph in content.split("\n\n"):
            candidate = paragraph if not current else f"{current}\n\n{paragraph}"
            if current and len(candidate) > self.max_safeguard_chars:
                parts.append(current)
                current = paragraph
            else:
                current = candidate
        if current:
            parts.append(current)
        return parts

    @staticmethod
    def _boundary(content: str) -> ChunkBoundary:
        lowered = content.lower()
        if "```" in content or any(token in lowered for token in ("def ", "class ", "função", "método")):
            return ChunkBoundary.TECHNICAL_SYMBOL
        if any(token in lowered for token in ("regra", "decisão", "deve ", "não deve", "must ")):
            return ChunkBoundary.BUSINESS_RULE
        return ChunkBoundary.SECTION
