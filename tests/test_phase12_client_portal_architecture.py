from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONVERSATIONS = ROOT / "apps" / "web_portal" / "conversations"
TEMPLATES = ROOT / "apps" / "web_portal" / "templates" / "conversations"
STATIC = ROOT / "apps" / "web_portal" / "static"


def test_client_portal_uses_django_routes_templates_and_same_origin_forms():
    urls = (CONVERSATIONS / "urls.py").read_text(encoding="utf-8")
    page = (TEMPLATES / "chat.html").read_text(encoding="utf-8")
    assert "chat/new/" not in urls  # names are composed under the chat/ prefix
    assert "new/" in urls and "messages/" in urls
    assert "{% csrf_token %}" in page
    assert 'method="post"' in page
    assert "{{ item.body }}" in page
    assert "|safe" not in page


def test_client_portal_has_no_agent_network_or_browser_credentials():
    files = (
        CONVERSATIONS / "views.py",
        CONVERSATIONS / "forms.py",
        TEMPLATES / "chat.html",
        TEMPLATES / "unavailable.html",
        STATIC / "client-chat.js",
    )
    content = "\n".join(path.read_text(encoding="utf-8") for path in files).lower()
    forbidden = (
        "apps.agent_api",
        "httpx",
        "xmlhttprequest",
        "localhost:8000",
        "agent-api",
        "deepseek",
        "tavily",
        "fastembed",
        "langgraph",
        "agent_api_service_token",
        "postgres_password",
        "ops_authorized",
        "csrf_exempt",
    )
    assert all(item not in content for item in forbidden)
    assert "fetch(liveregion.dataset.livepollurl" in content
    assert 'credentials: "same-origin"' in content
    page = (TEMPLATES / "chat.html").read_text(encoding="utf-8")
    assert "data-live-poll-url=\"{% url 'chat-updates' conversation.id %}\"" in page


def test_client_portal_has_responsive_and_accessible_foundations():
    page = (TEMPLATES / "chat.html").read_text(encoding="utf-8")
    css = (STATIC / "portal.css").read_text(encoding="utf-8")
    for marker in ("<header", "<aside", "<main", "<footer", "aria-live", "<label", "aria-current"):
        assert marker in page
    assert "@media (max-width: 48rem)" in css
    assert ":focus-visible" in css
