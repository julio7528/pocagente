FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FASTEMBED_CACHE_PATH=/var/cache/fastembed

WORKDIR /app

COPY . /app/

RUN python -m pip install --no-cache-dir '.[dev]' \
    && python -m pip check \
    && addgroup --system app \
    && adduser --system --ingroup app --home /home/app app \
    && mkdir -p /var/cache/fastembed \
    && chown -R app:app /home/app /var/cache/fastembed

USER app

EXPOSE 8000

CMD ["uvicorn", "apps.agent_api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
