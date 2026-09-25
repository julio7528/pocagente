from __future__ import annotations

from uuid import UUID

from django.contrib import messages
from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.web_portal.accounts.models import ROLE_VALUES, User
from apps.web_portal.accounts.services import (
    AccountPolicyError,
    ActiveSupportAssignmentError,
    LastActiveAdminError,
    activate_user,
    change_role,
    create_user,
    deactivate_user,
    set_user_password,
)
from apps.web_portal.accounts.views import role_required
from apps.web_portal.admin_portal.forms import (
    AdminSetPasswordForm,
    RoleChangeForm,
    UserCreateForm,
)


PAGE_SIZE = 25
ROLE_FILTERS = frozenset(ROLE_VALUES)
STATE_FILTERS = frozenset({"ACTIVE", "INACTIVE"})
USER_FIELDS = ("id", "username", "role", "is_active", "created_at", "updated_at", "last_login")


def _user_queryset():
    return User.objects.only(*USER_FIELDS).order_by("username", "id")


def _admin_error_message(exc: Exception) -> str:
    if isinstance(exc, LastActiveAdminError):
        return "Não é possível remover o último administrador ativo."
    if isinstance(exc, ActiveSupportAssignmentError):
        return "O atendente possui um atendimento humano ativo e não pode ser desativado ou trocar de perfil."
    if isinstance(exc, ValidationError):
        return "A senha não atende à política configurada. Revise os critérios e tente novamente."
    if isinstance(exc, AccountPolicyError):
        return "A operação não pôde ser concluída. Confira os dados e tente novamente."
    return "Não foi possível concluir a operação. Tente novamente."


def _safe_target(target_id: UUID) -> User:
    return get_object_or_404(_user_queryset(), pk=target_id)


def _success_redirect(request: HttpRequest, target_id: UUID, message: str) -> HttpResponse:
    acting_user_id = getattr(request.user, "pk", None)
    if acting_user_id == target_id:
        # The account service revokes persisted sessions. Flush the in-flight
        # request too, so message middleware cannot save its authenticated data
        # back under the revoked session key.
        logout(request)
        messages.success(request, "Sua sessão foi encerrada pela alteração. Entre novamente para continuar.")
        return redirect("login")
    messages.success(request, message)
    return redirect("admin-user-detail", target_id=target_id)


@role_required(User.Role.ADMIN)
@require_GET
def overview(request: HttpRequest) -> HttpResponse:
    try:
        counts = User.objects.aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(is_active=True)),
            inactive=Count("id", filter=Q(is_active=False)),
            clients=Count("id", filter=Q(role=User.Role.CLIENT)),
            support_agents=Count("id", filter=Q(role=User.Role.SUPPORT_AGENT)),
            admins=Count("id", filter=Q(role=User.Role.ADMIN)),
        )
    except DatabaseError:
        messages.error(request, "Não foi possível carregar o resumo de usuários.")
        counts = {key: 0 for key in ("total", "active", "inactive", "clients", "support_agents", "admins")}
        return render(request, "admin_portal/overview.html", {"counts": counts}, status=503)
    return render(request, "admin_portal/overview.html", {"counts": counts})


