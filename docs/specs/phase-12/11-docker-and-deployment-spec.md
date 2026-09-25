# Phase 12.15 — Docker and Deployment Topology

## Future Compose topology

Phase 11 Dockerization supplies the current `postgres` and `agent-api` services.
Phase 12 adds a separately built `web-portal` service:

```text
Browser --127.0.0.1:<portal-port>--> web-portal
                                         | Compose private network
                                         +--> agent-api:8000
                                         +--> postgres:5432 (portal schema only)
agent-api ----------------------------------> postgres:5432 (existing domains)
```

Preserve the existing PostgreSQL service, named data volume, database, schemas,
RAG corpus, OPS facts, AUDIT history, and existing service names. Expose only
the portal browser port on loopback for the POC. FastAPI remains private to
the Compose network or on its currently approved local developer mapping; the
browser must not receive an internal FastAPI route. Use runtime-injected
secrets/environment values, never Dockerfile `ARG`, image layers, source, or
static assets. The POC uses the existing shared PostgreSQL principal; a
dedicated least-privilege portal principal is future production hardening and
is not a Phase 12.3 prerequisite.

Both services wait for PostgreSQL health. Portal may wait for FastAPI health
for readiness but should present controlled degraded integration state if the
agent API is temporarily unavailable after startup. Liveness and readiness
remain distinct. FastAPI and Django startup perform no migrations. Explicit
operator commands execute native schema creation and Django migrations in
sequence after backup/approval. Existing volume persistence must be proven by
restart and `docker compose down`/`up` without `-v`.

## Requirements

- **REQ-P12-DOCKER-001:** Future Compose MUST contain the existing `postgres`
  and `agent-api` plus a new `web-portal`, without renaming/replacing the
  existing PostgreSQL volume or changing its data attachment.
- **REQ-P12-DOCKER-002:** Only the Django portal browser port SHOULD be
  published to loopback; browser traffic MUST NOT require or expose FastAPI's
  internal service credential or trusted authorization headers.
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
