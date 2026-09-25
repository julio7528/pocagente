FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements-docker.txt /tmp/web-portal-requirements.txt

RUN python -m pip install --no-cache-dir -r /tmp/web-portal-requirements.txt \
    && python -m pip check \
    && addgroup --system app \
    && adduser --system --ingroup app --home /home/app app \
    && mkdir -p /home/app \
    && chown -R app:app /home/app

COPY --chown=app:app . /app/apps/web_portal

USER app

EXPOSE 8001

CMD ["uvicorn", "apps.web_portal.config.asgi:application", "--host", "0.0.0.0", "--port", "8001"]