@role_required(User.Role.ADMIN)
@require_GET
def user_list(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("q", "").strip()[:100]
    requested_role = request.GET.get("role", "")
    requested_state = request.GET.get("state", "")
    role = requested_role if requested_role in ROLE_FILTERS else ""
    state = requested_state if requested_state in STATE_FILTERS else ""

    users = _user_queryset()
    if query:
        users = users.filter(username__icontains=query)
    if role:
        users = users.filter(role=role)
    if state == "ACTIVE":
        users = users.filter(is_active=True)
    elif state == "INACTIVE":
        users = users.filter(is_active=False)

    paginator = Paginator(users, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    context = {
        "page_obj": page_obj,
        "users": page_obj.object_list,
        "query": query,
        "selected_role": role,
        "selected_state": state,
        "page_query": query_params.urlencode(),
        "role_choices": User.Role.choices,
    }
    return render(request, "admin_portal/users.html", context)


@role_required(User.Role.ADMIN)
@require_GET
def user_create(request: HttpRequest) -> HttpResponse:
    return render(request, "admin_portal/user_create.html", {"form": UserCreateForm()})


@role_required(User.Role.ADMIN)
@require_POST
def user_create_submit(request: HttpRequest) -> HttpResponse:
    form = UserCreateForm(request.POST)
    if form.is_valid():
        try:
            result = create_user(
                actor=request.user,
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"],
                role=form.cleaned_data["role"],
                is_active=form.cleaned_data["is_active"],
            )
        except PermissionDenied:
            raise
        except AccountPolicyError:
            form.add_error("username", "Não foi possível criar o usuário. Confira o login e a senha.")
        except ValidationError:
            form.add_error("password", "A senha não atende à política configurada. Revise os critérios.")
        except DatabaseError:
            messages.error(request, "Não foi possível criar o usuário. Tente novamente.")
            return render(request, "admin_portal/user_create.html", {"form": form}, status=503)
        else:
            messages.success(request, "Usuário criado com sucesso.")
            return redirect("admin-user-detail", target_id=result.user.pk)
    return render(request, "admin_portal/user_create.html", {"form": form}, status=400)


@role_required(User.Role.ADMIN)
@require_GET
def user_detail(request: HttpRequest, target_id: UUID) -> HttpResponse:
    try:
        target = _safe_target(target_id)
    except DatabaseError:
        messages.error(request, "Não foi possível carregar os dados do usuário.")
        return redirect("admin-users")
    context = {
        "target": target,
        "role_form": RoleChangeForm(initial={"role": target.role}),
        "password_form": AdminSetPasswordForm(),
    }
    return render(request, "admin_portal/user_detail.html", context)


@role_required(User.Role.ADMIN)
@require_POST
def user_activate(request: HttpRequest, target_id: UUID) -> HttpResponse:
    return _change_account_state(request, target_id, activate_user, "Usuário ativado.")


@role_required(User.Role.ADMIN)
@require_POST
def user_deactivate(request: HttpRequest, target_id: UUID) -> HttpResponse:
    return _change_account_state(request, target_id, deactivate_user, "Usuário desativado.")


def _change_account_state(request, target_id, operation, success_message):
    try:
        target = _safe_target(target_id)
        operation(actor=request.user, target=target)
    except PermissionDenied:
        raise
    except AccountPolicyError as exc:
        messages.error(request, _admin_error_message(exc))
    except DatabaseError:
        messages.error(request, "Não foi possível atualizar o usuário. Tente novamente.")
        return redirect("admin-users")
    else:
        return _success_redirect(request, target_id, success_message)
    return redirect("admin-user-detail", target_id=target_id)


@role_required(User.Role.ADMIN)
@require_POST
def user_change_role(request: HttpRequest, target_id: UUID) -> HttpResponse:
    try:
        target = _safe_target(target_id)
    except DatabaseError:
        messages.error(request, "Não foi possível carregar os dados do usuário.")
        return redirect("admin-users")
    form = RoleChangeForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Selecione um dos perfis disponíveis.")
        return redirect("admin-user-detail", target_id=target_id)
    try:
        change_role(actor=request.user, target=target, new_role=form.cleaned_data["role"])
    except PermissionDenied:
        raise
    except AccountPolicyError as exc:
        messages.error(request, _admin_error_message(exc))
    except DatabaseError:
        messages.error(request, "Não foi possível atualizar o perfil. Tente novamente.")
    else:
        return _success_redirect(request, target_id, "Perfil atualizado.")
    return redirect("admin-user-detail", target_id=target_id)


@role_required(User.Role.ADMIN)
@require_POST
def user_set_password(request: HttpRequest, target_id: UUID) -> HttpResponse:
    try:
        target = _safe_target(target_id)
    except DatabaseError:
        messages.error(request, "Não foi possível carregar os dados do usuário.")
        return redirect("admin-users")
    form = AdminSetPasswordForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Confira a confirmação da nova senha.")
        return redirect("admin-user-detail", target_id=target_id)
    try:
        set_user_password(
            actor=request.user,
            target=target,
            new_password=form.cleaned_data["new_password"],
        )
    except PermissionDenied:
        raise
    except (AccountPolicyError, ValidationError) as exc:
        messages.error(request, _admin_error_message(exc))
    except DatabaseError:
        messages.error(request, "Não foi possível alterar a senha. Tente novamente.")
    else:
        return _success_redirect(
            request,
            target_id,
            "Senha alterada. As sessões anteriores do usuário foram encerradas.",
        )
    return redirect("admin-user-detail", target_id=target_id)
