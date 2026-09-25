"""Safe process-liveness and portal-database readiness responses."""

from __future__ import annotations

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def liveness(_request):
    """Report that Django can serve a request without checking dependencies."""

    return JsonResponse({"status": "ok"})


@require_GET
def readiness(_request):
    """Report portal database connectivity without exposing database errors."""

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ready"})
