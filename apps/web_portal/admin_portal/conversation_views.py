from __future__ import annotations

from uuid import UUID

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.web_portal.accounts.models import User
from apps.web_portal.accounts.views import role_required
from apps.web_portal.admin_portal.conversation_forms import (
    ConversationAdminFiltersForm,
    ConversationConfirmationForm,
)
from apps.web_portal.admin_portal.conversation_services import (
    AdminConversationConflict,
    AdminConversationUnavailable,
    ConversationAdminFilters,
    block_conversation as block_conversation_service,
    get_admin_conversation,
    get_admin_history,
    list_admin_conversations,
    soft_delete_conversation as soft_delete_conversation_service,
    unblock_conversation as unblock_conversation_service,
)
from apps.web_portal.conversations.models import Conversation
from apps.web_portal.support.models import SupportHandoff


PAGE_SIZE = 25
STATUS_LABELS = {
    Conversation.Status.ACTIVE: "Ativa",
    Conversation.Status.WAITING_HUMAN: "Aguardando atendimento",
    Conversation.Status.HUMAN: "Atendimento humano",
    Conversation.Status.CLOSED: "Finalizada",
    Conversation.Status.BLOCKED: "Bloqueada",
    Conversation.Status.DELETED: "Apagada",
}
HANDOFF_STATUS_LABELS = {
    SupportHandoff.Status.WAITING: "Aguardando atendimento",
    SupportHandoff.Status.ASSIGNED: "Em atendimento",
    SupportHandoff.Status.RESOLVED: "Finalizado",
    SupportHandoff.Status.CANCELLED: "Cancelado",
}
SAFE_CONFLICT_MESSAGES = {
    "This conversation is already blocked.": "Esta conversa já está bloqueada.",
    "This conversation is not blocked.": "Esta conversa não está bloqueada.",
    "The saved state cannot be safely restored.": "O estado anterior não pode ser restaurado com segurança.",
    "The conversation lifecycle is inconsistent.": "O estado atual da conversa não permite esta ação.",
    "This conversation cannot be blocked in its current state.": "Esta conversa não pode ser bloqueada no estado atual.",
    "This conversation is already deleted.": "Esta conversa já foi apagada.",
    "A conversa possui um atendimento humano ativo e não pode ser apagada.": "Há um atendimento humano ativo. A conversa não pode ser apagada.",
}


def _not_found(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "admin_portal/conversation_not_found.html",
        {"section": "conversations"},
        status=404,
    )


@role_required(User.Role.ADMIN)
@require_GET
def conversation_list(request: HttpRequest) -> HttpResponse:
    form = ConversationAdminFiltersForm(request.GET if request.GET else None)
    if form.is_bound and not form.is_valid():
        return render(
            request,
            "admin_portal/conversations.html",
            {"form": form, "page_obj": None, "section": "conversations"},
            status=400,
        )
    values = form.cleaned_data if form.is_bound else {}
    filters = ConversationAdminFilters(
        query=values.get("query", ""),
        owner_username=values.get("owner_username", ""),
        status=values.get("status", ""),
        date_from=values.get("date_from"),
        date_to=values.get("date_to"),
    )
    try:
        conversations = list_admin_conversations(actor=request.user, filters=filters)
        page_obj = Paginator(conversations, PAGE_SIZE).get_page(request.GET.get("page", 1))
        page_obj.object_list = list(page_obj.object_list)
        for conversation in page_obj.object_list:
            conversation.admin_status_label = STATUS_LABELS[conversation.status]
            try:
                handoff = conversation.support_handoff
            except SupportHandoff.DoesNotExist:
                handoff = None
            conversation.admin_handoff_label = (
                HANDOFF_STATUS_LABELS.get(handoff.status, "Atendimento")
                if handoff else ""
            )
            conversation.admin_assignee_username = (
                handoff.assigned_support_user.username
                if handoff and handoff.assigned_support_user_id else ""
            )
    except PermissionDenied:
        raise
    except ValidationError:
        form.add_error(None, "Os filtros informados não são válidos.")
        return render(
            request,
            "admin_portal/conversations.html",
            {"form": form, "page_obj": None, "section": "conversations"},
            status=400,
        )
    except DatabaseError:
        messages.error(request, "Não foi possível carregar as conversas. Tente novamente.")
        return render(
            request,
            "admin_portal/conversations.html",
            {"form": form, "page_obj": None, "section": "conversations"},
            status=503,
        )
    query_params = QueryDict(mutable=True)
    for key, value in values.items():
        if value not in (None, ""):
            query_params[key] = value.isoformat() if hasattr(value, "isoformat") else value
    return render(
        request,
        "admin_portal/conversations.html",
        {
            "form": form,
            "page_obj": page_obj,
            "conversations": page_obj.object_list,
            "page_query": query_params.urlencode(),
            "section": "conversations",
        },
    )


