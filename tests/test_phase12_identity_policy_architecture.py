"""Static checks for Phase 12.4 identity ownership and trust boundaries."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PORTAL = ROOT / "apps" / "web_portal"


def test_roles_are_a_single_closed_application_contract() -> None:
    model_source = (PORTAL / "accounts" / "models.py").read_text(encoding="utf-8")
    assert "class ApplicationRole(models.TextChoices)" in model_source
    assert "ROLE_VALUES = tuple(ApplicationRole.values)" in model_source
    for role in ("ADMIN", "CLIENT", "SUPPORT_AGENT"):
        assert f'{role} = "{role}"' in model_source
    assert "blocked = models.BooleanField" not in model_source


def test_account_policy_does_not_derive_ops_authority_or_import_agent_runtime() -> None:
    forbidden = (
        "apps.agent_api.app.agents",
        "apps.agent_api.app.rag",
        "apps.agent_api.app.database.repositories",
        "apps.agent_api.app.llm",
        "ops_authorized",
    )
    for relative in ("accounts/authorization.py", "accounts/services.py"):
        source = PORTAL / relative
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
        assert not any(
            module == prefix or module.startswith(prefix + ".")
            for module in modules
            for prefix in forbidden[:-1]
        )
        assert forbidden[-1] not in source.read_text(encoding="utf-8")


def test_approved_browser_routes_exist_and_no_public_registration_route() -> None:
    urls_path = PORTAL / "config" / "urls.py"
    source = urls_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(urls_path))
    declared_paths = [
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "path"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ]
    assert declared_paths == [
        "health/",
        "ready/",
        "login/",
        "password-reset/request/",
        "password-reset/request/confirm/",
        "logout/",
        "chat/",
        "support/",
        "admin-portal/",
        "admin/",
    ]
    assert not any(token in declared_paths for token in ("register", "signup", "create-account"))
    assert "register" not in "\n".join(
        str(path.relative_to(PORTAL)).lower() for path in PORTAL.rglob("*.py")
    )


def test_password_bootstrap_is_interactive_and_never_declares_defaults() -> None:
    command = (PORTAL / "accounts" / "management" / "commands" / "bootstrap_admin.py").read_text(
        encoding="utf-8"
    )
    assert "getpass.getpass" in command
    assert "Confirm password:" in command
    assert "bootstrap_first_admin" in command
    assert "admin123" not in command.lower()
    assert "set_password" not in command.lower()
