from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PORTAL_CONVERSATIONS = ROOT / "apps" / "web_portal" / "conversations"


def test_phase126_service_and_context_boundaries_exist():
    assert (PORTAL_CONVERSATIONS / "services.py").is_file()
    assert (PORTAL_CONVERSATIONS / "context.py").is_file()


def test_phase126_does_not_import_agent_runtime_or_http_clients():
    production = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (PORTAL_CONVERSATIONS / "services.py", PORTAL_CONVERSATIONS / "context.py")
    ).lower()
    prohibited = (
        "apps.agent_api",
        "httpx",
        "requests",
        "deepseek",
        "tavily",
        "fastembed",
        "app.rag",
        "app.ops",
        "auditrepository",
    )
    assert all(token not in production for token in prohibited)


def test_phase126_exposes_no_message_body_update_or_physical_delete_service():
    service = (PORTAL_CONVERSATIONS / "services.py").read_text(encoding="utf-8")
    assert "def update_message" not in service
    assert "def delete_message" not in service
    assert ".delete()" not in service
