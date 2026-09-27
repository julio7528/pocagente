"""One-use, session-bound presentation of the current CLIENT debug turn."""

from __future__ import annotations

import json
import re
import uuid
from typing import Iterable

from django.conf import settings
from django.http import HttpRequest

from apps.agent_api.app.telemetry import (
    CollectorTelemetrySink,
    RuntimeEventKind,
    RuntimeTelemetryEvent,
)
from apps.agent_api.app.telemetry_presentation import present_runtime_event
from apps.web_portal.integrations.agent_chat import AgentChatResponse


_SESSION_KEY = "client_debugger_current_turn"
_MAX_SESSION_BYTES = 48_000
_MAX_EVENTS = CollectorTelemetrySink.MAX_EVENTS
_STATES = {"complete", "error", "no_runtime"}
_SAFE_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")


def debugger_requested(request: HttpRequest) -> bool:
    return bool(
        settings.PORTAL_DEBUGGER_ENABLED
        and request.POST.get("debugger_mode") == "on"
    )


def clear_debug_turn(request: HttpRequest) -> None:
    if not settings.PORTAL_DEBUGGER_ENABLED:
        return
    try:
        request.session.pop(_SESSION_KEY, None)
    except Exception:
        pass


def _code(value: object) -> str | None:
    return value if isinstance(value, str) and _SAFE_CODE.fullmatch(value) else None


def remember_debug_turn(
    request: HttpRequest,
    *,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    state: str,
    trace: Iterable[RuntimeTelemetryEvent] = (),
    response: AgentChatResponse | None = None,
    trace_truncated: bool = False,
) -> None:
    """Keep only the next render's bounded, approved event data."""

    if not settings.PORTAL_DEBUGGER_ENABLED:
        return
    try:
        events = [
            event.model_dump(mode="json", exclude_none=True)
            for event in trace
            if isinstance(event, RuntimeTelemetryEvent)
        ]
        truncated = trace_truncated or len(events) > _MAX_EVENTS
        events = events[:_MAX_EVENTS]
        intent = next(
            (
                event.get("value") for event in reversed(events)
                if event.get("kind") == RuntimeEventKind.INTENT.value
            ),
            None,
        )
        record = {
            "owner_id": str(request.user.pk),
            "conversation_id": str(conversation_id),
            "message_id": str(message_id),
            "state": state if state in _STATES else "error",
            "trace": events,
            "trace_truncated": truncated,
            "route": _code(response.route) if response else None,
            "status": _code(response.status) if response else None,
            "intent": _code(intent),
        }
        while events and len(json.dumps(record, separators=(",", ":"))) > _MAX_SESSION_BYTES:
            events.pop()
            record["trace_truncated"] = True
        request.session[_SESSION_KEY] = record
    except Exception:
        # Debug state cannot interfere with message persistence or the reply.
        return


def consume_debug_turn(
    request: HttpRequest, *, conversation_id: uuid.UUID | None,
    message_ids: set[str],
) -> dict | None:
    """Read once after PRG, bound to the same owner, conversation, and turn."""

    try:
        record = request.session.pop(_SESSION_KEY, None)
        if (
            not settings.PORTAL_DEBUGGER_ENABLED
            or not isinstance(record, dict)
            or conversation_id is None
            or record.get("owner_id") != str(request.user.pk)
            or record.get("conversation_id") != str(conversation_id)
            or record.get("message_id") not in message_ids
        ):
            return None
        events = []
        for raw in record.get("trace", ())[:_MAX_EVENTS]:
            try:
                event = RuntimeTelemetryEvent.model_validate_json(json.dumps(raw))
                presented = present_runtime_event(event)
                events.append({
                    "label": presented.label,
                    "detail": presented.detail,
                    "elapsed_ms": presented.elapsed_ms,
                })
            except Exception:
                continue
        return {
            "state": record.get("state") if record.get("state") in _STATES else "error",
            "trace": events,
            "trace_truncated": record.get("trace_truncated") is True,
            "route": _code(record.get("route")),
            "status": _code(record.get("status")),
            "intent": _code(record.get("intent")),
        }
    except Exception:
        return None
