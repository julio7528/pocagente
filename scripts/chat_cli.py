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
import re
import sys
from time import perf_counter
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from apps.agent_api.app.telemetry import RuntimeEventKind, RuntimeTelemetryEvent, RuntimeTelemetrySink

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
    role: str = "SUPPORT_AGENT"
    ops_authorized: bool = True
    protocol_number: str | None = None
    operation: str | None = None
    analytics_grain_context: str | None = None
    protocol_context_transient: bool = False


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
        context = {"protocol_number": state.protocol_number}
        if state.operation:
            context["operation"] = state.operation
        if state.protocol_context_transient:
            context["transient"] = True
        payload["operational_context"] = context
    if state.analytics_grain_context:
        payload["analytics_grain_context"] = state.analytics_grain_context
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
    human_data = data.get("human")

    lines: list[str] = [
        "",
        "=" * 70,
        f"  ROTA:    {route}",
        f"  STATUS:  {status} (Motivo: {reason})",
        "-" * 70,
    ]

    intent = data.get("intent")
    if intent:
        lines.append(f"  INTENÇÃO: {intent}")
    if cs_data and isinstance(cs_data, dict):
        plan = cs_data.get("operational_plan")
        if isinstance(plan, dict):
            lines.append(f"  PLANO OPS: {plan.get('intent', 'UNKNOWN')}")
            selectors = {
                key: plan[key]
                for key in ("protocol_number", "run_id", "limit")
                if plan.get(key) is not None
            }
            if selectors:
                lines.append(f"    Seletores validados: {selectors}")

    is_combined = route == "KNOWLEDGE_AND_CUSTOMER_SUPPORT" or (kn_data and cs_data)

    if is_combined:
        if answer:
            lines.append("  SÍNTESE COOPERATIVA:")
            for line in str(answer).splitlines():
                lines.append(f"    {line}")
            lines.append("")
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
            if cs_answer and not answer:
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

    if human_data and isinstance(human_data, dict):
        lines.append("")
        lines.append("  [ATENDIMENTO HUMANO]")
        lines.append(f"    Estado: {human_data.get('state', 'UNKNOWN')}")
        if human_data.get("conversation_id"):
            lines.append(f"    Conversa: {human_data['conversation_id']}")
        if human_data.get("state") == "WAITING_CONFIRMATION":
            lines.append("    Aguardando confirmação explícita do usuário; ainda sem transferência para um operador.")

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
  /trace on|off            Liga ou desliga a telemetria de execução ao vivo.
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

    def __init__(self, telemetry_sink: RuntimeTelemetrySink | None = None) -> None:
        from fastapi.testclient import TestClient
        from apps.agent_api.app.main import create_app

        self._app = create_app(telemetry_sink=telemetry_sink)
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


def create_chat_client(
    url: str | None = None,
    telemetry_sink: RuntimeTelemetrySink | None = None,
) -> ChatClientProtocol:
    """Create either an in-process TestClient or a remote HTTPX client."""
    if url:
        return RemoteHttpChatClient(url)
    return InProcessChatClient(telemetry_sink=telemetry_sink)


