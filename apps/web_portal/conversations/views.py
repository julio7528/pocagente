"""Authenticated CLIENT presentation over the portal conversation services."""

from __future__ import annotations

import uuid

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.web_portal.accounts.models import User
from apps.web_portal.accounts.views import role_required
from apps.web_portal.conversations.forms import ClientMessageForm
from apps.web_portal.conversations.human_support_intent import requests_human_support
from apps.web_portal.conversations.models import Conversation, Message
from apps.web_portal.conversations.services import (
    ConversationNotWritableError,
    IdempotencyConflictError,
    mark_client_turn_failed,
    append_client_message,
    create_conversation_once,
    get_agent_response_for_turn,
    get_conversation_history,
    get_owned_conversation,
    list_owned_conversations,
)
from apps.web_portal.conversations.agent_turns import execute_agent_turn
from apps.web_portal.integrations.agent_chat import AgentChatUnavailable
from apps.web_portal.integrations.human_escalation import HumanTransitionUnavailable
from apps.web_portal.support.services import (
    SupportConversationUnavailable,
    SupportOperationConflict,
    request_human_support,
)


STATE_PRESENTATION = {
    Conversation.Status.ACTIVE: ("Ativa", "Esta conversa está aberta para mensagens."),
    Conversation.Status.WAITING_HUMAN: (
        "Aguardando atendimento humano",
        "Sua mensagem será registrada nesta conversa enquanto você aguarda atendimento.",
    ),
    Conversation.Status.HUMAN: (
        "Atendimento humano",
        "Continue nesta conversa com o atendimento humano.",
    ),
    Conversation.Status.CLOSED: ("Finalizada", "Esta conversa foi finalizada."),
    Conversation.Status.BLOCKED: (
        "Bloqueada",
        "Esta conversa está bloqueada para novas mensagens.",
    ),
}

_RETRY_SESSION_KEY = "recoverable_agent_chat_turns"


def _update_retry_session(request: HttpRequest, message_id: uuid.UUID, *, allowed: bool) -> None:
    identifiers = list(request.session.get(_RETRY_SESSION_KEY, ()))
    value = str(message_id)
    identifiers = [item for item in identifiers if item != value]
    if allowed:
        identifiers.append(value)
        identifiers = identifiers[-20:]
    request.session[_RETRY_SESSION_KEY] = identifiers


def _attempt_agent_turn(
    request: HttpRequest, conversation: Conversation, client_message, *, retry: bool = False
) -> None:
    try:
        result = execute_agent_turn(
            actor=request.user,
            conversation_id=conversation.pk,
            client_message_id=client_message.pk,
            retry=retry,
        )
    except AgentChatUnavailable as error:
        try:
            mark_client_turn_failed(
                conversation=conversation, client_message=client_message
            )
        except DatabaseError:
            pass
        _update_retry_session(request, client_message.pk, allowed=error.retryable)
        messages.warning(
            request,
            (
                "Não foi possível obter a resposta agora. Sua mensagem foi preservada; tente novamente."
                if error.retryable
                else "Não foi possível concluir a resposta agora. Sua mensagem foi preservada."
            ),
        )
        return
    except DatabaseError:
        return

    if result.outcome == "COMPLETED":
        _update_retry_session(request, client_message.pk, allowed=False)
        if (
            result.response is not None
            and result.response.requires_human
            and result.response.human is not None
            and result.response.human.state == "WAITING_CONFIRMATION"
        ):
            messages.info(
                request,
                "O assistente ofereceu atendimento humano. Confirme pela opção da conversa se desejar."
            )
    elif result.outcome == "ALREADY_COMPLETED":
        _update_retry_session(request, client_message.pk, allowed=False)
    elif result.outcome == "NO_ANSWER":
        _update_retry_session(request, client_message.pk, allowed=False)
        if (
            result.response is not None
            and result.response.requires_human
            and result.response.human is not None
            and result.response.human.state == "WAITING_CONFIRMATION"
        ):
            messages.info(
                request,
                "O atendimento humano está disponível para confirmação. Sua conversa permanece ativa.",
            )
        else:
            messages.info(request, "Sua mensagem foi preservada, mas não há uma resposta disponível para exibição.")
    else:
        _update_retry_session(request, client_message.pk, allowed=False)


