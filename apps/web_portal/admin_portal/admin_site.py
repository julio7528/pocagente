from functools import wraps

from django.contrib.admin import AdminSite
from django.core.exceptions import PermissionDenied

from apps.web_portal.accounts.authorization import user_is_admin


class TechnicalAdminSite(AdminSite):
    """Restricted technical Django Admin; application role is authoritative."""

    site_header = "Getnet Support — Technical Administration"
    site_title = "Getnet Support Admin"
    index_title = "Portal technical administration"

    def has_permission(self, request):
        return user_is_admin(getattr(request, "user", None))

    def admin_view(self, view, cacheable=False):
        protected_view = super().admin_view(view, cacheable=cacheable)

        @wraps(view)
        def role_gated_view(request, *args, **kwargs):
            user = getattr(request, "user", None)
            if getattr(user, "is_authenticated", False) and not self.has_permission(request):
                raise PermissionDenied
            return protected_view(request, *args, **kwargs)

        return role_gated_view


technical_admin_site = TechnicalAdminSite(name="admin")
