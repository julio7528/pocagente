from django.urls import path

from apps.web_portal.conversations import views
from apps.web_portal.support import views as support_views


urlpatterns = [
    path("", views.chat_home, name="client-landing"),
    path("new/", views.new_conversation, name="chat-new"),
    path("<uuid:conversation_id>/updates/", views.conversation_updates, name="chat-updates"),
    path("<uuid:conversation_id>/messages/<uuid:message_id>/retry/", views.retry_agent_message, name="chat-retry-agent"),
    path("<uuid:conversation_id>/human-support/confirm/", support_views.confirm_human_support, name="support-confirm"),
    path("<uuid:conversation_id>/human-support/request/", support_views.request_human_support_view, name="support-request-human"),
    path("<uuid:conversation_id>/", views.conversation_detail, name="chat-detail"),
    path("<uuid:conversation_id>/messages/", views.append_message, name="chat-message"),
]
