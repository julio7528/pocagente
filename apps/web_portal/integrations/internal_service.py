"""Shared trusted server-to-server FastAPI transport for narrow typed clients."""

from __future__ import annotations

import atexit
from threading import RLock

import httpx
from django.conf import settings


class InternalServiceConfigurationError(RuntimeError):
    """The private service channel is not configured."""


class InternalServicePrincipalError(RuntimeError):
    """The caller cannot form the requested trusted principal claims."""


def trusted_service_headers(actor, *, ops_authorized: bool = False) -> dict[str, str]:
    """Derive internal headers from an active server-loaded portal identity."""

    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
    ):
        raise InternalServicePrincipalError
    role = str(getattr(actor, "role", ""))
    if role not in {"ADMIN", "CLIENT", "SUPPORT_AGENT"}:
        raise InternalServicePrincipalError
    if ops_authorized and role != "SUPPORT_AGENT":
        raise InternalServicePrincipalError
    token = settings.AGENT_API_SERVICE_TOKEN
    if not token or not settings.AGENT_API_INTERNAL_URL:
        raise InternalServiceConfigurationError
    return {
        "Authorization": f"Bearer {token}",
        "X-Authenticated-User-Id": str(actor.pk),
        "X-Authenticated-Role": role,
        "X-Ops-Authorized": "true" if ops_authorized else "false",
    }


_CLIENTS: dict[tuple[str, float, float], httpx.Client] = {}
_CLIENTS_LOCK = RLock()


def _pooled_http_client(base_url: str, connect_timeout: float, read_timeout: float) -> httpx.Client:
    """Reuse private connection pools keyed by current process configuration."""

    key = (base_url.rstrip("/"), connect_timeout, read_timeout)
    with _CLIENTS_LOCK:
        client = _CLIENTS.get(key)
        if client is None:
            client = httpx.Client(
                base_url=key[0],
                timeout=httpx.Timeout(read_timeout, connect=connect_timeout),
                trust_env=False,
                follow_redirects=False,
            )
            _CLIENTS[key] = client
        return client


def request_internal(
    method: str,
    path: str,
    *,
    actor,
    ops_authorized: bool = False,
    params=None,
    json=None,
):
    """Call one fixed path selected by an application-owned typed client.

    This helper is private to the Django process. It is not exposed as a browser
    proxy and does not accept caller-provided headers or a destination URL.
    """

    if not path.startswith("/") or path.startswith("//") or "://" in path or "#" in path:
        raise InternalServiceConfigurationError
    headers = trusted_service_headers(actor, ops_authorized=ops_authorized)
    base_url = settings.AGENT_API_INTERNAL_URL.rstrip("/")
    client = _pooled_http_client(
        base_url,
        float(settings.AGENT_API_CONNECT_TIMEOUT_SECONDS),
        float(settings.AGENT_API_READ_TIMEOUT_SECONDS),
    )
    return client.request(
        method.upper(),
        path,
        headers=headers,
        params=params,
        json=json,
    )


def clear_internal_http_client_cache() -> None:
    """Close pooled transports; used by process shutdown hooks and tests."""

    with _CLIENTS_LOCK:
        clients = tuple(_CLIENTS.values())
        _CLIENTS.clear()
    for client in clients:
        client.close()


atexit.register(clear_internal_http_client_cache)