class ConsoleTraceSink:
    """Render only validated runtime events; never derives events from input text."""

    _LLM_LABELS = {
        "conversational_response": "LLM resposta",
        "ops_synthesis_retry": "LLM sintese (nova tentativa)",
        "ops_planning": "LLM planejamento OPS",
        "ops_synthesis": "LLM síntese",
        "cooperative_synthesis": "Síntese cooperativa",
        "grounded_generation": "LLM grounded generation",
    }

    def __init__(self, enabled: bool = True, available: bool = True) -> None:
        self.enabled = enabled
        self.available = available

    @staticmethod
    def _duration(event: RuntimeTelemetryEvent) -> str:
        return f" ({event.elapsed_ms / 1000:.1f}s)" if event.elapsed_ms is not None else ""

    def emit(self, event: RuntimeTelemetryEvent) -> None:
        if not self.enabled or not self.available:
            return
        kind = event.kind
        label = kind.value
        detail = event.value or ""
        if kind is RuntimeEventKind.SECURITY:
            label = "Segurança"
            detail = {
                "PREFLIGHT_STARTED": "preflight iniciado",
                "ALLOWED": "ALLOWED",
                "SECURITY_BLOCK": "SECURITY_BLOCK",
                "CONTINUATION_INTERRUPTED": "continuação interrompida",
            }.get(event.value or "", "verificação concluída")
        elif kind is RuntimeEventKind.SECURITY_SEMANTIC:
            label = "Segurança semântica"
            detail = {"STARTED": "iniciado", "ALLOWED": "ALLOWED", "BLOCKED": "BLOCK", "CONTROLLED_ERROR": "CONTROLLED_ERROR"}.get(event.value or "", "concluído")
        elif kind is RuntimeEventKind.SECURITY_OUTPUT:
            label = "Validação de saída"
            detail = {"STARTED": "iniciada", "ALLOWED": "ALLOWED", "REDACTED": "REDACT", "BLOCKED": "BLOCK", "CONTROLLED_ERROR": "CONTROLLED_ERROR"}.get(event.value or "", "concluída")
        elif kind is RuntimeEventKind.CLASSIFIER:
            label = "Classificador semântico"
            detail = {
                "STARTED": "iniciado",
                "COMPLETED": "concluído",
                "CONTROLLED_ERROR": "CONTROLLED_ERROR",
                "NOT_CONFIGURED": "indisponível",
            }.get(event.value or "", "")
        elif kind is RuntimeEventKind.INTENT:
            label = "Intenção"
        elif kind is RuntimeEventKind.ROUTER:
            label = "Router"
        elif kind is RuntimeEventKind.CAPABILITY_NEED:
            label = "Necessidade semântica"
        elif kind is RuntimeEventKind.KNOWLEDGE_SCOPE:
            label = "KnowledgeScope"
        elif kind is RuntimeEventKind.KNOWLEDGE_QUERY:
            label = "Consulta RAG interna"
            detail = "formulada" if event.value == "COMPLETED" else "CONTROLLED_ERROR"
        elif kind is RuntimeEventKind.WEB_POLICY:
            label = "Web policy"
        elif kind is RuntimeEventKind.CAPABILITY:
            label = event.name or "Capability"
            detail = {
                "STARTED": "iniciado",
                "ANSWERED": "concluído",
                "COMPLETED": "concluído",
                "LLM_FORMULATED_RESPONSE": "concluído (LLM)",
                "BOUNDED_CONVERSATIONAL_RESPONSE": "fallback seguro",
                "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_EVIDENCE",
                "PROVIDER_ERROR": "CONTROLLED_ERROR",
                "UNAUTHORIZED": "UNAUTHORIZED",
                "OPERATIONAL_UNAVAILABLE": "CONTROLLED_ERROR",
                "CLARIFICATION_REQUIRED": "clarificação necessária",
            }.get(event.value or "", event.value or "")
        elif kind is RuntimeEventKind.OPS_AUTHORIZATION:
            label = "Autorização OPS"
            detail = "YES" if event.value == "ALLOWED" else "NO"
        elif kind is RuntimeEventKind.OPS_PLAN:
            if event.name == "analytics_grain":
                label, detail = "Grain", event.value or ""
            elif event.name == "analytics_metric":
                label, detail = "Métrica", event.value or ""
            elif event.name == "analytics_ordering":
                label, detail = "Ordenacao analitica", event.value or ""
            elif event.name == "analytics_group_by":
                label, detail = "Agregacao", event.value or ""
            elif event.name == "analytics_window":
                label, detail = "Janela temporal", event.value or ""
            elif event.name == "analytics_interval":
                label = "Intervalo resolvido"
                start = event.start_date.isoformat() if event.start_date else "início aberto"
                end = event.end_date.isoformat() if event.end_date else "fim aberto"
                detail = f"{start} .. {end}"
            elif event.name == "analytics_robot":
                label, detail = "Filtro robot", event.value or ""
            elif event.name == "analytics_outcome":
                label, detail = "Filtro resultado", event.value or ""
            elif event.name == "analytics_status":
                label, detail = "Filtro status", event.value or ""
            elif event.name == "evidence_need":
                label = "Evidência solicitada OPS"
                detail = event.value or ""
            elif event.name == "discovery_order":
                label = "Ordenação descoberta OPS"
                detail = event.value or ""
            elif event.name == "investigation_round":
                label = "Investigação OPS"
                detail = f"rodada {(event.value or '').removeprefix('ROUND_')}"
            elif event.name == "evidence_sufficiency":
                label = "Suficiência de evidências"
                detail = event.value or ""
            else:
                label = "Plano operacional"
                detail = event.value or "plano validado"
            if event.protocol_number:
                detail += f" (protocolo={event.protocol_number})"
            if event.limit is not None:
                detail += f" (limit={event.limit})"
        elif kind is RuntimeEventKind.OPS_TOOL:
            label = f"Ferramenta OPS {event.name or ''}".strip()
            detail = {
                "STARTED": "iniciada",
                "SUCCESS": "concluída",
                "NOT_FOUND": "nenhum registro",
                "DENIED": "DENIED",
                "CONTROLLED_ERROR": "CONTROLLED_ERROR",
            }.get(event.value or "", event.value or "")
        elif kind is RuntimeEventKind.REPOSITORY:
            label = f"OperationalRepository {event.name or ''}".strip()
            detail = {
                "COMPLETED": "consulta concluída",
                "CONTROLLED_ERROR": "CONTROLLED_ERROR",
            }.get(event.value or "", event.value or "")
        elif kind is RuntimeEventKind.RAG:
            label = {
                "lexical": "RAG lexical",
                "semantic": "RAG semântico",
                "rrf": "RRF",
                "hybrid_retrieval": "RAG híbrido",
            }.get(event.name or "", "RAG")
            detail = {
                "COMPLETED": "concluído",
                "SELECTED": "Top-K selecionado",
                "INTERNAL": "INTERNAL",
                "PUBLIC_GETNET": "PUBLIC_GETNET",
            }.get(event.value or "", event.value or "")
        elif kind is RuntimeEventKind.GROUNDING:
            label = "Live grounding" if event.name == "live_web" else "Grounded context"
            detail = event.value or "concluído"
        elif kind is RuntimeEventKind.WEB_SEARCH:
            label = "Web Search"
            detail = {
                "STARTED": "iniciado",
                "SUCCESS": "concluído",
                "NO_RESULTS": "nenhum resultado",
                "CONTROLLED_ERROR": "CONTROLLED_ERROR",
                "SKIPPED_LOCATION_REQUIRED": "ignorado; localização necessária",
            }.get(event.value or "", event.value or "concluído")
        elif kind is RuntimeEventKind.LLM:
            label = self._LLM_LABELS.get(event.name or "", "LLM")
            detail = {
                "STARTED": "iniciado",
                "COMPLETED": "concluído",
                "ANSWERED": "ANSWERED",
                "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_EVIDENCE",
                "CONTROLLED_ERROR": "CONTROLLED_ERROR",
                "INVALID_OUTPUT": "INVALID_OUTPUT",
            }.get(event.value or "", event.value or "")
            if event.count is not None and event.name == "grounded_generation" and event.value == "STARTED":
                detail += f" ({event.count} citações disponíveis)"
        elif kind in {
            RuntimeEventKind.PROVIDER_HTTP,
            RuntimeEventKind.PROVIDER_PARSE,
            RuntimeEventKind.PROVIDER_REQUEST,
        }:
            providers = {"deepseek": "DeepSeek", "tavily": "Web provider"}
            provider = providers.get(event.name or "", "Provider")
            phase_labels = {
                RuntimeEventKind.PROVIDER_HTTP: "HTTP",
                RuntimeEventKind.PROVIDER_PARSE: "parse",
                RuntimeEventKind.PROVIDER_REQUEST: "request total",
            }
            label = f"{provider} {phase_labels[kind]}"
            detail = {
                "STARTED": "iniciado",
                "RESPONSE_RECEIVED": "resposta recebida",
                "COMPLETED": "concluído",
                "CONTROLLED_ERROR": "CONTROLLED_ERROR",
            }.get(event.value or "", event.value or "")
            if kind is RuntimeEventKind.PROVIDER_HTTP and event.client_reused is not None:
                detail += " [cliente reutilizado]" if event.client_reused else " [cliente novo]"
            if kind is RuntimeEventKind.PROVIDER_HTTP and event.input_characters is not None:
                detail += f" [entrada {event.input_characters} caracteres]"
        elif kind is RuntimeEventKind.HUMAN:
            label = "Human Escalation"
        elif kind is RuntimeEventKind.SECURITY_AUDIT:
            label = "Security audit"
        elif kind is RuntimeEventKind.ORCHESTRATION:
            label = "Orquestração"

        if event.count is not None:
            noun = "resultado" if event.count == 1 else "resultados"
            if kind is RuntimeEventKind.REPOSITORY:
                detail += f" ({event.count} {noun})"
            elif kind in {RuntimeEventKind.RAG, RuntimeEventKind.GROUNDING, RuntimeEventKind.WEB_SEARCH}:
                detail += f" ({event.count} {noun})"
        if event.protocol_number and kind is RuntimeEventKind.REPOSITORY:
            detail += f" [{event.protocol_number}]"
        line = f"[TRACE] {label:<30} {detail}{self._duration(event)}"
        print(_safe_console_text(line), flush=True)


