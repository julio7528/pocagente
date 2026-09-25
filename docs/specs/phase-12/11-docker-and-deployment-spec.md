# Phase 12.15 — Docker and Deployment Topology

## Implemented Compose topology

Phase 11 Dockerization supplies the existing `postgres` and `agent-api`
services. Phase 12.15 adds a separately built `web-portal` service without
renaming either existing service or replacing the PostgreSQL data volume:

```text
Browser --127.0.0.1:8001--> web-portal
                                         | Compose private network
                                         +--> agent-api:8000
                                         +--> postgres:5432 (portal schema only)
agent-api ----------------------------------> postgres:5432 (existing domains)
```

Preserve the existing PostgreSQL service, named data volume, database,
schemas, RAG corpus, OPS facts, AUDIT history, and existing service names. The
portal browser port binds to `127.0.0.1:8001`. Existing loopback developer
mappings for PostgreSQL (`127.0.0.1:5432`) and FastAPI
(`127.0.0.1:8000`) are retained unchanged. The browser calls Django only and
never receives an internal FastAPI route, service token, or trusted headers.
Use runtime-injected secrets/environment values, never Dockerfile `ARG`,
image layers, source, or static assets. The POC uses the existing shared
PostgreSQL principal; a dedicated least-privilege portal principal is future
production hardening and is not a Phase 12.3 prerequisite.

Both `agent-api` and `web-portal` wait for PostgreSQL health. The portal does
not depend on FastAPI startup, so portal-owned login/history/admin pages remain
available during an agent outage. `/health/` reports process liveness;
`/ready/` checks the portal database. Startup performs no migration, seed,
admin bootstrap, or database reset. Native schema creation and Django
migrations are explicit operator actions after backup/approval. Existing
volume persistence is verified by service restarts and
`docker compose down`/`up` without `-v`.

The portal image uses the existing project Python 3.14 base and a dedicated
`requirements-docker.txt` containing the already approved Django, HTTPX,
Pydantic, psycopg, and Uvicorn versions. Uvicorn serves Django's ASGI app;
`ASGIStaticFilesHandler` serves the portal's local assets, including the
self-hosted Chart.js 4.5.1 file. No frontend build, CDN, migration entrypoint,
or additional service is introduced.

## Requirements

- **REQ-P12-DOCKER-001:** Compose MUST contain the existing `postgres`
  and `agent-api` plus a new `web-portal`, without renaming/replacing the
  existing PostgreSQL volume or changing its data attachment.
- **REQ-P12-DOCKER-002:** The Django portal browser port MUST bind to loopback.
  Existing approved loopback developer mappings for PostgreSQL and FastAPI
  remain unchanged. Browser traffic MUST call Django only and MUST NOT expose
  FastAPI's internal service credential or trusted authorization headers.
- **REQ-P12-DOCKER-003:** `web-portal` MUST reach FastAPI and PostgreSQL by
  private service networking with runtime-configured addresses; Django DB
  access MUST be scoped to `portal` and no host/address may be hardcoded in
  application code.
- **REQ-P12-DOCKER-004:** Secrets MUST be injected only at runtime and MUST NOT
  be committed, copied into source/image layers, printed, or placed in browser
  responses.
- **REQ-P12-DOCKER-005:** Health checks and service startup ordering MUST
  distinguish process liveness from dependency readiness and MUST provide a
  controlled degraded state when FastAPI is unavailable.
- **REQ-P12-DOCKER-006:** Native portal-schema migration and Django migration
  commands MUST remain explicit; container build/startup MUST NOT run
  migrations, seed/destructive scripts, volume reset, or database recreation.

## Phase 12.15 execution evidence (2026-09-25)

- Before the change, Compose contained `postgres` and `agent-api`. After the
  change, `docker compose config` contains exactly `postgres`, `agent-api`,
  and `web-portal`. The existing host mappings remain on loopback at ports
  5432 and 8000; the portal binds to `127.0.0.1:8001`.
- PostgreSQL volume identity before and after the safe down/up cycle:
  `getnet-support_getnet_support_pgdata`, mounted at
  `/var/lib/postgresql/data`. Validation used `docker compose down` followed
  by `docker compose up -d`; `down -v` was not run.
