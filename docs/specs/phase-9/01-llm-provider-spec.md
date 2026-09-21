# Phase 9.2 — Provider-neutral LLM boundary

Status: Phase 9.2 implementation complete. The provider-neutral boundary and
initial DeepSeek adapter passed mocked validation and an explicitly enabled real
smoke test. The API key remains local runtime configuration and is not present
in this specification or repository-tracked source.

## Contract

The provider layer MUST expose a typed, provider-neutral generation boundary to
agents. DeepSeek is the intended first real provider, but agent code MUST NOT
depend on a DeepSeek SDK or provider-specific response shape.

The future provider layer MUST handle request construction, generation, response
extraction, configuration validation, timeout handling, controlled provider
error translation, and a provider-neutral return contract.

It MUST NOT query PostgreSQL, perform retrieval/RRF/grounding, choose agents,
execute OPS tools, read arbitrary environment variables, decide authorization,
or expose API keys.

The DeepSeek credential MUST arrive through approved runtime configuration and
MUST never be hard-coded, committed, logged, returned, or included in prompts.

## Requirements

- **REQ-P9-LLM-001:** Agents MUST depend on a provider-neutral interface.
- **REQ-P9-LLM-002:** DeepSeek MUST be the initial provider behind that interface.
- **REQ-P9-LLM-003:** Missing provider configuration MUST fail safely without a
  fabricated answer or secret disclosure.
- **REQ-P9-LLM-004:** Provider calls MUST enforce the approved timeout and expose
  controlled errors without credentials or raw secret-bearing diagnostics.
- **REQ-P9-LLM-005:** A successful smoke generation MUST return the typed neutral
  result without leaking provider internals.
- **REQ-P9-LLM-006:** Provider failures MUST remain distinguishable from valid
  generated content and MUST never be converted into invented user facts.

## Acceptance scenarios

| Given | When | Then |
|---|---|---|
| Valid non-secret configuration | A provider smoke test runs | A typed result is returned |
| Missing configuration | Generation is requested | A controlled failure is returned; no call with an empty secret |
| Provider timeout/error | Generation fails | The neutral error path is used; no fabricated answer |
| Agent invokes generation | A request is built | No database, retrieval, tool, or authorization work occurs in the provider |

Future verification: unit mocks, a separately enabled real DeepSeek smoke test,
and failure/secret-safety tests. No implementation starts in this baseline.
