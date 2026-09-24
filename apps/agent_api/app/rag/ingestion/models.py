"""Immutable Phase 5 contracts, deliberately separate from database rows."""

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StrictBool, StrictStr, model_validator

from ..models import SourceMetadata


class PublicRegistrySource(BaseModel):
    """One strict exact-URL source record authorized by the public registry."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_id: StrictStr = Field(min_length=1)
    title: StrictStr = Field(min_length=1)
    url: HttpUrl
    domain: StrictStr = Field(min_length=1)
    source_type: Literal["public_getnet"]
    source_class: Literal[
        "official_website",
        "official_support",
        "official_product",
        "official_service",
        "official_contract",
        "official_technical_documentation",
        "official_catalog",
    ]
    authority_level: StrictStr = Field(min_length=1)
    scope: tuple[StrictStr, ...] = Field(min_length=1)
    audience: tuple[StrictStr, ...] = Field(min_length=1)
    approved: StrictBool
    active: StrictBool
    ingestion_enabled: StrictBool
    ingestion_mode: Literal["manual"]
    content_type: Literal["html", "pdf"]
    allow_discovered_links: StrictBool = False
    discovery_policy: dict[str, StrictBool] | None = None

    @model_validator(mode="after")
    def exact_approved_https_identity(self) -> PublicRegistrySource:
        if self.url.scheme != "https":
            raise ValueError("public source registry URL must use HTTPS")
        if self.url.host.lower() != self.domain.lower():
            raise ValueError("public source URL host must match its registry domain")
        if self.url.username or self.url.password or self.url.port not in (None, 443):
            raise ValueError("public source URL cannot contain credentials or a custom port")
        if self.url.query or self.url.fragment:
            raise ValueError("public source URL cannot contain query or fragment components")
        if self.allow_discovered_links:
            raise ValueError("public registry source cannot enable discovered-link ingestion")
        if self.ingestion_enabled and not self.allow_discovered_links and self.ingestion_mode != "manual":
            raise ValueError("approved public acquisition must use manual exact-URL mode")
        if self.source_class == "official_catalog" and self.active and self.ingestion_enabled:
            raise ValueError("active public catalogs cannot be ingestion-enabled")
        return self

    def to_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            source_id=self.source_id,
            title=self.title,
            source_type=self.source_type,
            source_class=self.source_class,
            domain=self.domain,
            url=self.url,
            approved=self.approved,
            active=self.active,
            ingestion_enabled=self.ingestion_enabled,
        )


class PreparedChunk(BaseModel):
    """A complete structural unit before embedding and FTS publication."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content: str = Field(min_length=1)
    chunk_order: int = Field(ge=0)
    section: str | None = None
    boundary_type: Literal["section", "business_rule", "technical_symbol"]
    content_type: Literal["TEXT", "BUSINESS_RULE", "TECHNICAL"]
    metadata: Mapping[str, object] = Field(default_factory=dict)


class PreparedDocument(BaseModel):
    """A normalized validated document ready for later publication."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str = Field(min_length=1)
    metadata: SourceMetadata
    normalized_content: str = Field(min_length=1)
    content_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    database_source_type: Literal["INTERNAL_DOCUMENT", "INTERNAL_POLICY", "PUBLIC_OFFICIAL"]
    database_origin: Literal["INTERNAL", "PUBLIC"]


class PreparedIngestion(BaseModel):
    """Result of Phase 5 preparation, with no embedding or tsvector payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Literal["INGEST", "REINGEST", "SKIPPED_UNCHANGED"]
    document: PreparedDocument
    chunks: tuple[PreparedChunk, ...] = ()
