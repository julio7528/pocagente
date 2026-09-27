"""Safe, shared presentation of validated runtime telemetry events."""

from __future__ import annotations

from dataclasses import dataclass

from apps.agent_api.app.telemetry import RuntimeEventKind, RuntimeTelemetryEvent


@dataclass(frozen=True)
class PresentedRuntimeEvent:
    label: str
    detail: str
    elapsed_ms: int | None


_LLM_LABELS = {
    "conversational_response": "LLM resposta",
    "ops_synthesis_retry": "LLM sintese (nova tentativa)",
    "ops_planning": "LLM planejamento OPS",
    "ops_synthesis": "LLM síntese",
    "cooperative_synthesis": "Síntese cooperativa",
    "grounded_generation": "LLM grounded generation",
}


def present_runtime_event(event: RuntimeTelemetryEvent) -> PresentedRuntimeEvent:
    """Translate only approved event fields for CLI and portal display."""

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
        label = _LLM_LABELS.get(event.name or "", "LLM")
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
    return PresentedRuntimeEvent(label=label, detail=detail, elapsed_ms=event.elapsed_ms)
