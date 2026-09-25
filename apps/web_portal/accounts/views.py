from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.web_portal.accounts.authorization import has_role
from apps.web_portal.accounts.forms import (
    LoginForm,
    PasswordResetRequestConfirmationForm,
    PasswordResetRequestForm,
)
from apps.web_portal.accounts.models import User
from apps.web_portal.accounts.password_reset_services import request_password_reset
from apps.web_portal.accounts.session_policy import establish_session_policy


INVALID_LOGIN_MESSAGE = "Usuário ou senha inválidos."
ROLE_LANDINGS = {
    User.Role.CLIENT: "/chat/",
    User.Role.SUPPORT_AGENT: "/support/",
    User.Role.ADMIN: "/admin-portal/",
}


def landing_for_role(role: str) -> str | None:
    return ROLE_LANDINGS.get(role)


@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        destination = landing_for_role(request.user.role)
        if destination and request.user.is_active:
            return redirect(destination)
        logout(request)

    form = LoginForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"],
            )
            destination = landing_for_role(getattr(user, "role", ""))
            if user is not None and user.is_active and destination:
                login(request, user)
                establish_session_policy(request)
                return redirect(destination)
        form.add_error(None, INVALID_LOGIN_MESSAGE)

    return render(request, "accounts/login.html", {"form": form})


@require_http_methods(["GET", "POST"])
def password_reset_request_view(request: HttpRequest) -> HttpResponse:
    form = PasswordResetRequestForm(
        request.POST if request.method == "POST" else None
    )
    if request.method == "POST":
        if not form.is_valid():
            return render(
                request,
                "accounts/password_reset_request.html",
                {"form": form},
                status=400,
            )
        confirmation_form = PasswordResetRequestConfirmationForm(
            initial={"username": form.cleaned_data["username"]}
        )
        return render(
            request,
            "accounts/password_reset_confirm.html",
            {"form": confirmation_form},
        )
    return render(request, "accounts/password_reset_request.html", {"form": form})


@require_POST
def password_reset_request_confirm_view(request: HttpRequest) -> HttpResponse:
    form = PasswordResetRequestConfirmationForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "accounts/password_reset_confirm.html",
            {"form": form},
            status=400,
        )
    try:
        # Both known/inactive and unknown identifiers lead to the same static
        # response. The service result and request UUID never leave the server.
        request_password_reset(form.cleaned_data["username"])
    except DatabaseError:
        return render(
            request,
            "accounts/password_reset_unavailable.html",
            status=503,
        )
    return render(request, "accounts/password_reset_confirmation.html")


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("login")


def role_required(role: str):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request: HttpRequest, *args, **kwargs):
            if not request.user.is_authenticated:
                if request.COOKIES.get("sessionid"):
                    messages.warning(
                        request,
                        "Sua sessão não está mais disponível. Entre novamente ou contate o administrador.",
                    )
                return redirect("login")
            if not has_role(request.user, role):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


@role_required(User.Role.SUPPORT_AGENT)
def support_landing(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/role_landing.html", {"area_name": "Área de suporte"})


@role_required(User.Role.ADMIN)
def admin_landing(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/role_landing.html", {"area_name": "Área administrativa"})


def permission_denied_view(request: HttpRequest, exception=None) -> HttpResponse:
    destination = landing_for_role(getattr(request.user, "role", ""))
    return render(
        request,
        "accounts/403.html",
        {"allowed_destination": destination},
        status=403,
    )
