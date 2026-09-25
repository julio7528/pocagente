"""WSGI entry point for the Django web portal."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apps.web_portal.config.settings")

application = get_wsgi_application()
