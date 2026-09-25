"""Browser-facing route composition for the Django portal."""

from django.urls import include, path

from apps.web_portal.accounts import views as account_views
from apps.web_portal.admin_portal.admin_site import technical_admin_site
from apps.web_portal.admin_portal import user_admin  # noqa: F401 - registers the technical User view
from apps.web_portal.config import health


urlpatterns = [
    path("health/", health.liveness, name="health"),
    path("ready/", health.readiness, name="ready"),
    path("login/", account_views.login_view, name="login"),
    path(
        "password-reset/request/",
        account_views.password_reset_request_view,
        name="password-reset-request",
    ),
    path(
        "password-reset/request/confirm/",
        account_views.password_reset_request_confirm_view,
        name="password-reset-request-confirm",
    ),
    path("logout/", account_views.logout_view, name="logout"),
    path("chat/", include("apps.web_portal.conversations.urls")),
    path("support/", include("apps.web_portal.support.urls")),
    path("admin-portal/", include("apps.web_portal.admin_portal.urls")),
    path("admin/", technical_admin_site.urls),
]

handler403 = "apps.web_portal.accounts.views.permission_denied_view"
