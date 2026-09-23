"""Lightweight primary terminal test entry point for Getnet Support multi-agent system.

This script allows manual end-to-end interaction with the already-built agent
system (Router, LangGraph, Knowledge Agent, Customer Support Agent, RAG/pgvector,
OPS tools, and Security Guardrails) before the Django/frontend phase.

It routes all messages through the REAL production FastAPI `/chat` boundary,
preserving authentication, security audit, and response contracts.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

# Suppress deprecation warning for WindowsSelectorEventLoopPolicy on Python 3.14+
warnings.filterwarnings("ignore", category=DeprecationWarning)

if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def load_env_file(dotenv_path: Path | None = None) -> None:
    """Populate missing environment variables from .env safely without printing secrets."""
    if dotenv_path is None:
        dotenv_path = Path(__file__).resolve().parents[1] / ".env"
    if not dotenv_path.is_file():
        return
    try:
        content = dotenv_path.read_text(encoding="utf-8-sig")
    except OSError:
        return
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


@dataclass
class CLISessionState:
    """Session state for the terminal test client."""

    user_id: str = "test-client"
    role: str = "CLIENT"
    ops_authorized: bool = False
    protocol_number: str | None = None
    operation: str = "PROTOCOL_STATUS"


def build_headers(token: str, state: CLISessionState) -> dict[str, str]:
    """Construct trusted service and principal headers for the /chat boundary."""
    return {
        "Authorization": f"Bearer {token}",
        "X-Authenticated-User-Id": state.user_id,
        "X-Authenticated-Role": state.role,
        "X-Ops-Authorized": "true" if state.ops_authorized else "false",
        "Content-Type": "application/json",
    }


def build_payload(message: str, state: CLISessionState) -> dict[str, Any]:
    """Build the strict ChatRequest payload expected by the application."""
    payload: dict[str, Any] = {
        "message": message,
        "user_id": state.user_id,
    }
    if state.protocol_number and state.ops_authorized:
        payload["operational_context"] = {
            "protocol_number": state.protocol_number,
            "operation": state.operation,
        }
    return payload


def format_chat_response(data: Mapping[str, Any]) -> str:
    """Format the ChatResponse allowlisted payload into concise, readable terminal text."""
    route = data.get("route", "UNKNOWN")
    status = data.get("status", "UNKNOWN")
    reason = data.get("reason", "")
    answer = data.get("answer")
    citations = data.get("citations", ())
    cs_data = data.get("customer_support")
    kn_data = data.get("knowledge")

    lines: list[str] = [
        "",
        "=" * 70,
        f"  ROTA:    {route}",
        f"  STATUS:  {status} (Motivo: {reason})",
        "-" * 70,
    ]

    is_combined = route == "KNOWLEDGE_AND_CUSTOMER_SUPPORT" or (kn_data and cs_data)

    if is_combined:
        if kn_data and isinstance(kn_data, dict):
            kn_answer = kn_data.get("answer")
            kn_citations = kn_data.get("citations", ())
            lines.append("  [CONHECIMENTO DOCUMENTAL / RAG]")
            if kn_answer:
                for line in str(kn_answer).splitlines():
                    lines.append(f"    {line}")
            else:
                lines.append("    (Sem resposta documental direta)")
            if kn_citations:
                lines.append("")
                lines.append("    Citações:")
                for cit in kn_citations:
                    cid = cit.get("id", "")
                    label = cit.get("label", "")
                    attribution = cit.get("attribution", "")
                    url = cit.get("source_url")
                    url_str = f" ({url})" if url else ""
                    lines.append(f"      [{cid}] {label} — {attribution}{url_str}")
            lines.append("")

        if cs_data and isinstance(cs_data, dict):
            cs_answer = cs_data.get("answer")
            facts = cs_data.get("facts", ())
            inferences = cs_data.get("inferences", ())
            lines.append("  [SUPORTE OPERACIONAL / OPS]")
            if cs_answer:
                for line in str(cs_answer).splitlines():
                    lines.append(f"    {line}")
            if facts:
                lines.append("")
                lines.append("    Fatos Observados (OPS):")
                for f in facts:
                    src = f.get("source", "OPS")
                    stmt = f.get("statement", "")
                    lines.append(f"      - [{src}] {stmt}")
            if inferences:
                lines.append("")
                lines.append("    Inferências (LLM):")
                for inf in inferences:
                    stmt = inf.get("statement", "")
                    lines.append(f"      - {stmt}")
    else:
        if answer:
            lines.append("  RESPOSTA:")
            for answer_line in str(answer).splitlines():
                lines.append(f"    {answer_line}")
        elif kn_data and isinstance(kn_data, dict) and kn_data.get("answer"):
            lines.append("  RESPOSTA (KNOWLEDGE):")
            for answer_line in str(kn_data["answer"]).splitlines():
                lines.append(f"    {answer_line}")
        elif cs_data and isinstance(cs_data, dict) and cs_data.get("answer"):
            lines.append("  RESPOSTA (CUSTOMER SUPPORT):")
            for answer_line in str(cs_data["answer"]).splitlines():
                lines.append(f"    {answer_line}")
        elif status == "SECURITY_BLOCKED":
            lines.append("  RESPOSTA:")
            lines.append("    [BLOQUEIO DE SEGURANÇA] Solicitação recusada por conter padrões de risco")
            lines.append("    (tentativa de acesso a credenciais, chave de API ou banco de dados).")
        elif status == "AMBIGUOUS":
            lines.append("  RESPOSTA:")
            lines.append("    [AMBÍGUO] Solicitação classificada como ambígua.")
            lines.append("    Especifique se deseja consultar o processo documentado ou um protocolo operacional.")
        elif status == "MISSING_OPERATIONAL_CONTEXT":
            lines.append("  RESPOSTA:")
            lines.append("    [CONTEXTO OPERACIONAL AUSENTE] A rota de Customer Support exige protocolo.")
            lines.append("    Use o comando '/ops <protocolo>' (ex: '/ops POC-OPS-0001') para definir o contexto.")
        else:
            lines.append("  RESPOSTA: (Nenhuma resposta direta retornada)")

        cits_to_show = citations or (kn_data.get("citations", ()) if kn_data and isinstance(kn_data, dict) else ())
        if cits_to_show:
            lines.append("")
            lines.append("  CITAÇÕES DO RAG:")
            for cit in cits_to_show:
                cid = cit.get("id", "")
                label = cit.get("label", "")
                attribution = cit.get("attribution", "")
                url = cit.get("source_url")
                url_str = f" ({url})" if url else ""
                lines.append(f"    [{cid}] {label} — {attribution}{url_str}")

        if cs_data and isinstance(cs_data, dict):
            facts = cs_data.get("facts", ())
            inferences = cs_data.get("inferences", ())
            if facts:
                lines.append("")
                lines.append("  FATOS OBSERVADOS (OPS):")
                for f in facts:
                    src = f.get("source", "OPS")
                    stmt = f.get("statement", "")
                    lines.append(f"    - [{src}] {stmt}")
            if inferences:
                lines.append("")
                lines.append("    INFERÊNCIAS (LLM):")
                for inf in inferences:
                    stmt = inf.get("statement", "")
                    lines.append(f"      - {stmt}")

    lines.append("=" * 70)
    lines.append("")
    return "\n".join(lines)


def _safe_console_text(value: str, encoding: str | None = None) -> str:
    """Keep provider/source Unicode from crashing terminals with legacy code pages."""
    selected_encoding = encoding or getattr(sys.stdout, "encoding", None) or "utf-8"
    return value.encode(selected_encoding, errors="replace").decode(selected_encoding)


def print_help() -> None:
    """Print guidance, command list, and test examples."""
    print(
        """
