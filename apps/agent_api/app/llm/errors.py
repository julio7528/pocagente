"""Secret-safe LLM provider failures."""

from __future__ import annotations


class LLMProviderError(Exception):
    """Base controlled provider failure that intentionally omits driver details."""

    error_code = "llm_provider_error"
    default_message = "The language model provider could not complete the request."

    def __init__(self) -> None:
        super().__init__(self.default_message)


class LLMConfigurationError(LLMProviderError):
    """Required provider runtime configuration is absent or invalid."""

    error_code = "llm_configuration_unavailable"
    default_message = "Language model provider configuration is unavailable."


class LLMProviderUnavailableError(LLMProviderError):
    """The provider could not be reached or rejected the request."""

    error_code = "llm_provider_unavailable"
    default_message = "The language model provider is temporarily unavailable."


class LLMProviderTimeoutError(LLMProviderError):
    """The provider did not respond before the approved timeout."""

    error_code = "llm_provider_timeout"
    default_message = "The language model provider request timed out."


class LLMProviderResponseError(LLMProviderError):
    """The provider returned a response that cannot meet the neutral contract."""

    error_code = "llm_provider_invalid_response"
    default_message = "The language model provider returned an invalid response."
