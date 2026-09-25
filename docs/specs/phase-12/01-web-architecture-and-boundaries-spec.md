# Phase 12.1–12.2 — Web Architecture and Service Structure

## Application boundary

`apps/agent_api` remains the existing FastAPI service. Add a future
`apps/web_portal` Django service. Django is a backend-for-frontend (BFF) for
browser requests and the source of truth for web identity and conversation
state. It calls FastAPI over authenticated server-to-server HTTP for agent
turns, trusted Human Escalation coordination, and administrative AUDIT reads.

```text
Browser --Django session/CSRF--> Django web_portal
                                    | trusted internal HTTP
                                    v
                              FastAPI agent_api
                               / LangGraph
                         RAG / OPS / Audit / Web
```

The browser never calls FastAPI directly. Hiding a link is not authorization:
Django server-side route and object checks guard every operation. Django owns
presentation and web state; FastAPI owns all agent/business decisions and the
existing data-domain repositories.

## Proposed Django package organization

```text
apps/web_portal/
  manage.py
  config/             settings, URL composition, WSGI/ASGI
  accounts/           custom user, login/session, role and account policy
  conversations/      conversation/message models, client views/services
  support/             handoff records, support queue and human messages
  admin_portal/        user, conversation, and reset-request workflows
  integrations/        typed FastAPI clients and error mapping
  templates/           shared and role-specific Django templates
  static/              scoped CSS and ordinary browser JavaScript
```

Keep business operations in narrow Django services, not view functions or
templates. Templates render data and forms; they do not make authorization
decisions. Use Django's standard app registry and migrations. A multi-database
router or Django model must not give the portal ownership of `rag`, `ops`, or
`audit`.

## Requirements

- **REQ-P12-ARCH-001:** The portal MUST be a Django application under
  `apps/web_portal`; `apps/agent_api` MUST remain the FastAPI agent/backend
  service. Generic `apps/frontend` and `apps/backend` replacements are
  prohibited.
- **REQ-P12-ARCH-002:** Browser agent execution MUST pass through an
  authenticated Django request and a trusted server-to-server FastAPI call;
  browser JavaScript MUST NOT call FastAPI directly.
- **REQ-P12-ARCH-003:** Django MUST own login/session, users, roles, account
  state, conversations, messages, persistent handoffs, and portal workflows;
  FastAPI MUST own Router, orchestration, agents, security, RAG, OPS, Web,
  Human Escalation decisions, and AUDIT repository access.
- **REQ-P12-ARCH-004:** Django MUST NOT duplicate routing, agent reasoning,
  RAG retrieval, OPS access, security decisions, or provider integrations.
- **REQ-P12-ARCH-005:** Internal integration MUST use typed service clients
  and stable transport DTOs; portal views MUST NOT import LangGraph state,
  provider SDKs, database repositories, or runtime implementation modules.
- **REQ-P12-ARCH-006:** The Django package MUST be modular, with accounts,
  conversations, support, admin workflows, and integrations separated by
  ownership; templates and browser code MUST remain presentation-only.
- **REQ-P12-ARCH-007:** Phase 12 MUST preserve the existing local FastAPI and
  Docker PostgreSQL/agent-api workflows while adding web_portal as a separate
  service; the frontend MUST remain usable without exposing agent internals.