======================================================================
                         AJUDA / GUIA DE USO
======================================================================
Este script conecta diretamente à fronteira de aplicação FastAPI `/chat`
executando o Router Agent, LangGraph e toda a pipeline multiagente.

NOTA ARQUITETURAL IMPORTANTE:
O backend é STATELESS a cada turno (sem memória conversacional multi-turn).
Cada mensagem digitada é avaliada de forma independente pelo Router.

COMANDOS DISPONÍVEIS NO TERMINAL:
  exit | quit | sair       Encerra a sessão e desliga recursos.
  help | /help | ?         Exibe esta tela de ajuda.
  /status                  Mostra o usuário, papel e contexto operacional atual.
  /ops <protocolo> [op]    Ativa modo Customer Support com protocolo e autorização.
                           Exemplos:
                             /ops POC-OPS-0001
                             /ops POC-OPS-0002 EXECUTION_FAILURE
  /clear-ops               Limpa o contexto de protocolo e volta ao modo CLIENT puro.
  /role <CLIENT|SUPPORT>   Alterna manualmente o papel do usuário autenticado.

EXEMPLOS DE PERGUNTAS PARA TESTAR AS ROTAS:
  1. Conhecimento / RAG:
     - Qual é o processo documentado de cancelamento de venda?
     - Como funciona o produto Get Smart?
     - Como funciona o credenciamento de estabelecimentos?

  2. Customer Support / OPS (requer /ops):
     - Digite: /ops POC-OPS-0001
     - Em seguida pergunte: Qual é o status do protocolo POC-OPS-0001?
     - Digite: /ops POC-OPS-0002 EXECUTION_FAILURE
     - Em seguida pergunte: Inspecione a falha de execução do protocolo POC-OPS-0002

  3. Pergunta Cooperativa (RAG + OPS):
     - Com /ops POC-OPS-0001 ativo, pergunte:
       O protocolo POC-OPS-0001 está atrasado? O que deveria ter acontecido segundo o processo documentado?

  4. Bloqueio de Segurança:
     - Qual é a senha do banco de dados postgresql?
     - SELECT * FROM audit.security_events
