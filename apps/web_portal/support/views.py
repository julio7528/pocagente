"""Authenticated browser presentation for the HUMAN support workflow."""

from __future__ import annotations

import hashlib
import json
import uuid

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.web_portal.accounts.models import User
from apps.web_portal.accounts.views import role_required
from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.conversations.services import (
    ConversationNotWritableError,
    IdempotencyConflictError,
    get_owned_conversation,
)
from apps.web_portal.integrations.human_escalation import HumanTransitionUnavailable
from apps.web_portal.support.forms import FinalizeHandoffForm, SupportMessageForm
from apps.web_portal.support.services import (
    SupportConversationUnavailable,
    SupportOperationConflict,
    append_assigned_support_message,
    assigned_handoffs,
    claim_handoff,
    conversation_message_version,
    finalize_handoff,
    finalized_handoffs,
    get_support_conversation,
    request_human_support,
    waiting_handoffs,
)


STATUS_LABELS = {
    Conversation.Status.WAITING_HUMAN: "Aguardando atendimento",
    Conversation.Status.HUMAN: "Em atendimento",
    Conversation.Status.CLOSED: "Finalizado",
}


def _unavailable(request: HttpRequest) -> HttpResponse:
    return render(request, "support/unavailable.html", status=503)


def _not_found() -> HttpResponse:
    raise Http404("This conversation is not available.")


def _queue_data(actor: User) -> dict:
    waiting = list(waiting_handoffs(actor=actor))
    active = list(assigned_handoffs(actor=actor))
    finalized = list(finalized_handoffs(actor=actor))
    records = [
        (item.pk, item.status, item.requested_at, item.accepted_at, item.resolved_at, item.conversation.updated_at)
        for item in (*waiting, *active, *finalized)
    ]
    serialized = json.dumps(
        [(str(pk), status, *(value.isoformat() if value else None for value in dates))
         for pk, status, *dates in records],
        separators=(",", ":"),
    )
    return {
        "waiting_handoffs": waiting,
        "active_handoffs": active,
        "finalized_handoffs": finalized,
        "open_count": len(waiting) + len(active),
        "finalized_count": len(finalized),
        "queue_version": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
    }


def _thread_context(actor: User, conversation: Conversation, *, message_form=None) -> dict:
    return {
        "conversation": conversation,
        "history": list(Message.objects.filter(conversation=conversation).order_by("created_at", "id")),
        "handoff": conversation.support_handoff,
        "state_label": STATUS_LABELS.get(conversation.status, "Atendimento"),
        "can_claim": conversation.status == Conversation.Status.WAITING_HUMAN,
        "can_reply": conversation.status == Conversation.Status.HUMAN,
        "message_form": message_form or SupportMessageForm(initial={"support_turn_key": uuid.uuid4()}),
        "finalize_form": FinalizeHandoffForm(),
        "live_version": conversation_message_version(conversation),
        "status_note": (
            "Aguardando um atendente assumir." if conversation.status == Conversation.Status.WAITING_HUMAN
            else "Este atendimento está finalizado e disponível somente para leitura."
            if conversation.status == Conversation.Status.CLOSED
            else "Atendimento humano em andamento."
        ),
    }


@role_required(User.Role.SUPPORT_AGENT)
@require_GET
def support_dashboard(request: HttpRequest) -> HttpResponse:
    try:
        return render(request, "support/dashboard.html", _queue_data(request.user))
    except DatabaseError:
        return _unavailable(request)


@role_required(User.Role.SUPPORT_AGENT)
@require_GET
def support_dashboard_updates(request: HttpRequest) -> JsonResponse:
    try:
        data = _queue_data(request.user)
    except DatabaseError:
        return JsonResponse({"error": "unavailable"}, status=503)
    return JsonResponse({"version": data["queue_version"]})


@role_required(User.Role.SUPPORT_AGENT)
@require_GET
def support_conversation(request: HttpRequest, conversation_id: uuid.UUID) -> HttpResponse:
    try:
        conversation = get_support_conversation(actor=request.user, conversation_id=conversation_id)
    except SupportConversationUnavailable:
        return _not_found()
    except DatabaseError:
        return _unavailable(request)
    try:
        context = _thread_context(request.user, conversation)
    except DatabaseError:
        return _unavailable(request)
    return render(request, "support/conversation.html", context)


@role_required(User.Role.SUPPORT_AGENT)
@require_GET
def support_conversation_updates(request: HttpRequest, conversation_id: uuid.UUID) -> JsonResponse:
    try:
        conversation = get_support_conversation(actor=request.user, conversation_id=conversation_id)
    except SupportConversationUnavailable:
        return JsonResponse({"error": "not_found"}, status=404)
    except DatabaseError:
        return JsonResponse({"error": "unavailable"}, status=503)
    return JsonResponse({"version": conversation_message_version(conversation)})


