"""Focused unit tests for the primary manual terminal test entry point (scripts/chat_cli.py)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from scripts.chat_cli import (
    ChatClientProtocol,
    CLISessionState,
    build_headers,
    build_payload,
    dispatch_message,
    format_chat_response,
    interactive_loop,
    load_env_file,
    _safe_console_text,
)


def test_load_env_file_populates_missing_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("TEST_CLI_VAR_A=hello\nTEST_CLI_VAR_B='world'\n# comment\nINVALID_LINE\n", encoding="utf-8")
    monkeypatch.delenv("TEST_CLI_VAR_A", raising=False)
    monkeypatch.setenv("TEST_CLI_VAR_B", "existing")

    load_env_file(dotenv)

    assert os_env("TEST_CLI_VAR_A") == "hello"
    assert os_env("TEST_CLI_VAR_B") == "existing"


def os_env(key: str) -> str | None:
    import os

    return os.environ.get(key)


def test_build_headers_and_payload_default_client() -> None:
    state = CLISessionState(user_id="user-1", role="CLIENT", ops_authorized=False)
    headers = build_headers("test-token", state)
    payload = build_payload("Test message", state)

    assert headers["Authorization"] == "Bearer test-token"
    assert headers["X-Authenticated-User-Id"] == "user-1"
    assert headers["X-Authenticated-Role"] == "CLIENT"
    assert headers["X-Ops-Authorized"] == "false"
    assert payload == {"message": "Test message", "user_id": "user-1"}


def test_build_headers_and_payload_with_ops_context() -> None:
    state = CLISessionState(
        user_id="user-ops",
        role="SUPPORT_AGENT",
        ops_authorized=True,
        protocol_number="POC-OPS-0001",
        operation="PROTOCOL_STATUS",
    )
    headers = build_headers("token-123", state)
    payload = build_payload("Check status", state)

    assert headers["Authorization"] == "Bearer token-123"
    assert headers["X-Authenticated-User-Id"] == "user-ops"
    assert headers["X-Authenticated-Role"] == "SUPPORT_AGENT"
    assert headers["X-Ops-Authorized"] == "true"
    assert payload == {
        "message": "Check status",
        "user_id": "user-ops",
        "operational_context": {
            "protocol_number": "POC-OPS-0001",
            "operation": "PROTOCOL_STATUS",
        },
    }


def test_format_chat_response_knowledge() -> None:
    data = {
        "route": "KNOWLEDGE",
        "status": "COMPLETED",
        "reason": "CAPABILITIES_COMPLETED",
        "answer": "O processo documentado é Cancelamento de Venda [C1].",
        "citations": [
            {
                "id": "C1",
                "label": "PDD Cancelamento",
                "attribution": "robot_01_r1/pdd-cancelamento",
                "source_url": None,
            }
        ],
    }
    output = format_chat_response(data)
    assert "ROTA:    KNOWLEDGE" in output
    assert "STATUS:  COMPLETED (Motivo: CAPABILITIES_COMPLETED)" in output
    assert "O processo documentado é Cancelamento de Venda [C1]." in output
    assert "[C1] PDD Cancelamento — robot_01_r1/pdd-cancelamento" in output


def test_format_chat_response_conversational_route_shows_safe_top_level_answer() -> None:
    output = format_chat_response({
        "status": "COMPLETED",
        "route": "CONVERSATIONAL",
        "answer": "Olá! Posso ajudar com produtos Getnet.",
        "citations": [],
        "reason": "BOUNDED_CONVERSATIONAL_RESPONSE",
    })
    assert "ROTA:    CONVERSATIONAL" in output
    assert "Olá! Posso ajudar com produtos Getnet." in output


def test_chat_output_replaces_characters_unavailable_in_legacy_console_codepages() -> None:
    rendered = _safe_console_text("Resposta pública ✓", "cp1252")
    assert "Resposta pública" in rendered
    assert "✓" not in rendered


def test_format_chat_response_customer_support() -> None:
    data = {
        "route": "CUSTOMER_SUPPORT",
        "status": "COMPLETED",
        "reason": "CAPABILITIES_COMPLETED",
        "answer": "O status observado do protocolo POC-OPS-0001 é COMPLETED.",
        "customer_support": {
            "status": "ANSWERED",
            "facts": [
                {
                    "source": "OPS_PROTOCOL_STATUS",
                    "statement": "Protocol POC-OPS-0001 has observed request status COMPLETED.",
                }
            ],
            "inferences": [
                {
                    "statement": "A solicitação foi concluída com sucesso.",
                }
            ],
        },
    }
    output = format_chat_response(data)
    assert "ROTA:    CUSTOMER_SUPPORT" in output
    assert "O status observado do protocolo POC-OPS-0001 é COMPLETED." in output
    assert "[OPS_PROTOCOL_STATUS] Protocol POC-OPS-0001 has observed request status COMPLETED." in output
    assert "A solicitação foi concluída com sucesso." in output


def test_format_chat_response_combined() -> None:
    data = {
        "route": "KNOWLEDGE_AND_CUSTOMER_SUPPORT",
        "status": "COMPLETED",
        "reason": "CAPABILITIES_COMPLETED",
        "answer": None,
        "knowledge": {
            "status": "ANSWERED",
            "answer": "Processo prevê retorno em até 48h [C1].",
            "citations": [
                {
                    "id": "C1",
                    "label": "SDD",
                    "attribution": "robot_01_r1/sdd",
                }
            ],
        },
        "customer_support": {
            "status": "ANSWERED",
            "answer": "O protocolo está no prazo.",
            "facts": [{"source": "OPS", "statement": "Protocol status COMPLETED"}],
            "inferences": [{"statement": "Sem atraso observado."}],
        },
    }
    output = format_chat_response(data)
    assert "ROTA:    KNOWLEDGE_AND_CUSTOMER_SUPPORT" in output
    assert "[CONHECIMENTO DOCUMENTAL / RAG]" in output
    assert "Processo prevê retorno em até 48h [C1]." in output
    assert "[C1] SDD — robot_01_r1/sdd" in output
    assert "[SUPORTE OPERACIONAL / OPS]" in output
    assert "O protocolo está no prazo." in output
    assert "Protocol status COMPLETED" in output
    assert "Sem atraso observado." in output


def test_format_chat_response_security_and_ambiguity() -> None:
    sec_data = {
        "route": "SECURITY_BLOCK",
        "status": "SECURITY_BLOCKED",
        "reason": "SECURITY_REQUEST_BLOCKED",
        "answer": "I can't provide protected credentials.",
    }
    sec_output = format_chat_response(sec_data)
    assert "ROTA:    SECURITY_BLOCK" in output_contains(sec_output, "SECURITY_BLOCK")

    amb_data = {
        "route": "AMBIGUOUS",
        "status": "AMBIGUOUS",
        "reason": "ROUTER_ROUTE_UNDETERMINED",
        "answer": None,
    }
    amb_output = format_chat_response(amb_data)
    assert "ROTA:    AMBIGUOUS" in amb_output
    assert "classificada como ambígua" in amb_output


def output_contains(text: str, token: str) -> str:
    assert token in text
    return text


class FakeChatClient(ChatClientProtocol):
    def __init__(self, response_code: int = 200, response_data: dict[str, Any] | None = None) -> None:
        self.response_code = response_code
        self.response_data = response_data or {"status": "COMPLETED", "route": "KNOWLEDGE", "answer": "OK"}
        self.sent_requests: list[tuple[dict[str, str], dict[str, Any]]] = []
        self.closed = False

    def get_ready(self) -> tuple[int, dict[str, Any]]:
        return 200, {"status": "ready", "detail": "Application runtime is ready."}

    def send_chat(self, headers: dict[str, str], payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        self.sent_requests.append((headers, payload))
        return self.response_code, self.response_data

    def close(self) -> None:
        self.closed = True


def test_dispatch_message_success(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeChatClient()
    state = CLISessionState()
    dispatch_message(client, "test-token", state, "Hello")

    captured = capsys.readouterr().out
    assert "ROTA:    KNOWLEDGE" in captured
    assert "OK" in captured
    assert len(client.sent_requests) == 1
    assert client.sent_requests[0][1]["message"] == "Hello"


def test_dispatch_message_error(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeChatClient(response_code=503, response_data={"error": {"code": "SERVICE_DOWN", "message": "Down"}})
    state = CLISessionState()
    dispatch_message(client, "test-token", state, "Hello")

    captured = capsys.readouterr().out
    assert "HTTP 503" in captured
    assert "SERVICE_DOWN" in captured


def test_interactive_loop_commands_and_exit(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeChatClient()
    state = CLISessionState()
    inputs = iter(
        [
            "/status",
            "/ops POC-OPS-0001 PROTOCOL_STATUS",
            "/status",
            "/clear-ops",
            "/role SUPPORT_AGENT",
            "/help",
            "sair",
        ]
    )

    with patch("builtins.input", lambda prompt="": next(inputs)):
        interactive_loop(client, "tok", state)

    captured = capsys.readouterr().out
    assert "GETNET SUPPORT — CLI INTERATIVO DE TESTES" in captured
    assert "Contexto OPS ativado: Protocolo 'POC-OPS-0001'" in captured
    assert "Contexto operacional limpo. Modo retornado para CLIENT." in captured
    assert "Papel alterado para SUPPORT_AGENT." in captured
    assert "AJUDA / GUIA DE USO" in captured
    assert "Encerrando Getnet Support CLI." in captured
