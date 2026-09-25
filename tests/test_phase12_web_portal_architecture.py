"""Static boundary checks for the Phase 12.2 Django service skeleton."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PORTAL = ROOT / "apps" / "web_portal"


def test_web_portal_is_separate_and_has_modular_package_boundaries() -> None:
    expected = {
        "config",
        "accounts",
        "conversations",
        "support",
        "admin_portal",
        "integrations",
        "templates",
        "static",
    }

    assert (PORTAL / "manage.py").is_file()
    assert expected <= {entry.name for entry in PORTAL.iterdir() if entry.is_dir()}
    assert (ROOT / "apps" / "agent_api" / "app" / "main.py").is_file()
    assert not (ROOT / "apps" / "frontend").exists()
    assert not (ROOT / "apps" / "backend").exists()


def test_django_apps_select_custom_user_and_initial_portal_migrations(monkeypatch) -> None:
    monkeypatch.setenv("DJANGO_SECRET_KEY", "phase12-test-only-key")
    from apps.web_portal.config import settings

    expected_apps = {
        "apps.web_portal.accounts.apps.AccountsConfig",
        "apps.web_portal.conversations.apps.ConversationsConfig",
        "apps.web_portal.support.apps.SupportConfig",
        "apps.web_portal.admin_portal.apps.AdminPortalConfig",
    }
    assert expected_apps <= set(settings.INSTALLED_APPS)

    executable_migrations = {
        path.parent.parent.name: path.name
        for path in PORTAL.glob("*/migrations/*.py")
        if path.name != "__init__.py"
    }
    assert executable_migrations == {
        "accounts": "0001_initial.py",
        "conversations": "0001_initial.py",
        "support": "0001_initial.py",
    }
    assert (PORTAL / "accounts" / "models.py").is_file()
    assert settings.AUTH_USER_MODEL == "accounts.User"
    assert settings.DATABASES["default"]["OPTIONS"]["options"] == "-c search_path=portal"


def test_portal_has_no_direct_agent_or_data_domain_imports() -> None:
    forbidden_prefixes = (
        "apps.agent_api.app.agents",
        "apps.agent_api.app.rag",
        "apps.agent_api.app.database.repositories",
        "apps.agent_api.app.llm",
        "apps.agent_api.app.web",
        "langgraph",
        "fastembed",
        "tavily",
        "deepseek",
    )

    for source in PORTAL.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        imported_modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.append(node.module)

        violations = [
            module
            for module in imported_modules
            if any(
                module == prefix or module.startswith(prefix + ".")
                for prefix in forbidden_prefixes
            )
        ]
        assert violations == [], f"{source.relative_to(ROOT)} imports {violations}"


def test_portal_secrets_are_environment_backed_and_browser_areas_are_scoped() -> None:
    settings_source = (PORTAL / "config" / "settings.py").read_text(
        encoding="utf-8"
    )
    assert 'os.getenv("DJANGO_SECRET_KEY")' in settings_source
    assert "must be configured in the environment" in settings_source
    assert 'os.getenv("POSTGRES_PASSWORD", "")' in settings_source

    expected_templates = {
        "accounts/login.html",
        "accounts/403.html",
        "accounts/role_landing.html",
        "conversations/chat.html",
        "conversations/unavailable.html",
    }
    actual_templates = {
        path.relative_to(PORTAL / "templates").as_posix()
        for path in (PORTAL / "templates").rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    }
    assert expected_templates <= actual_templates
    assert (PORTAL / "static" / "portal.css").is_file()
    browser_files = list((PORTAL / "templates").rglob("*.html")) + list(
        (PORTAL / "static").rglob("*.js")
    )
    browser_content = "\n".join(path.read_text(encoding="utf-8") for path in browser_files)
    for secret_name in (
        "AGENT_API_SERVICE_TOKEN",
        "DEEPSEEK_API_KEY",
        "TAVILY_API_KEY",
        "POSTGRES_PASSWORD",
    ):
        assert secret_name not in browser_content