def _route_client_turn(
    request: HttpRequest,
    conversation: Conversation,
    client_message: Message,
    *,
    retry: bool = False,
) -> None:
    """Send an explicit human request to the handoff flow, otherwise use automation."""

    if not requests_human_support(client_message.body):
        _attempt_agent_turn(request, conversation, client_message, retry=retry)
        return

    _update_retry_session(request, client_message.pk, allowed=False)
    try:
        request_human_support(
            actor=request.user,
            conversation_id=conversation.pk,
            explicit_confirmation=True,
        )
    except (SupportConversationUnavailable, PermissionDenied):
        messages.warning(
            request,
            "Não foi possível localizar esta conversa para solicitar atendimento humano.",
        )
    except (SupportOperationConflict, ConversationNotWritableError):
        messages.info(
            request,
            "Esta conversa não pode iniciar um novo atendimento humano.",
        )
    except HumanTransitionUnavailable:
        messages.warning(
            request,
            "O atendimento humano está temporariamente indisponível. Sua mensagem foi preservada.",
        )
    except DatabaseError:
        messages.warning(
            request,
            "Não foi possível solicitar atendimento humano agora. Sua mensagem foi preservada.",
        )
    else:
        messages.success(
            request,
            "Solicitação enviada. Você pode continuar nesta conversa enquanto aguarda.",
        )


def _message_form() -> ClientMessageForm:
    return ClientMessageForm(initial={"client_turn_key": uuid.uuid4()})


def _unavailable(request: HttpRequest) -> HttpResponse:
    return render(request, "conversations/unavailable.html", status=503)


def _render_chat(
    request: HttpRequest,
    *,
    conversation: Conversation | None = None,
    form: ClientMessageForm | None = None,
    status: int = 200,
) -> HttpResponse:
    try:
        sidebar = list(list_owned_conversations(owner=request.user))
        history = (
            list(get_conversation_history(owner=request.user, conversation_id=conversation.id))
            if conversation is not None else []
        )
        recoverable_ids = set(request.session.get(_RETRY_SESSION_KEY, ()))
        retry_candidates = [
            item for item in history
            if item.sender_type == Message.SenderType.CLIENT
            and item.processing_status == Message.ProcessingStatus.FAILED
            and str(item.pk) in recoverable_ids
        ]
        response_ids = {
            uuid.uuid5(item.pk, "portal-agent-response") for item in retry_candidates
        }
        existing_response_ids = set(
            Message.objects.filter(pk__in=response_ids).values_list("pk", flat=True)
        ) if response_ids else set()
        for item in history:
            item.agent_retry_available = (
                conversation is not None
                and conversation.status == Conversation.Status.ACTIVE
                and item in retry_candidates
                and uuid.uuid5(item.pk, "portal-agent-response") not in existing_response_ids
            )
    except DatabaseError:
        return _unavailable(request)
    writable = conversation is None or conversation.status in {
        Conversation.Status.ACTIVE,
        Conversation.Status.WAITING_HUMAN,
        Conversation.Status.HUMAN,
    }
    label, description = STATE_PRESENTATION.get(conversation.status, ("", "")) if conversation else ("", "")
    live_version = (
        f"{conversation.status}:{conversation.updated_at.isoformat()}:{history[-1].pk if history else ''}"
        if conversation is not None else ""
    )
    return render(
        request,
        "conversations/chat.html",
        {
            "sidebar_conversations": sidebar,
            "conversation": conversation,
            "history": history,
            "form": form or _message_form(),
            "writable": writable,
            "state_label": label,
            "state_description": description,
            "live_version": live_version,
        },
        status=status,
    )


@role_required(User.Role.CLIENT)
@require_GET
def chat_home(request: HttpRequest) -> HttpResponse:
    return _render_chat(request)


@role_required(User.Role.CLIENT)
@require_POST
def new_conversation(request: HttpRequest) -> HttpResponse:
    form = ClientMessageForm(request.POST)
    if not form.is_valid():
        return _render_chat(request, form=form, status=400)
    try:
        created = create_conversation_once(
            owner=request.user,
            first_message=form.cleaned_data["body"],
            client_turn_key=form.cleaned_data["client_turn_key"],
        )
    except IdempotencyConflictError:
        form.add_error(None, "Esta tentativa de envio já foi utilizada. Atualize a página e tente novamente.")
        return _render_chat(request, form=form, status=409)
    except ValidationError:
        form.add_error("body", "Revise a mensagem e tente novamente.")
        return _render_chat(request, form=form, status=400)
    except DatabaseError:
        return _unavailable(request)
    messages.success(request, "Mensagem registrada.")
    if created.created and created.conversation.status == Conversation.Status.ACTIVE:
        _route_client_turn(request, created.conversation, created.first_message)
    return redirect("chat-detail", conversation_id=created.conversation.id)


