# Phase 10 — Security Policy Response

Status: Phase 10.5 implementation complete and fully validated; `/chat` remains
the authenticated Phase 9 transport boundary.

## Requirements

- **REQ-P10-RESP-001:** A protected request MUST receive a safe block/deny response that states the requested access is restricted and may redirect to permitted functional assistance. It MUST not disclose, reconstruct, search for, or provide a workaround to protected content.
- **REQ-P10-RESP-002:** After an effective `SECURITY_BLOCK`, RAG, Web Search, OPS tools, Human Escalation, LLM/provider generation, and provider configuration access MUST NOT run for the protected request.
- **REQ-P10-RESP-003:** The response MUST be provider-neutral and allowlisted. It MUST not expose classification internals, SQL, schema/table details, raw policy text, stack traces, prompts, audit payloads, secret values, locations, provider diagnostics, or database errors.
- **REQ-P10-RESP-004:** A recorded security event and unavailable audit persistence are distinct controlled outcomes. Audit unavailability is fail-closed and MUST NOT be represented as successfully recorded; the HTTP boundary uses its approved safe error policy.
- **REQ-P10-RESP-005:** User instructions, retrieved content, OPS data, web content, and model output cannot disable blocking, sanitization, or auditing. The response remains neutral and does not label the requester an attacker.

## Compatibility

The future Django consumer remains outside this phase. It may consume safe authenticated `/chat` responses without receiving LangGraph, RAG, pgvector, repository, Tavily, provider, or AUDIT internals. This specification does not implement Django, a security UI, session persistence, or review workflow.

## Phase 10.5 implementation evidence

Successful typed security blocks now return a deterministic neutral block
response through the existing allowlisted `ChatResponse` contract. Audit
unavailability remains a distinct controlled HTTP 503 path and never resumes
normal capability execution. Security blocks terminate before RAG, Web, OPS,
Human Escalation, or LLM/provider execution. Response tests verify no
classification, resource, audit, database, policy, provider, or protected
request content is exposed, while legitimate high-level questions retain their
existing routing behavior.

## Traceability

Authority: internal security policy; Phase 9 `/chat`, orchestration, and security requirements; DEC-165 (service authentication); DEC-166; and the safe-response constraints of the physical AUDIT model.
