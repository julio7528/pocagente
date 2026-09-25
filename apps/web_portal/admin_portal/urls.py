from django.urls import path

from apps.web_portal.admin_portal import views
from apps.web_portal.admin_portal import security_views
from apps.web_portal.admin_portal import conversation_views
from apps.web_portal.admin_portal import password_request_views


urlpatterns = [
    path("", views.overview, name="admin-overview"),
    path("users/", views.user_list, name="admin-users"),
    path("users/new/", views.user_create, name="admin-user-create"),
    path("users/new/submit/", views.user_create_submit, name="admin-user-create-submit"),
    path("users/<uuid:target_id>/", views.user_detail, name="admin-user-detail"),
    path("users/<uuid:target_id>/activate/", views.user_activate, name="admin-user-activate"),
    path("users/<uuid:target_id>/deactivate/", views.user_deactivate, name="admin-user-deactivate"),
    path("users/<uuid:target_id>/role/", views.user_change_role, name="admin-user-role"),
    path("users/<uuid:target_id>/password/", views.user_set_password, name="admin-user-password"),
    path("security/", security_views.security_dashboard, name="admin-security"),
    path("security/data/", security_views.security_dashboard_data, name="admin-security-data"),
    path(
        "security/events/<int:event_id>/",
        security_views.security_event_detail,
        name="admin-security-event-detail",
    ),
    path("conversations/", conversation_views.conversation_list, name="admin-conversations"),
    path(
        "password-requests/",
        password_request_views.password_request_list,
        name="admin-password-requests",
    ),
    path(
        "password-requests/<uuid:request_id>/",
        password_request_views.password_request_detail,
        name="admin-password-request-detail",
    ),
    path(
        "password-requests/<uuid:request_id>/resolve/",
        password_request_views.password_request_resolve,
        name="admin-password-request-resolve",
    ),
    path(
        "password-requests/<uuid:request_id>/reject/",
        password_request_views.password_request_reject,
        name="admin-password-request-reject",
    ),
    path(
        "conversations/<uuid:conversation_id>/",
        conversation_views.conversation_detail,
        name="admin-conversation-detail",
    ),
    path(
        "conversations/<uuid:conversation_id>/block/",
        conversation_views.conversation_block,
        name="admin-conversation-block",
    ),
    path(
        "conversations/<uuid:conversation_id>/unblock/",
        conversation_views.conversation_unblock,
        name="admin-conversation-unblock",
    ),
    path(
        "conversations/<uuid:conversation_id>/delete/",
        conversation_views.conversation_soft_delete,
        name="admin-conversation-delete",
    ),
]
