"""Server-owned inactivity and absolute lifetime policy for portal sessions."""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import SESSION_KEY, logout
from django.shortcuts import redirect
from django.utils import timezone

from apps.web_portal.accounts.models import ROLE_VALUES, User


AUTHENTICATED_AT_KEY = "portal_authenticated_at"
LAST_ACTIVITY_AT_KEY = "portal_last_activity_at"
SESSION_UNAVAILABLE_MESSAGE = (
    "Sua sessão não está mais disponível. Entre novamente ou contate o administrador."
)


def current_timestamp() -> int:
    return int(timezone.now().timestamp())


def establish_session_policy(request) -> None:
    """Set fixed authentication and sliding activity clocks after Django login."""
    now = current_timestamp()
    request.session[AUTHENTICATED_AT_KEY] = now
    request.session[LAST_ACTIVITY_AT_KEY] = now
    request.session.set_expiry(settings.PORTAL_SESSION_ABSOLUTE_SECONDS)


def invalidate_browser_session(request) -> None:
    logout(request)
    messages.warning(request, SESSION_UNAVAILABLE_MESSAGE)


class PortalSessionPolicyMiddleware:
    """Revalidate identity plus independent inactivity and absolute deadlines."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session_had_identity = bool(request.session.get(SESSION_KEY))
        user = getattr(request, "user", None)
        touch_activity_after_response = False

        if user is not None and user.is_authenticated:
            current_user = User.objects.filter(pk=user.pk).only("is_active", "role").first()
            if (
                current_user is None
                or not current_user.is_active
                or current_user.role not in ROLE_VALUES
            ):
                return self._expire(request)

            now = current_timestamp()
            authenticated_at = request.session.get(AUTHENTICATED_AT_KEY)
            last_activity_at = request.session.get(LAST_ACTIVITY_AT_KEY)

            # Sessions created through Django's technical AdminSite receive the
            # same policy on their first authenticated request.
            if authenticated_at is None or last_activity_at is None:
                establish_session_policy(request)
            else:
                try:
                    inactivity_elapsed = now - int(last_activity_at)
                    absolute_elapsed = now - int(authenticated_at)
                except (TypeError, ValueError):
                    return self._expire(request)
                if (
                    inactivity_elapsed >= settings.PORTAL_SESSION_INACTIVITY_SECONDS
                    or absolute_elapsed >= settings.PORTAL_SESSION_ABSOLUTE_SECONDS
                ):
                    return self._expire(request)
                touch_activity_after_response = True
        elif session_had_identity:
            # AuthenticationMiddleware rejects inactive/missing users; remove
            # the remaining stale session as defense in depth.
            return self._expire(request)

        response = self.get_response(request)
        if (
            touch_activity_after_response
            and response.status_code < 400
            and getattr(request, "user", None) is not None
            and request.user.is_authenticated
        ):
            request.session[LAST_ACTIVITY_AT_KEY] = current_timestamp()
        return response

    @staticmethod
    def _expire(request):
        invalidate_browser_session(request)
        return redirect(settings.LOGIN_URL)
