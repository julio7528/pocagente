from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.web_portal.accounts.authorization import user_is_admin
from apps.web_portal.accounts.models import User
from apps.web_portal.admin_portal.admin_site import technical_admin_site


@admin.register(User, site=technical_admin_site)
class ReadOnlyPortalUserAdmin(UserAdmin):
    """Identity inspection only; mutations belong to the approved service layer."""

    list_display = ("username", "role", "is_active", "created_at", "last_login")
    list_filter = ("role", "is_active")
    search_fields = ("username", "email")
    ordering = ("username",)
    readonly_fields = (
        "id",
        "username",
        "email",
        "role",
        "is_active",
        "is_staff",
        "is_superuser",
        "date_joined",
        "created_at",
        "updated_at",
        "last_login",
    )
    exclude = ("password", "groups", "user_permissions")

    def has_module_permission(self, request):
        return user_is_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return user_is_admin(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
