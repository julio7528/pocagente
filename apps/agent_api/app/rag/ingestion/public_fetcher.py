"""Bounded acquisition and extraction for exact approved public URLs."""

from __future__ import annotations

from datetime import UTC, datetime
from html.parser import HTMLParser
from io import BytesIO
import re
from urllib.parse import urljoin, urlsplit

import httpx

from ..models import Document, SourceMetadata
from .models import PublicRegistrySource


_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
_SKIP_TAGS = frozenset({"script", "style", "nav", "header", "footer", "aside", "form", "button", "template", "noscript", "svg"})
_BLOCK_TAGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####", "p": "", "li": "- "}


class _PageTextExtractor(HTMLParser):
    """Extract useful visible headings, paragraphs and list items; never follows links."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._capture: list[str] | None = None
        self._prefix = ""
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth or tag not in _BLOCK_TAGS:
            return
        if self._capture is not None:
            self._finish_block()
        self._capture = []
        self._prefix = _BLOCK_TAGS[tag]

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if not self._skip_depth and tag in _BLOCK_TAGS:
            self._finish_block()

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and self._capture is not None and data.strip():
            self._capture.append(" ".join(data.split()))

    def close(self) -> None:
        super().close()
        self._finish_block()

    def _finish_block(self) -> None:
        if self._capture is None:
            return
        text = re.sub(r"\s+", " ", " ".join(self._capture)).strip()
        if text:
            self.blocks.append(f"{self._prefix} {text}".strip())
        self._capture = None
        self._prefix = ""


class PublicSourceAcquisitionError(ValueError):
    """A safe, controlled acquisition or extraction failure."""


class PublicSourceFetcher:
    """Fetch only validated registry records with bounded HTTP and extraction."""

    async def fetch(self, source: PublicRegistrySource, client: httpx.AsyncClient) -> Document:
        if not (source.approved and source.active and source.ingestion_enabled):
            raise PublicSourceAcquisitionError("Public registry source is not eligible for acquisition")

        try:
            target_url = str(source.url)
            for redirect_number in range(3):
                async with client.stream(
                    "GET",
                    target_url,
                    follow_redirects=False,
                    headers={"Accept": "text/html, application/pdf", "User-Agent": "getnet-support-approved-source-ingestion/1.0"},
                ) as response:
                    if response.is_redirect:
                        if redirect_number >= 2:
                            raise PublicSourceAcquisitionError("Approved public source exceeded redirect limit")
                        location = response.headers.get("location")
                        if not location:
                            raise PublicSourceAcquisitionError("Approved public source returned an invalid redirect")
                        redirected = urljoin(target_url, location)
                        parsed = urlsplit(redirected)
                        if (
                            parsed.scheme != "https"
                            or parsed.hostname is None
                            or parsed.hostname.lower() != source.domain.lower()
                            or parsed.username is not None
                            or parsed.password is not None
                            or parsed.port not in (None, 443)
                            or parsed.query
                            or parsed.fragment
                        ):
                            raise PublicSourceAcquisitionError("Approved public source redirected outside its approved host")
                        target_url = redirected
                        continue
                    response.raise_for_status()
                    media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    expected = "text/html" if source.content_type == "html" else "application/pdf"
                    if media_type != expected:
                        raise PublicSourceAcquisitionError("Approved public source returned an unexpected content type")
                    body = bytearray()
                    async for part in response.aiter_bytes():
                        body.extend(part)
                        if len(body) > _MAX_RESPONSE_BYTES:
                            raise PublicSourceAcquisitionError("Approved public source exceeded the response size limit")
                break
        except PublicSourceAcquisitionError:
            raise
        except (httpx.HTTPError, OSError) as error:
            raise PublicSourceAcquisitionError("Approved public source could not be acquired") from error

        if source.content_type == "html":
            content = self._extract_html(bytes(body))
        else:
            content = self._extract_pdf(bytes(body))
        if len(content) < 200 or len(content.splitlines()) < 2:
            raise PublicSourceAcquisitionError("Approved public source did not contain enough extractable text")

        retrieved_at = datetime.now(UTC)
        metadata = SourceMetadata(
            source_id=source.source_id,
            document_id=source.source_id,
            title=source.title,
            source_type=source.source_type,
            source_class=source.source_class,
            domain=source.domain,
            url=source.url,
            retrieved_at=retrieved_at,
            approved=source.approved,
            active=source.active,
            ingestion_enabled=source.ingestion_enabled,
        )
        return Document(document_id=source.source_id, content=content, metadata=metadata)

    @staticmethod
    def _extract_html(body: bytes) -> str:
        try:
            text = body.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise PublicSourceAcquisitionError("Approved HTML source is not valid UTF-8") from error
        parser = _PageTextExtractor()
        try:
            parser.feed(text)
            parser.close()
        except Exception as error:
            raise PublicSourceAcquisitionError("Approved HTML source could not be parsed") from error
        return "\n\n".join(parser.blocks)

    @staticmethod
    def _extract_pdf(body: bytes) -> str:
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(body), strict=True)
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception as error:
            raise PublicSourceAcquisitionError("Approved PDF source could not be extracted") from error
        return "\n\n".join(page.strip() for page in pages if page.strip())
