"""Environment-backed Django foundation; portal persistence is not initialized here."""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parents[3]


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be configured in the environment.")
DEBUG = _env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = _env_csv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.web_portal.accounts.apps.AccountsConfig",
    "apps.web_portal.conversations.apps.ConversationsConfig",
    "apps.web_portal.support.apps.SupportConfig",
    "apps.web_portal.admin_portal.apps.AdminPortalConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.web_portal.accounts.session_policy.PortalSessionPolicyMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "apps.web_portal.config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "apps" / "web_portal" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "apps.web_portal.config.wsgi.application"
ASGI_APPLICATION = "apps.web_portal.config.asgi.application"

# Phase 12.3 owns the portal schema and search-path/migration strategy. This
# environment-backed connection definition performs no connection or DDL.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "getnet_support"),
        "USER": os.getenv("POSTGRES_USER", "getnet_app"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 0,
        "TEST": {"NAME": os.getenv("POSTGRES_TEST_DB") or None},
        # Resolve unqualified Django table names only in the portal schema.
        "OPTIONS": {"options": "-c search_path=portal"},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/login/"

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "apps" / "web_portal" / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = _env_bool(
    "WEB_PORTAL_SECURE_COOKIES", _env_bool("DJANGO_SESSION_COOKIE_SECURE")
)
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = False
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = _env_bool(
    "WEB_PORTAL_SECURE_COOKIES", _env_bool("DJANGO_CSRF_COOKIE_SECURE")
)
PORTAL_SESSION_INACTIVITY_SECONDS = 30 * 60
PORTAL_SESSION_ABSOLUTE_SECONDS = 8 * 60 * 60
AGENT_API_INTERNAL_URL = os.getenv("AGENT_API_INTERNAL_URL", "").rstrip("/")
AGENT_API_SERVICE_TOKEN = os.getenv("AGENT_API_SERVICE_TOKEN", "")
AGENT_API_CONNECT_TIMEOUT_SECONDS = float(os.getenv("AGENT_API_CONNECT_TIMEOUT_SECONDS", "2"))
AGENT_API_READ_TIMEOUT_SECONDS = float(os.getenv("AGENT_API_READ_TIMEOUT_SECONDS", "90"))
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
