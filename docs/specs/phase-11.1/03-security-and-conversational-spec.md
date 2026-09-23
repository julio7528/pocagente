# Phase 11.1 — Deterministic Security and Conversational Capability

## Security hardening

Phase 10 remains the sole security semantic authority. Harden the existing Router-owned classifier rather than adding a second classifier. It shall normalize case, accents where appropriate, whitespace, and punctuation/separators before matching declarative semantic families. It shall detect compositional combinations of override/injection verbs (for example ignore, disregard, `desconsidere`, forget, bypass, circumvent, override, leave aside) with instruction/policy/system targets and protected resource families.

This deterministic preflight completes before any asynchronous semantic-provider call. A matching protected request is terminal and must not await, invoke, or be reclassified by the semantic model.

Protected families remain those approved in Phase 10/security policy: credentials/secrets, direct database access, secret locations, connection strings, protected internal paths, authorization bypass, and infrastructure details materially assisting unauthorized access. The response must preserve the existing typed Phase 10 event/resource classification, sanitizer, `SecurityAuditService`, action `BLOCK`, and terminal graph behavior.

High-level permitted architecture questions remain answerable: asking whether PostgreSQL or pgvector is used is not, by itself, a protected-access request. Tests must prove this non-overblocking boundary.

## Conversational capability

Add a small deterministic, no-tool conversational capability for greetings, thanks, basic orientation, and “what can you do?” messages. It returns a bounded helpful response such as an offer to help with Getnet products/services, documented processes, support, and general information. It does not independently answer knowledge-intensive, protected, operational, or customer-specific requests.

It may be implemented as an additive controlled route/node or an equivalent current-contract extension, but must be observable as `CONVERSATIONAL`, must not be reported as `AMBIGUOUS`, and must preserve safe public response boundaries.

## Requirements

* `REQ-P11R-SEC-001`: Phase 10 deterministic security executes before semantic routing.
* `REQ-P11R-SEC-002`: normalization/compositional security detection covers Portuguese and English override semantics.
* `REQ-P11R-SEC-003`: protected resource/access/bypass families map to current typed Phase 10 semantics.
* `REQ-P11R-SEC-004`: protected requests execute sanitized AUDIT `BLOCK` and terminalize.
* `REQ-P11R-SEC-005`: a block has zero Knowledge, Web, OPS, Human, and provider continuation.
* `REQ-P11R-SEC-006`: permitted high-level architecture questions are not falsely blocked.
* `REQ-P11R-SEC-007`: security policy is neither classified nor overridden by the semantic model.
* `REQ-P11R-CONV-001`: pure greetings/thanks/orientation map to bounded conversational behavior.
* `REQ-P11R-CONV-002`: conversational behavior has no RAG/Web/OPS/Human/tool access.
* `REQ-P11R-CONV-003`: greeting prefixes do not override dominant substantive intent.
* `REQ-P11R-CONV-004`: conversational responses remain public-safe and do not expose implementation detail.
