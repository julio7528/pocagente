"""Static security and scope checks for Phase 12.5 browser access control."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PORTAL = ROOT / "apps" / "web_portal"


def test_session_limits_and_cookie_policy_are_server_configured() -> None:
    settings = (PORTAL / "config" / "settings.py").read_text(encoding="utf-8")
    assert "PORTAL_SESSION_INACTIVITY_SECONDS = 30 * 60" in settings
    assert "PORTAL_SESSION_ABSOLUTE_SECONDS = 8 * 60 * 60" in settings
    assert '"WEB_PORTAL_SECURE_COOKIES"' in settings
    assert "SESSION_COOKIE_HTTPONLY = True" in settings
    assert 'SESSION_COOKIE_SAMESITE = "Lax"' in settings
    assert "csrf_exempt" not in settings


def test_browser_templates_expose_no_dead_controls_or_trusted_claims() -> None:
    templates = PORTAL / "templates"
    html = "\n".join(path.read_text(encoding="utf-8") for path in templates.rglob("*.html")).lower()
    non_admin_html = "\n".join(
        path.read_text(encoding="utf-8")
        for area in ("accounts", "conversations", "support")
        for path in (templates / area).rglob("*.html")
    ).lower()
    forbidden = (
        "remember me",
        "cadastrar",
        "criar conta",
        "signup",
        "agent_api_service_token",
        "deepseek_api_key",
        "tavily_api_key",
        "postgres_password",
        "ops_authorized",
    )
    assert all(value not in html for value in forbidden)
    login = (templates / "accounts" / "login.html").read_text(encoding="utf-8").lower()
    assert "esqueci minha senha" in login
    assert "password-reset-request" in login
    # The product ADMIN form may choose a target user's role. Public and
    # non-admin browser forms must never establish the caller's role.
    assert 'name="role"' not in non_admin_html
    assert "{% csrf_token %}" in html


def test_browser_layer_has_no_fastapi_or_data_repository_dependency() -> None:
    browser_sources = (
        PORTAL / "accounts" / "views.py",
        PORTAL / "accounts" / "session_policy.py",
        PORTAL / "accounts" / "forms.py",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in browser_sources)
    forbidden = (
        "apps.agent_api",
        "AuditRepository",
        "OperationalRepository",
        "FastEmbed",
        "Tavily",
        "DeepSeek",
        "AGENT_API_SERVICE_TOKEN",
    )
    assert all(value not in source for value in forbidden)


def test_login_does_not_honor_browser_next_or_role_claims() -> None:
    source = (PORTAL / "accounts" / "views.py").read_text(encoding="utf-8")
    assert "ROLE_LANDINGS" in source
    assert 'request.POST.get("role")' not in source
    assert 'request.GET.get("next")' not in source
    assert 'request.POST.get("next")' not in source