@role_required(User.Role.CLIENT)
@require_GET
def conversation_detail(request: HttpRequest, conversation_id: uuid.UUID) -> HttpResponse:
    try:
        conversation = get_owned_conversation(
            owner=request.user, conversation_id=conversation_id
        )
    except DatabaseError:
        return _unavailable(request)
    return _render_chat(request, conversation=conversation)


@role_required(User.Role.CLIENT)
@require_GET
def conversation_updates(request: HttpRequest, conversation_id: uuid.UUID) -> JsonResponse:
    try:
        conversation = get_owned_conversation(
            owner=request.user, conversation_id=conversation_id
        )
        latest_id = (
            conversation.messages.order_by("-created_at", "-id")
            .values_list("id", flat=True)
            .first()
        )
    except PermissionDenied:
        return JsonResponse({"error": "not_found"}, status=404)
    except DatabaseError:
        return JsonResponse({"error": "unavailable"}, status=503)
    return JsonResponse({"version": f"{conversation.status}:{conversation.updated_at.isoformat()}:{latest_id or ''}"})


@role_required(User.Role.CLIENT)
@require_POST
def append_message(request: HttpRequest, conversation_id: uuid.UUID) -> HttpResponse:
    try:
        conversation = get_owned_conversation(
            owner=request.user, conversation_id=conversation_id
        )
    except DatabaseError:
        return _unavailable(request)
    if conversation.status not in {
        Conversation.Status.ACTIVE,
        Conversation.Status.WAITING_HUMAN,
        Conversation.Status.HUMAN,
    }:
        return _render_chat(request, conversation=conversation, status=409)
    form = ClientMessageForm(request.POST)
    if not form.is_valid():
        return _render_chat(request, conversation=conversation, form=form, status=400)
    try:
        persisted = append_client_message(
            actor=request.user,
            conversation=conversation,
            body=form.cleaned_data["body"],
            client_turn_key=form.cleaned_data["client_turn_key"],
        )
    except ConversationNotWritableError:
        conversation.refresh_from_db()
        return _render_chat(request, conversation=conversation, status=409)
    except IdempotencyConflictError:
        form.add_error(None, "Esta tentativa de envio já foi utilizada. Atualize a página e tente novamente.")
        return _render_chat(request, conversation=conversation, form=form, status=409)
    except ValidationError:
        form.add_error("body", "Revise a mensagem e tente novamente.")
        return _render_chat(request, conversation=conversation, form=form, status=400)
    except DatabaseError:
        return _unavailable(request)
    messages.success(request, "Mensagem registrada.")
    if persisted.created and conversation.status == Conversation.Status.ACTIVE:
        _route_client_turn(request, conversation, persisted.message)
    return redirect("chat-detail", conversation_id=conversation.id)


@role_required(User.Role.CLIENT)
@require_POST
def retry_agent_message(
    request: HttpRequest, conversation_id: uuid.UUID, message_id: uuid.UUID
) -> HttpResponse:
    try:
        conversation = get_owned_conversation(
            owner=request.user, conversation_id=conversation_id
        )
        client_message = Message.objects.get(
            pk=message_id,
            conversation=conversation,
            sender_type=Message.SenderType.CLIENT,
            sender_user=request.user,
        )
    except (PermissionDenied, Message.DoesNotExist):
        return render(request, "conversations/unavailable.html", status=404)
    except DatabaseError:
        return _unavailable(request)

    retryable_ids = set(request.session.get(_RETRY_SESSION_KEY, ()))
    existing = get_agent_response_for_turn(
        conversation=conversation, client_message=client_message
    )
    if existing is not None:
        _update_retry_session(request, client_message.pk, allowed=False)
        return redirect("chat-detail", conversation_id=conversation.pk)
    if str(client_message.pk) not in retryable_ids:
        messages.info(request, "Esta tentativa não está disponível para reenvio.")
        return redirect("chat-detail", conversation_id=conversation.pk)
    if conversation.status != Conversation.Status.ACTIVE:
        _update_retry_session(request, client_message.pk, allowed=False)
        messages.info(request, "Esta conversa não está disponível para uma nova resposta automática.")
        return redirect("chat-detail", conversation_id=conversation.pk)

    _route_client_turn(request, conversation, client_message, retry=True)
    return redirect("chat-detail", conversation_id=conversation.pk)
