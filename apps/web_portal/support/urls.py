from django.urls import path

from apps.web_portal.support import views


urlpatterns = [
    path("", views.support_dashboard, name="support-landing"),
    path("updates/", views.support_dashboard_updates, name="support-updates"),
    path("<uuid:conversation_id>/", views.support_conversation, name="support-conversation"),
    path("<uuid:conversation_id>/updates/", views.support_conversation_updates, name="support-conversation-updates"),
    path("<uuid:conversation_id>/claim/", views.claim_support_conversation, name="support-claim"),
    path("<uuid:conversation_id>/messages/", views.support_message, name="support-message"),
    path("<uuid:conversation_id>/close/", views.close_support_conversation, name="support-close"),
]
