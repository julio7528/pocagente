"""ASGI entry point for the Django web portal."""

import os

from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apps.web_portal.config.settings")

application = ASGIStaticFilesHandler(get_asgi_application())