def dispatch_message(
    client: ChatClientProtocol,
    token: str,
    state: CLISessionState,
    message: str,
) -> None:
    """Send one message through the /chat boundary and print the result."""
    headers = build_headers(token, state)
    payload = build_payload(message, state)
    used_transient_protocol = state.protocol_context_transient
    try:
        status_code, data = client.send_chat(headers, payload)
    except Exception as exc:
        print("\n[ERRO] Falha ao comunicar com o runtime. Detalhes omitidos.\n")
        return
    if used_transient_protocol:
        state.protocol_number = None
        state.operation = None
        state.protocol_context_transient = False

    if status_code == 200:
        support = data.get("customer_support")
        plan = support.get("operational_plan") if isinstance(support, dict) else None
        analytics = plan.get("analytics") if isinstance(plan, dict) else None
        grain = analytics.get("grain") if isinstance(analytics, dict) else None
        if grain in {"PROTOCOL", "EXECUTION", "EVENT"}:
            state.analytics_grain_context = grain
        selected_protocol = support.get("selected_protocol_number") if isinstance(support, dict) else None
        if state.ops_authorized and isinstance(selected_protocol, str) and re.fullmatch(
            r"POC-OPS-\d{4}", selected_protocol, flags=re.IGNORECASE,
        ):
            state.protocol_number = selected_protocol.upper()
            state.operation = None
            state.protocol_context_transient = True
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
    trace_sink: ConsoleTraceSink | None = None,
) -> None:
    """Run the main interactive read-eval-print loop in the terminal."""
    state = initial_state
    print("\n" + "=" * 70)
    print("           GETNET SUPPORT — CLI INTERATIVO DE TESTES")
    print("=" * 70)
    print("Digite sua mensagem para falar com o agente.")
    print("Comandos: /help (ajuda), /ops <protocolo> (contexto OPS), /trace on|off, exit (sair).\n")

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
        print("[AVISO] Nao foi possivel verificar /ready. Detalhes omitidos.\n")

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

        # Carry only an explicitly named protocol as a non-authoritative
        # follow-up selector. Routing and OPS permission remain runtime-owned.
        explicit_protocols = tuple(dict.fromkeys(
            match.upper() for match in re.findall(r"\bPOC-OPS-\d{4}\b", user_input, re.IGNORECASE)
        ))
        if len(explicit_protocols) == 1 and state.ops_authorized:
            state.protocol_number = explicit_protocols[0]
            state.operation = None
            state.protocol_context_transient = False

        normalized = user_input.lower()
        if normalized in {"exit", "quit", "sair", "/exit", "/quit", "/sair"}:
            print("Encerrando Getnet Support CLI. Recursos liberados com sucesso.")
            break

        if normalized in {"help", "/help", "?"}:
            print_help()
            continue

        if normalized in {"/trace on", "/trace off"}:
            if trace_sink is None or not trace_sink.available:
                print("\n[AVISO] Telemetria ao vivo indisponível neste runtime.\n")
            else:
                trace_sink.enabled = normalized == "/trace on"
                state_text = "ativada" if trace_sink.enabled else "desativada"
                print(f"\n[OK] Telemetria ao vivo {state_text}.\n")
            continue
        if normalized == "/trace":
            print("\n[USAGE] /trace on or /trace off\n")
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
            if new_role == "CLIENT":
                state.ops_authorized = False
                state.protocol_number = None
            print(f"\n[OK] Papel alterado para {new_role}.\n")
            continue

        dispatch_message(client, token, state, user_input)


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_env_file()
    token = os.environ.setdefault("AGENT_API_SERVICE_TOKEN", "agent-api-internal-test-token")

    parser = argparse.ArgumentParser(
        description="Getnet Support — Primary Manual Terminal Agent Test Entry Point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--url",
        type=str,
        default=os.environ.get("AGENT_API_BASE_URL"),
        help="URL of an already-running Agent API; defaults to AGENT_API_BASE_URL, otherwise runs in-process.",
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
        default=None,
        choices=["CLIENT", "SUPPORT_AGENT"],
        help="Synthetic principal role (local default: SUPPORT_AGENT; remote default: CLIENT).",
    )
    parser.add_argument(
        "--protocol",
        type=str,
        default=None,
        help="Pre-configured synthetic operational protocol number (e.g. POC-OPS-0001).",
    )
    ops_group = parser.add_mutually_exclusive_group()
    ops_group.add_argument(
        "--ops-authorized",
        dest="ops_authorization",
        action="store_const",
        const=True,
        help="Explicitly authorize OPS reads for the local synthetic test principal.",
    )
    ops_group.add_argument(
        "--no-ops-authorized",
        dest="ops_authorization",
        action="store_const",
        const=False,
        help="Explicitly deny OPS reads for the synthetic test principal.",
    )
    parser.set_defaults(ops_authorization=None)
    parser.add_argument(
        "--no-trace",
        action="store_true",
        help="Disable live runtime telemetry (enabled by default for the in-process CLI).",
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

    role = args.role or ("CLIENT" if args.url else "SUPPORT_AGENT")
    if role == "CLIENT" and args.protocol:
        parser.error("--protocol requires SUPPORT_AGENT; a selector cannot grant OPS authorization")
    if role == "CLIENT" and args.ops_authorization is True:
        parser.error("CLIENT cannot be combined with --ops-authorized")
    ops_authorized = args.ops_authorization
    if ops_authorized is None:
        ops_authorized = bool(args.protocol) or (role == "SUPPORT_AGENT" and args.url is None)

    state = CLISessionState(
        user_id=args.user_id,
        role=role,
        ops_authorized=ops_authorized,
        protocol_number=args.protocol,
        operation=args.operation if args.protocol else None,
    )

    trace_sink = ConsoleTraceSink(enabled=not args.no_trace, available=args.url is None)
    if args.url is None:
        ops_state = "OPS READ AUTHORIZED" if state.ops_authorized else "OPS READ UNAUTHORIZED"
        print(f"[DEV TEST PRINCIPAL] {state.role} / {ops_state}")
    client = create_chat_client(args.url, telemetry_sink=trace_sink)
    if args.url and not args.no_trace:
        print("[NOTICE] --url remote runtime does not stream telemetry; no execution stages will be inferred.")
    try:
        if args.message:
            dispatch_message(client, token, state, args.message)
        else:
            interactive_loop(client, token, state, trace_sink=trace_sink)
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
