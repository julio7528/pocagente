FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY apps/web_portal/requirements-docker.txt /tmp/web-portal-requirements.txt

RUN python -m pip install --no-cache-dir -r /tmp/web-portal-requirements.txt \
    && python -m pip check \
    && addgroup --system app \
    && adduser --system --ingroup app --home /home/app app \
    && mkdir -p /home/app \
    && chown -R app:app /home/app

COPY --chown=app:app apps/web_portal /app/apps/web_portal
COPY --chown=app:app apps/agent_api/app/__init__.py /app/apps/agent_api/app/__init__.py
COPY --chown=app:app apps/agent_api/app/telemetry.py /app/apps/agent_api/app/telemetry.py
COPY --chown=app:app apps/agent_api/app/telemetry_presentation.py /app/apps/agent_api/app/telemetry_presentation.py

USER app

EXPOSE 8001

CMD ["uvicorn", "apps.web_portal.config.asgi:application", "--host", "0.0.0.0", "--port", "8001"]