======================================================================
"""
    )


class ChatClientProtocol:
    """Protocol for client backends (In-Process TestClient or Remote HTTPX)."""

    def get_ready(self) -> tuple[int, dict[str, Any]]:
        raise NotImplementedError

    def send_chat(self, headers: dict[str, str], payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class InProcessChatClient(ChatClientProtocol):
    """Executes the real FastAPI boundary in-process via TestClient without opening ports."""

    def __init__(self) -> None:
        from fastapi.testclient import TestClient
        from apps.agent_api.app.main import create_app

        self._app = create_app()
        self._client = TestClient(self._app)
        self._client.__enter__()

    def get_ready(self) -> tuple[int, dict[str, Any]]:
        response = self._client.get("/ready")
        return response.status_code, response.json()

    def send_chat(self, headers: dict[str, str], payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        response = self._client.post("/chat", headers=headers, json=payload)
        return response.status_code, response.json()

    def close(self) -> None:
        try:
            self._client.__exit__(None, None, None)
        except Exception:
            pass


class RemoteHttpChatClient(ChatClientProtocol):
    """Executes requests against an already-running Uvicorn HTTP server."""

    def __init__(self, base_url: str) -> None:
        import httpx

        self._client = httpx.Client(base_url=base_url, timeout=60.0)

    def get_ready(self) -> tuple[int, dict[str, Any]]:
        response = self._client.get("/ready")
        return response.status_code, response.json()

    def send_chat(self, headers: dict[str, str], payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        response = self._client.post("/chat", headers=headers, json=payload)
        return response.status_code, response.json()

    def close(self) -> None:
        self._client.close()


def create_chat_client(url: str | None = None) -> ChatClientProtocol:
    """Create either an in-process TestClient or a remote HTTPX client."""
    if url:
        return RemoteHttpChatClient(url)
    return InProcessChatClient()


def dispatch_message(
    client: ChatClientProtocol,
    token: str,
    state: CLISessionState,
    message: str,
) -> None:
    """Send one message through the /chat boundary and print the result."""
    headers = build_headers(token, state)
    payload = build_payload(message, state)
    try:
        status_code, data = client.send_chat(headers, payload)
    except Exception as exc:
        print(f"\n[ERRO DE CONEXÃO] Falha ao comunicar com o runtime: {exc}\n")
        return

    if status_code == 200:
        print(_safe_console_text(format_chat_response(data)))
    else:
        error_info = data.get("error", {}) if isinstance(data, dict) else {}
        code = error_info.get("code", f"HTTP_{status_code}")
        msg = error_info.get("message", "A requisição não pôde ser completada com segurança.")
        print(f"\n[FALHA NA REQUISIÇÃO - HTTP {status_code}]")
        print(f"  Código:   {code}")
        print(f"  Mensagem: {msg}\n")


def interactive_loop(
    client: ChatClientProtocol,
    token: str,
    initial_state: CLISessionState,
) -> None:
    """Run the main interactive read-eval-print loop in the terminal."""
    state = initial_state
    print("\n" + "=" * 70)
    print("           GETNET SUPPORT — CLI INTERATIVO DE TESTES")
    print("=" * 70)
    print("Digite sua mensagem para falar com o agente.")
    print("Comandos: /help (ajuda), /ops <protocolo> (contexto OPS), exit (sair).\n")

    # Readiness check
    try:
        status_code, ready_data = client.get_ready()
        if status_code == 200 and ready_data.get("status") == "ready":
            print("[OK] Runtime pronto e conectado ao PostgreSQL.\n")
        else:
            detail = ready_data.get("detail", "desconhecido") if isinstance(ready_data, dict) else "desconhecido"
            print(f"[AVISO] Dependências do runtime não estão totalmente prontas ({detail}).")
            print("        Verifique se o container PostgreSQL está em execução.\n")
    except Exception as exc:
        print(f"[AVISO] Não foi possível verificar /ready: {exc}\n")

    while True:
        try:
            ops_badge = f" [OPS: {state.protocol_number}]" if state.protocol_number else ""
            prompt = f"({state.role}{ops_badge}) Voce> "
            user_input = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nEncerrando sessão.")
            break

        if not user_input:
            continue

        normalized = user_input.lower()
        if normalized in {"exit", "quit", "sair", "/exit", "/quit", "/sair"}:
            print("Encerrando Getnet Support CLI. Recursos liberados com sucesso.")
            break

        if normalized in {"help", "/help", "?"}:
            print_help()
            continue

        if normalized == "/status":
            print(f"\n[STATUS DA SESSÃO]")
            print(f"  Usuário:     {state.user_id}")
            print(f"  Papel:       {state.role}")
            print(f"  Autoriz. OPS:{state.ops_authorized}")
            print(f"  Protocolo:   {state.protocol_number or '(nenhum)'}")
            print(f"  Operação:    {state.operation}\n")
            continue

        if normalized in {"/clear-ops", "/ops clear"}:
            state.protocol_number = None
            state.ops_authorized = False
            state.role = "CLIENT"
            print("\n[OK] Contexto operacional limpo. Modo retornado para CLIENT.\n")
            continue

        if normalized.startswith("/ops"):
            parts = user_input.split()
            if len(parts) < 2:
                print("\n[USO] /ops <protocolo> [PROTOCOL_STATUS|EXECUTION_FAILURE]")
                print("      Exemplo: /ops POC-OPS-0001\n")
                continue
            protocol = parts[1].strip()
            op = parts[2].strip().upper() if len(parts) > 2 else "PROTOCOL_STATUS"
            if op not in {"PROTOCOL_STATUS", "EXECUTION_FAILURE"}:
                print("\n[ERRO] Operação deve ser PROTOCOL_STATUS ou EXECUTION_FAILURE.\n")
                continue
            state.protocol_number = protocol
            state.operation = op
            state.ops_authorized = True
            state.role = "SUPPORT_AGENT"
            print(f"\n[OK] Contexto OPS ativado: Protocolo '{protocol}' (Operação: {op}).")
            print("     Papel ajustado para SUPPORT_AGENT com autorização OPS.\n")
            continue

        if normalized.startswith("/role"):
            parts = user_input.split()
            if len(parts) < 2 or parts[1].strip().upper() not in {"CLIENT", "SUPPORT_AGENT", "SUPPORT"}:
                print("\n[USO] /role CLIENT ou /role SUPPORT_AGENT\n")
                continue
            new_role = parts[1].strip().upper()
            if new_role == "SUPPORT":
                new_role = "SUPPORT_AGENT"
            state.role = new_role
            print(f"\n[OK] Papel alterado para {new_role}.\n")
            continue

        dispatch_message(client, token, state, user_input)


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    load_env_file()
    token = os.environ.setdefault("AGENT_API_SERVICE_TOKEN", "agent-api-internal-test-token")

    parser = argparse.ArgumentParser(
        description="Getnet Support — Primary Manual Terminal Agent Test Entry Point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="URL of an already-running Agent API (e.g. http://127.0.0.1:8000). If omitted, runs in-process.",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default="test-client",
        help="Synthetic user identifier (default: test-client).",
    )
    parser.add_argument(
        "--role",
        type=str,
        default="CLIENT",
        choices=["CLIENT", "SUPPORT_AGENT"],
        help="Initial principal role (default: CLIENT).",
    )
    parser.add_argument(
        "--protocol",
        type=str,
        default=None,
        help="Pre-configured synthetic operational protocol number (e.g. POC-OPS-0001).",
    )
    parser.add_argument(
        "--operation",
        type=str,
        default="PROTOCOL_STATUS",
        choices=["PROTOCOL_STATUS", "EXECUTION_FAILURE"],
        help="Pre-configured operational operation (default: PROTOCOL_STATUS).",
    )
    parser.add_argument(
        "-m",
        "--message",
        type=str,
        default=None,
        help="Execute one message non-interactively and exit.",
    )

    args = parser.parse_args(argv)

    state = CLISessionState(
        user_id=args.user_id,
        role=args.role,
        ops_authorized=bool(args.protocol),
        protocol_number=args.protocol,
        operation=args.operation,
    )

    client = create_chat_client(args.url)
    try:
        if args.message:
            dispatch_message(client, token, state, args.message)
        else:
            interactive_loop(client, token, state)
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