@role_required(User.Role.SUPPORT_AGENT)
@require_POST
def claim_support_conversation(request: HttpRequest, conversation_id: uuid.UUID) -> HttpResponse:
    try:
        claim_handoff(actor=request.user, conversation_id=conversation_id)
    except SupportConversationUnavailable:
        return _not_found()
    except SupportOperationConflict:
        messages.warning(request, "Este atendimento já foi assumido por outro atendente.")
        try:
            return render(request, "support/dashboard.html", _queue_data(request.user), status=409)
        except DatabaseError:
            return _unavailable(request)
    except HumanTransitionUnavailable:
        return _unavailable(request)
    except DatabaseError:
        return _unavailable(request)
    else:
        messages.success(request, "Atendimento assumido.")
    return redirect("support-conversation", conversation_id=conversation_id)


@role_required(User.Role.SUPPORT_AGENT)
@require_POST
def support_message(request: HttpRequest, conversation_id: uuid.UUID) -> HttpResponse:
    form = SupportMessageForm(request.POST)
    try:
        conversation = get_support_conversation(actor=request.user, conversation_id=conversation_id)
    except SupportConversationUnavailable:
        return _not_found()
    except DatabaseError:
        return _unavailable(request)
    if conversation.status != Conversation.Status.HUMAN:
        messages.warning(request, "Este atendimento não está disponível para novas mensagens.")
        return redirect("support-conversation", conversation_id=conversation_id)
    if not form.is_valid():
        return _render_support_form(request, conversation, form, 400)
    try:
        append_assigned_support_message(
            actor=request.user,
            conversation_id=conversation_id,
            body=form.cleaned_data["body"],
            support_turn_key=form.cleaned_data["support_turn_key"],
        )
    except SupportConversationUnavailable:
        return _not_found()
    except (IdempotencyConflictError, ConversationNotWritableError):
        messages.warning(request, "A mensagem não pôde ser registrada. Atualize o atendimento e tente novamente.")
        return redirect("support-conversation", conversation_id=conversation_id)
    except ValidationError:
        form.add_error("body", "Revise a mensagem e tente novamente.")
        return _render_support_form(request, conversation, form, 400)
    except DatabaseError:
        return _unavailable(request)
    messages.success(request, "Mensagem enviada.")
    return redirect("support-conversation", conversation_id=conversation_id)


def _render_support_form(request, conversation, form, status):
    try:
        current = get_support_conversation(actor=request.user, conversation_id=conversation.id)
        context = _thread_context(request.user, current, message_form=form)
    except (SupportConversationUnavailable, PermissionDenied):
        return _not_found()
    except DatabaseError:
        return render(request, "support/unavailable.html", status=503)
    return render(request, "support/conversation.html", context, status=status)


@role_required(User.Role.SUPPORT_AGENT)
@require_POST
def close_support_conversation(request: HttpRequest, conversation_id: uuid.UUID) -> HttpResponse:
    try:
        get_support_conversation(actor=request.user, conversation_id=conversation_id)
    except SupportConversationUnavailable:
        return _not_found()
    except DatabaseError:
        return _unavailable(request)
    form = FinalizeHandoffForm(request.POST)
    if not form.is_valid():
        messages.warning(request, "Confirme que deseja finalizar o atendimento.")
        return redirect("support-conversation", conversation_id=conversation_id)
    try:
        finalize_handoff(actor=request.user, conversation_id=conversation_id)
    except SupportConversationUnavailable:
        return _not_found()
    except SupportOperationConflict:
        messages.warning(request, "Este atendimento não pode mais ser finalizado.")
    except HumanTransitionUnavailable:
        return _unavailable(request)
    except DatabaseError:
        return _unavailable(request)
    else:
        messages.success(request, "Atendimento finalizado.")
    return redirect("support-conversation", conversation_id=conversation_id)


@role_required(User.Role.CLIENT)
@require_GET
def confirm_human_support(request: HttpRequest, conversation_id: uuid.UUID) -> HttpResponse:
    try:
        conversation = get_owned_conversation(owner=request.user, conversation_id=conversation_id)
    except PermissionDenied:
        return _not_found()
    except DatabaseError:
        return _unavailable(request)
    if conversation.status != Conversation.Status.ACTIVE:
        messages.info(request, "Esta conversa não pode iniciar um novo atendimento humano.")
        return redirect("chat-detail", conversation_id=conversation_id)
    return render(request, "support/client_confirm.html", {"conversation": conversation})


@role_required(User.Role.CLIENT)
@require_POST
def request_human_support_view(request: HttpRequest, conversation_id: uuid.UUID) -> HttpResponse:
    try:
        request_human_support(
            actor=request.user,
            conversation_id=conversation_id,
            explicit_confirmation=True,
        )
    except (SupportConversationUnavailable, PermissionDenied):
        return _not_found()
    except (SupportOperationConflict, ConversationNotWritableError):
        messages.info(request, "Esta conversa não pode iniciar um novo atendimento humano.")
    except HumanTransitionUnavailable:
        return _unavailable(request)
    except DatabaseError:
        return _unavailable(request)
    else:
        messages.success(request, "Solicitação enviada. Você pode continuar nesta conversa enquanto aguarda.")
    return redirect("chat-detail", conversation_id=conversation_id)
