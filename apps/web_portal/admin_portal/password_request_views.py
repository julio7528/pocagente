"""ADMIN views for the administrator-managed password-reset workflow."""

from __future__ import annotations

from uuid import UUID

from django.contrib import messages
from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.web_portal.accounts.models import User
from apps.web_portal.accounts.password_reset_services import (
    PasswordResetRequestConflict,
    PasswordResetRequestFilters,
    PasswordResetRequestUnavailable,
    get_password_reset_request,
    list_password_reset_requests,
    reject_password_reset_request,
    resolve_password_reset_request,
)
from apps.web_portal.accounts.views import role_required
from apps.web_portal.admin_portal.password_request_forms import (
    PasswordResetRejectForm,
    PasswordResetRequestFilterForm,
    PasswordResetResolveForm,
)


PAGE_SIZE = 25


def _not_found(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "admin_portal/password_request_not_found.html",
        {"section": "password-requests"},
        status=404,
    )


def _detail_response(
    request: HttpRequest,
    request_id: UUID,
    *,
    status: int = 200,
    resolve_form: PasswordResetResolveForm | None = None,
) -> HttpResponse:
    item = get_password_reset_request(actor=request.user, request_id=request_id)
    return render(
        request,
        "admin_portal/password_request_detail.html",
        {
            "section": "password-requests",
            "reset_request": item,
            "resolve_form": resolve_form or PasswordResetResolveForm(),
            "reject_form": PasswordResetRejectForm(),
        },
        status=status,
    )


@role_required(User.Role.ADMIN)
@require_GET
def password_request_list(request: HttpRequest) -> HttpResponse:
    data = request.GET.copy()
    if "status" not in data:
        data["status"] = "OPEN"
    form = PasswordResetRequestFilterForm(data)
    if not form.is_valid():
        return render(
            request,
            "admin_portal/password_requests.html",
            {
                "section": "password-requests",
                "form": form,
                "page_obj": None,
                "selected_status": "",
                "search_query": "",
            },
            status=400,
        )

    values = form.cleaned_data
    filters = PasswordResetRequestFilters(
        status=values["status"],
        query=values["query"],
    )
    try:
        queryset = list_password_reset_requests(actor=request.user, filters=filters)
        page_obj = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page", 1))
        page_obj.object_list = list(page_obj.object_list)
    except PermissionDenied:
        raise
    except (ValidationError, ValueError):
        form.add_error(None, "Os filtros informados não são válidos.")
        return render(
            request,
            "admin_portal/password_requests.html",
            {
                "section": "password-requests",
                "form": form,
                "page_obj": None,
                "selected_status": values["status"],
                "search_query": values["query"],
            },
            status=400,
        )
    except DatabaseError:
        return render(
            request,
            "admin_portal/password_requests.html",
            {
                "section": "password-requests",
                "form": form,
                "page_obj": None,
                "selected_status": values["status"],
                "search_query": values["query"],
                "error_message": "Não foi possível carregar as solicitações. Tente novamente.",
            },
            status=503,
        )

    return render(
        request,
        "admin_portal/password_requests.html",
        {
            "section": "password-requests",
            "form": form,
            "page_obj": page_obj,
            "selected_status": values["status"],
            "search_query": values["query"],
        },
    )


@role_required(User.Role.ADMIN)
@require_GET
def password_request_detail(request: HttpRequest, request_id: UUID) -> HttpResponse:
    try:
        return _detail_response(request, request_id)
    except PermissionDenied:
        raise
    except PasswordResetRequestUnavailable:
        return _not_found(request)
    except DatabaseError:
        messages.error(request, "Não foi possível carregar a solicitação. Tente novamente.")
        return redirect("admin-password-requests")


@role_required(User.Role.ADMIN)
@require_POST
def password_request_resolve(request: HttpRequest, request_id: UUID) -> HttpResponse:
    form = PasswordResetResolveForm(request.POST)
    if not form.is_valid():
        # Bind only an empty mapping so Django initializes cleaned_data and
        # required-field errors without retaining either submitted password.
        safe_form = PasswordResetResolveForm(data={})
        for field_name, errors in form.errors.as_data().items():
            if field_name in safe_form.fields:
                for error in errors:
                    # Form error messages contain validation guidance, never
                    # submitted password values. PasswordInput stays unbound.
                    safe_form.add_error(field_name, error)
        try:
            return _detail_response(
                request,
                request_id,
                status=400,
                # Never bind submitted secret fields into a response template.
                resolve_form=safe_form,
            )
        except PasswordResetRequestUnavailable:
            return _not_found(request)
        except DatabaseError:
            messages.error(request, "Não foi possível carregar a solicitação. Tente novamente.")
            return redirect("admin-password-requests")

    try:
        result = resolve_password_reset_request(
            actor=request.user,
            request_id=request_id,
            new_password=form.cleaned_data["new_password"],
        )
    except PermissionDenied:
        raise
    except PasswordResetRequestUnavailable:
        return _not_found(request)
    except PasswordResetRequestConflict:
        messages.error(request, "Esta solicitação já foi concluída e não pode ser alterada.")
        return redirect("admin-password-request-detail", request_id=request_id)
    except ValidationError:
        # Password validators are intentionally summarized; never reflect the
        # submitted value or any validator-specific user attributes.
        messages.error(request, "A senha não atende à política configurada. Revise os critérios e tente novamente.")
        return redirect("admin-password-request-detail", request_id=request_id)
    except DatabaseError:
        messages.error(request, "Não foi possível redefinir a senha. Tente novamente.")
        return redirect("admin-password-request-detail", request_id=request_id)

    if result.acting_admin_was_requester:
        # The account service revoked the saved session. Flush this request too;
        # do not put a success message in the session being invalidated.
        logout(request)
        return redirect("login")
    messages.success(
        request,
        "Senha redefinida. Oriente o usuário pelo canal interno aprovado.",
    )
    return redirect("admin-password-request-detail", request_id=request_id)


@role_required(User.Role.ADMIN)
@require_POST
def password_request_reject(request: HttpRequest, request_id: UUID) -> HttpResponse:
    form = PasswordResetRejectForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Confirme a rejeição para continuar.")
        return redirect("admin-password-request-detail", request_id=request_id)
    try:
        reject_password_reset_request(actor=request.user, request_id=request_id)
    except PermissionDenied:
        raise
    except PasswordResetRequestUnavailable:
        return _not_found(request)
    except PasswordResetRequestConflict:
        messages.error(request, "Esta solicitação já foi concluída e não pode ser alterada.")
    except DatabaseError:
        messages.error(request, "Não foi possível atualizar a solicitação. Tente novamente.")
    else:
        messages.success(request, "Solicitação rejeitada. A conta e a senha permaneceram inalteradas.")
    return redirect("admin-password-request-detail", request_id=request_id)
