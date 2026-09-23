# Phase 11.1 — Deterministic Security and Conversational Capability

## Security hardening

Phase 10 remains the sole security semantic authority. Harden the existing Router-owned classifier rather than adding a second classifier. It shall normalize case, accents where appropriate, whitespace, and punctuation/separators before matching declarative semantic families. It shall detect compositional combinations of override/injection verbs (for example ignore, disregard, `desconsidere`, forget, bypass, circumvent, override, leave aside) with instruction/policy/system targets and protected resource families.

This deterministic preflight completes before any asynchronous semantic-provider call. A matching protected request is terminal and must not await, invoke, or be reclassified by the semantic model.

Protected families remain those approved in Phase 10/security policy: credentials/secrets, direct database access, secret locations, connection strings, protected internal paths, authorization bypass, and infrastructure details materially assisting unauthorized access. The response must preserve the existing typed Phase 10 event/resource classification, sanitizer, `SecurityAuditService`, action `BLOCK`, and terminal graph behavior.

High-level permitted architecture questions remain answerable: asking whether PostgreSQL or pgvector is used is not, by itself, a protected-access request. Tests must prove this non-overblocking boundary.

## Defense-in-depth security extension (Phase 11.1.5.4)

Deterministic input preflight remains first and terminal for obvious protected requests. When it allows continuation, a provider-neutral strict semantic security classifier runs before business semantic routing. Its closed result contains only action/category/audit-required metadata; it cannot produce a response, route, authorization, capability, tool, SQL, or policy. Provider failure fails closed to a no-capability controlled outcome.

Protected information includes credentials and secrets; direct database/infrastructure access details; protected paths and secret locations; source code, prompts, private tool/repository implementation, internal configuration, and instructions that materially enable restricted infrastructure access. Permitted high-level technology/architecture, documented functional processes, and authorized OPS business facts remain distinct from implementation/access instructions.

Every blocked request continues through the existing Phase 10 audit service and existing approved AUDIT event/resource vocabulary. Raw protected input is never persisted. The normal refusal is formulated naturally by the shared provider-neutral LLM using only validated category, action, language, and safe reason metadata. A short deterministic response is used only when generation fails or is invalid.

Every outbound answer and handoff text passes an application-owned security output gate. Deterministic patterns detect credentials, connection strings, private keys, bearer tokens, protected paths, and internal infrastructure identifiers. A provider-neutral semantic reviewer may return only ALLOW, REDACT, or BLOCK plus a safe category. Recognized spans may be redacted deterministically; unsafe semantic content is blocked and may trigger one new refusal generated only from sanitized metadata. Retrieved documents and OPS/Web evidence are untrusted for disclosure purposes and cannot override this gate.

Clearly abusive or prohibited inappropriate content may be blocked under organizational policy using an existing semantically correct audit category. No event taxonomy/schema change is authorized here; unsupported categories must be reported rather than mislabeled.

## Conversational capability

Add a narrow conversational capability for greetings, thanks, basic orientation, and “what can you do?” messages. On normal provider success, `ConversationalAgent` uses the shared provider-neutral LLM boundary to formulate a natural, brief response in the user's language. It has no tools, RAG, OPS, Web, authorization, routing, or handoff authority and does not independently answer knowledge-intensive, protected, operational, or customer-specific requests. The existing deterministic orientation response is only the safe fallback when generation fails or returns invalid output. Bound and validate generated output; do not require JSON for this user-facing generation.

It may be implemented as an additive controlled route/node or an equivalent current-contract extension, but must be observable as `CONVERSATIONAL`, must not be reported as `AMBIGUOUS`, and must preserve safe public response boundaries.

## Requirements

* `REQ-P11R-SEC-001`: Phase 10 deterministic security executes before semantic routing.
* `REQ-P11R-SEC-002`: normalization/compositional security detection covers Portuguese and English override semantics.
* `REQ-P11R-SEC-003`: protected resource/access/bypass families map to current typed Phase 10 semantics.
* `REQ-P11R-SEC-004`: protected requests execute sanitized AUDIT `BLOCK` and terminalize.
* `REQ-P11R-SEC-005`: a block has zero Knowledge, Web, OPS, Human, and provider continuation.
* `REQ-P11R-SEC-006`: permitted high-level architecture questions are not falsely blocked.
* `REQ-P11R-SEC-007`: security policy is neither classified nor overridden by the business semantic model.
* `REQ-P11R-SEC-008`: deterministic preflight precedes semantic security classification, which precedes business routing; either block prevents all capability calls.
* `REQ-P11R-SEC-009`: semantic security returns only a validated action/category/audit contract and distinguishes functional facts from protected implementation and infrastructure access.
* `REQ-P11R-SEC-010`: blocked responses are normally naturally generated from sanitized metadata; deterministic refusal is fallback only.
* `REQ-P11R-SEC-011`: every blocked request uses current sanitized AUDIT categories; no unsupported event type or schema change is introduced.
* `REQ-P11R-SEC-012`: every candidate final response and handoff crosses deterministic and bounded semantic output review before disclosure.
* `REQ-P11R-SEC-013`: output gate safely redacts recognized sensitive spans or blocks unsafe semantic content; at most one safe regeneration receives no unsafe candidate.
* `REQ-P11R-SEC-014`: RAG/OPS/Web evidence is untrusted for disclosure; protected implementation details cannot escape while functional answers remain available.
* `REQ-P11R-SEC-015`: inappropriate-content blocking uses contextual policy and only semantically correct existing AUDIT categories.
* `REQ-P11R-CONV-001`: pure greetings/thanks/orientation map to bounded conversational behavior.
* `REQ-P11R-CONV-002`: conversational behavior has no RAG/Web/OPS/Human/tool access.
* `REQ-P11R-CONV-003`: greeting prefixes do not override dominant substantive intent.
* `REQ-P11R-CONV-004`: conversational responses remain public-safe and do not expose implementation detail.
* `REQ-P11R-CONV-005`: normal conversational responses are naturally formulated through the approved provider-neutral LLM boundary without tools/RAG/OPS/Web authority; deterministic orientation is a safe generation-failure fallback.
