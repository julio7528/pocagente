"""Build and boundary checks for the Phase 12.15 web-portal image."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PORTAL = ROOT / "apps" / "web_portal"


def test_compose_has_the_existing_services_and_separate_web_portal() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    assert set(compose["services"]) == {"postgres", "agent-api", "web-portal"}

    postgres = compose["services"]["postgres"]
    assert postgres["volumes"] == ["getnet_support_pgdata:/var/lib/postgresql/data"]
    assert postgres["ports"] == ["127.0.0.1:5432:5432"]
    assert compose["volumes"]["getnet_support_pgdata"] is None

    agent_api = compose["services"]["agent-api"]
    assert agent_api["ports"] == ["127.0.0.1:8000:8000"]

    portal = compose["services"]["web-portal"]
    assert portal["build"] == {"context": "./apps/web_portal", "dockerfile": "Dockerfile"}
    assert portal["ports"] == ["127.0.0.1:8001:8001"]
    assert portal["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert "agent-api" not in portal["depends_on"]
    assert portal["environment"]["POSTGRES_HOST"] == "postgres"
    assert portal["environment"]["AGENT_API_INTERNAL_URL"] == "http://agent-api:8000"
    assert "network_mode" not in portal


def test_portal_image_has_no_secret_build_args_or_startup_mutations() -> None:
    dockerfile = (PORTAL / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.14-slim-bookworm" in dockerfile
    assert 'CMD ["uvicorn", "apps.web_portal.config.asgi:application"' in dockerfile
    assert "PYTHONPATH=/app" in dockerfile
    assert "--reload" not in dockerfile
    assert not any(line.strip().startswith("ARG ") for line in dockerfile.splitlines())
    assert all(
        command not in dockerfile.lower()
        for command in ("manage.py migrate", "bootstrap_admin", "collectstatic", "seed")
    )

    required_runtime = {"Django==6.1.1", "httpx==0.28.1", "pydantic==2.13.5", "psycopg[binary]==3.3.6", "uvicorn==0.53.0"}
    assert required_runtime == set(
        (PORTAL / "requirements-docker.txt").read_text(encoding="utf-8").splitlines()
    )


def test_runtime_secret_files_and_build_context_are_excluded() -> None:
    root_ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    portal_ignore = (PORTAL / ".dockerignore").read_text(encoding="utf-8")
    assert ".env" in root_ignore
    assert ".env.*" in root_ignore
    assert ".docker-secrets/" in root_ignore
    assert "*.sqlite3" in root_ignore
    assert "/.env" in portal_ignore
    assert "/.env.*" in portal_ignore
    assert "/.docker-secrets/" in portal_ignore
    assert "/.git/" in portal_ignore
    assert "/.venv/" in portal_ignore
    assert "*.sqlite3" in portal_ignore
    assert "**/test*.py" in portal_ignore

    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "DJANGO_SECRET_KEY=replace-with-a-long-random-local-secret" in example
    assert "POSTGRES_PASSWORD=replace-with-a-local-postgres-password" in example
    assert "AGENT_API_SERVICE_TOKEN=" in example


def test_portal_database_and_agent_endpoints_are_runtime_configured() -> None:
    settings = (PORTAL / "config" / "settings.py").read_text(encoding="utf-8")
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    portal_environment = compose["services"]["web-portal"]["environment"]

    assert 'os.getenv("DJANGO_SECRET_KEY")' in settings
    assert '"-c search_path=portal"' in settings
    assert 'os.getenv("POSTGRES_HOST", "127.0.0.1")' in settings
    assert portal_environment["POSTGRES_HOST"] == "postgres"
    assert portal_environment["AGENT_API_INTERNAL_URL"] == "http://agent-api:8000"


def test_asgi_serves_local_portal_static_assets_and_safe_health_routes() -> None:
    asgi = (PORTAL / "config" / "asgi.py").read_text(encoding="utf-8")
    urls = (PORTAL / "config" / "urls.py").read_text(encoding="utf-8")
    health = (PORTAL / "config" / "health.py").read_text(encoding="utf-8")

    assert "ASGIStaticFilesHandler(get_asgi_application())" in asgi
    assert 'path("health/", health.liveness' in urls
    assert 'path("ready/", health.readiness' in urls
    assert "SELECT 1" in health
    assert '{"status": "unavailable"}, status=503' in health
    assert "str(exc)" not in health


def test_compose_and_browser_sources_do_not_publish_fastapi_or_trusted_claims() -> None:
    browser_sources = list((PORTAL / "templates").rglob("*.html")) + list(
        (PORTAL / "static").rglob("*.js")
    )
    browser_content = "\n".join(path.read_text(encoding="utf-8") for path in browser_sources)
    assert "agent-api:8000" not in browser_content
    assert "AGENT_API_INTERNAL_URL" not in browser_content
    assert "AGENT_API_SERVICE_TOKEN" not in browser_content
    assert "X-Authenticated-Role" not in browser_content
    assert "X-Ops-Authorized" not in browser_content
