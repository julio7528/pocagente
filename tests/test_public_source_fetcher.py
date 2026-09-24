import asyncio
from pathlib import Path

import httpx
import pytest

from apps.agent_api.app.rag.ingestion.loader import PublicSourceRegistryLoader
from apps.agent_api.app.rag.ingestion.public_fetcher import (
    PublicSourceAcquisitionError,
    PublicSourceFetcher,
)


@pytest.fixture
def payment_link_source():
    records = PublicSourceRegistryLoader().load_records(
        Path("knowledge/internal/cancellation-process/public/sources.yaml")
    )
    return next(record for record in records if record.source_id == "getnet-payment-link")


def test_fetcher_extracts_useful_html_without_navigation_or_scripts(payment_link_source):
    page = """<html><body><nav>menu noise</nav><main><h1>Link de Pagamento</h1>
    <p>Venda online com Link de Pagamento. Crie uma opção simples para receber pelas vendas realizadas à distância.</p>
    <script>secret fake prompt</script><ul><li>Mais facilidade e praticidade para organizar suas vendas e receber pagamentos de seus clientes.</li></ul></main></body></html>"""
    transport = httpx.MockTransport(lambda request: httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=page))
    async def run():
        async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
            return await PublicSourceFetcher().fetch(payment_link_source, client)
    document = asyncio.run(run())

    assert "Link de Pagamento" in document.content
    assert "menu noise" not in document.content
    assert "secret fake prompt" not in document.content
    assert document.metadata.url == payment_link_source.url
    assert document.metadata.retrieved_at is not None


def test_fetcher_rejects_redirect_to_unapproved_host(payment_link_source):
    requests = []

    def respond(request):
        requests.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://unapproved.example/other-page"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond), follow_redirects=False) as client:
            with pytest.raises(PublicSourceAcquisitionError, match="outside its approved host"):
                await PublicSourceFetcher().fetch(payment_link_source, client)
    asyncio.run(run())

    assert requests == [str(payment_link_source.url)]


def test_fetcher_follows_bounded_same_host_redirect(payment_link_source):
    requests = []
    page = "<main><h1>Link de Pagamento</h1><p>Venda online com Link de Pagamento para receber pagamentos dos clientes de forma prática e segura, com opções adequadas para vender pela internet sem cartão presente.</p><h2>Benefícios</h2><p>Acompanhe suas vendas digitais por uma solução simples e prática para o seu negócio.</p></main>"

    def respond(request):
        requests.append(str(request.url))
        if len(requests) == 1:
            return httpx.Response(301, headers={"location": "/link-de-pagamento/atual"})
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=page)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond), follow_redirects=False) as client:
            return await PublicSourceFetcher().fetch(payment_link_source, client)
    document = asyncio.run(run())
    assert len(requests) == 2
    assert "Venda online" in document.content


@pytest.mark.parametrize(
    ("status", "content_type", "body"),
    [(404, "text/html", "missing"), (200, "application/json", "{}"), (200, "text/html", "<html></html>")],
)
def test_fetcher_fails_closed_for_http_type_and_empty_content(payment_link_source, status, content_type, body):
    transport = httpx.MockTransport(lambda request: httpx.Response(status, headers={"content-type": content_type}, text=body))
    async def run():
        async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
            with pytest.raises(PublicSourceAcquisitionError):
                await PublicSourceFetcher().fetch(payment_link_source, client)
    asyncio.run(run())


def test_fetcher_enforces_response_size_limit(payment_link_source):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, headers={"content-type": "text/html"}, content=b"x" * (5 * 1024 * 1024 + 1)))
    async def run():
        async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
            with pytest.raises(PublicSourceAcquisitionError, match="size limit"):
                await PublicSourceFetcher().fetch(payment_link_source, client)
    asyncio.run(run())