@role_required(User.Role.ADMIN)
@require_GET
def conversation_detail(request: HttpRequest, conversation_id: UUID) -> HttpResponse:
    try:
        conversation = get_admin_conversation(
            actor=request.user, conversation_id=conversation_id
        )
        history = list(get_admin_history(actor=request.user, conversation=conversation))
    except PermissionDenied:
        raise
    except AdminConversationUnavailable:
        return _not_found(request)
    except DatabaseError:
        messages.error(request, "Não foi possível carregar o histórico. Tente novamente.")
        return redirect("admin-conversations")

    try:
        handoff = conversation.support_handoff
    except SupportHandoff.DoesNotExist:
        handoff = None
    active_handoff = bool(
        handoff and handoff.status in (SupportHandoff.Status.WAITING, SupportHandoff.Status.ASSIGNED)
    )
    return render(
        request,
        "admin_portal/conversation_detail.html",
        {
            "conversation": conversation,
            "history": history,
            "handoff": handoff,
            "section": "conversations",
            "status_label": STATUS_LABELS.get(conversation.status, "Indisponível"),
            "handoff_status_label": (
                HANDOFF_STATUS_LABELS.get(handoff.status, "Atendimento")
                if handoff else ""
            ),
            "status_before_label": STATUS_LABELS.get(conversation.status_before_block, "Indisponível"),
            "can_block": conversation.status in (
                Conversation.Status.ACTIVE,
                Conversation.Status.WAITING_HUMAN,
                Conversation.Status.HUMAN,
            ),
            "can_unblock": conversation.status == Conversation.Status.BLOCKED,
            "can_delete": conversation.status != Conversation.Status.DELETED and not active_handoff,
            "delete_restricted": conversation.status != Conversation.Status.DELETED and active_handoff,
        },
    )


def _mutation_result(
    request: HttpRequest,
    conversation_id: UUID,
    operation,
    *,
    success: str,
) -> HttpResponse:
    confirmation = ConversationConfirmationForm(request.POST)
    if not confirmation.is_valid():
        messages.error(request, "Confirme a ação para continuar.")
        return redirect("admin-conversation-detail", conversation_id=conversation_id)
    try:
        operation(actor=request.user, conversation_id=conversation_id)
    except PermissionDenied:
        raise
    except AdminConversationUnavailable:
        messages.error(request, "A conversa não está disponível.")
        return redirect("admin-conversations")
    except AdminConversationConflict as exc:
        safe_message = SAFE_CONFLICT_MESSAGES.get(
            str(exc), "A alteração não pode ser aplicada ao estado atual da conversa."
        )
        messages.error(request, safe_message)
    except DatabaseError:
        messages.error(request, "Não foi possível atualizar a conversa. Tente novamente.")
        return redirect("admin-conversation-detail", conversation_id=conversation_id)
    else:
        messages.success(request, success)
    return redirect("admin-conversation-detail", conversation_id=conversation_id)


@role_required(User.Role.ADMIN)
@require_POST
def conversation_block(request: HttpRequest, conversation_id: UUID) -> HttpResponse:
    return _mutation_result(
        request,
        conversation_id,
        block_conversation_service,
        success="Conversa bloqueada. O histórico foi preservado.",
    )


@role_required(User.Role.ADMIN)
@require_POST
def conversation_unblock(request: HttpRequest, conversation_id: UUID) -> HttpResponse:
    return _mutation_result(
        request,
        conversation_id,
        unblock_conversation_service,
        success="Conversa restaurada ao estado anterior.",
    )


@role_required(User.Role.ADMIN)
@require_POST
def conversation_soft_delete(request: HttpRequest, conversation_id: UUID) -> HttpResponse:
    return _mutation_result(
        request,
        conversation_id,
        soft_delete_conversation_service,
        success="Conversa apagada da visualização normal; o histórico foi mantido.",
    )
