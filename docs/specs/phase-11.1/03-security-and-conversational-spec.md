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

Safe, stable general questions outside the Getnet domain use a distinct
`DIRECT_GENERAL` capability after both security layers allow the request. It
has no retrieval or tool authority. Changing/current facts retain the Web
capability. Genuine ambiguous requests receive a natural bounded LLM-formulated
clarification from safe context, with a deterministic fallback if generation
fails; off-domain simplicity alone is not ambiguity.

For a safe off-domain direct answer, the LLM answers briefly and naturally adds
a concise, varied invitation to ask about Getnet products/services or
cancellation support. This is response guidance, not a fixed application
sentence and does not grant any capability. Semantic classification and public
Getnet retrieval formulation tolerate high-confidence ordinary spelling and
informal-language variation without a product-specific correction dictionary;
uncertain interpretations remain eligible for clarification. A retrieval
query is a bounded search aid only: the original user request remains the
grounding question and the source of intent, while trusted scope, Web policy,
authorization, and security remain unchanged.

Typed `INSUFFICIENT_EVIDENCE`, provider-unavailable, and genuine clarification
outcomes must not render an empty-answer placeholder in normal chat. A narrow
LLM recovery response may use only the safe original question, typed route and
failure category, and a high-confidence normalized interpretation when one is
available. It asks the user to reformulate or confirm when evidence is lacking;
it must not invent an answer or receive retrieved evidence, prompts, secrets,
or provider error details. Existing output security validation still applies.

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
* `REQ-P11R-DIRECT-004`: the real CLI matrix and unseen paraphrases prove that direct answers occur after security, use no tools, and cross outbound validation.
* `REQ-P11R-DIRECT-005`: genuinely ambiguous requests receive a natural bounded clarification without tools; deterministic clarification is fallback-only.
* `REQ-P11R-DIRECT-006`: safe off-domain direct answers are concise and add a naturally varied LLM-formulated Getnet/support orientation without granting tools or retrieval authority.
* `REQ-P11R-KNOW-009`: Public Getnet retrieval may use a bounded semantic search-query formulation that preserves intent and trusted policy, while original user text remains authoritative for grounding; low-confidence or failed formulation falls back safely.
* `REQ-P11R-CONV-006`: semantic classification tolerates high-confidence minor spelling/informal-language variation, while typed insufficient-evidence/provider failures receive concise safe natural recovery instead of an empty response; genuinely unclear requests still ask for clarification.