- The clean, no-cache web-portal build reported a 5.75 KB compressed context
  transfer; its separate portal `.dockerignore` excludes `.env`, `.env.*`,
  `.docker-secrets`, `.git`, virtual environments, local databases, and
  test/cache artifacts.
  The root ignore was also exercised by rebuilding `agent-api` successfully.
- The portal image runs only
  `uvicorn apps.web_portal.config.asgi:application --host 0.0.0.0 --port 8001`
  as a non-root user. Its image configuration/history contains no application
  secrets or build arguments; no `.env` or secret directory exists in the
  image. Secrets are passed at runtime. No package was added to the project
  dependency set; the container manifest pins the already approved runtime
  packages.
- `web-portal` does not depend on `agent-api` startup. From inside the portal
  container, Django connected to `current_schema() = portal`, the typed
  AgentChatClient reached `/chat` through `agent-api:8000` and returned a safe
  completed response, and the existing read-only AUDIT client returned a
  snapshot through FastAPI. No portal record was created by those connectivity
  smokes.
- `/health/`, `/ready/`, `/login/`, portal CSS/JS, and the local Chart.js asset
  returned HTTP 200. The chart file is present in the image at 208,522 bytes.
  The portal's Docker healthcheck calls `/ready/`; readiness returned 503
  while PostgreSQL was stopped even though liveness stayed 200, then recovered
  after PostgreSQL restart. During a separate agent-api outage, portal pages
  stayed available and the chat client returned its controlled retryable
  unavailable state; service recovery restored the integration.
- Startup logs and the browser login response were scanned for runtime
  credentials. Image metadata/history and image paths were checked for baked
  secrets. Runtime secrets are not printed in validation output.
- Startup uses the Dockerfile `CMD` only; it contains no migration, schema,
  seed, `bootstrap_admin`, or cleanup invocation. Container checks passed:
  `manage.py check`, `showmigrations`,
  `makemigrations --check --dry-run` (no changes), and `python -m pip check`.
  `agent-api` container `pip check` also passed. The unrelated host-global
  `google-adk 1.23.0`/FastAPI version conflict remains unchanged.
- Explicit operator procedure, only after backup/approval and only when the
  portal schema has not already been created:

  ```powershell
  $compose = docker compose config --format json | ConvertFrom-Json
  $dbUser = $compose.services.postgres.environment.POSTGRES_USER
  $dbName = $compose.services.postgres.environment.POSTGRES_DB
  Get-Content -Raw .\database\migrations\0007_portal_schema.sql |
    docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U $dbUser -d $dbName
  docker compose run --rm --no-deps web-portal python apps/web_portal/manage.py migrate --noinput
  docker compose run --rm --no-deps web-portal python apps/web_portal/manage.py showmigrations
  ```

  `0007_portal_schema.sql` is immutable and creates the schema; do not rerun it
  against an already-existing `portal` schema. First-admin creation remains a
  separate explicit operator action:

  ```powershell
  docker compose run --rm --no-deps web-portal python apps/web_portal/manage.py bootstrap_admin
  ```

- Persistent baseline and final counts were identical:

  | Domain | Table | Before | After |
  |---|---|---:|---:|
  | portal | users | 3 | 3 |
  | portal | conversations | 8 | 8 |
  | portal | messages | 24 | 24 |
  | portal | support_handoffs | 0 | 0 |
  | portal | password_reset_requests | 0 | 0 |
  | rag | sources | 3 | 3 |
  | rag | documents | 7 | 7 |
  | rag | chunks | 221 | 221 |
  | ops | service_requests | 5 | 5 |
  | ops | automation_runs | 9 | 9 |
  | ops | execution_log | 75 | 75 |
  | ops | establishments | 5 | 5 |
  | audit | security_events | 146 | 146 |

  The `vector` extension remained at 0.8.6 and the RAG vector distance operator
  remained usable. The isolated Django validation database was removed; no
  persistent domain rows were added or deleted.
- The Django application suite passed **181 tests** on disposable PostgreSQL;
  the Phase 12.14 route/journey suite passed **4 tests** against a separate
  disposable database. Full `python -m pytest` passed **928**, skipped **37**,
  with one existing FastEmbed warning. `compileall` and `git diff --check`
  passed. The final roadmap status is Phase 12.15 complete and 12.16 next;
  Phase 12.16 implementation did not start.
