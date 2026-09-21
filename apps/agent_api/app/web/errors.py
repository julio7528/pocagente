"""Secret-safe controlled failures for public web search."""

from __future__ import annotations


class WebSearchError(Exception):
    """Base web-search failure without HTTP diagnostics or provider details."""

    error_code = "web_search_error"
    default_message = "The public web search provider could not complete the request."

    def __init__(self) -> None:
        super().__init__(self.default_message)


class WebSearchConfigurationError(WebSearchError):
    error_code = "web_search_configuration_unavailable"
    default_message = "Public web search configuration is unavailable."


class WebSearchUnavailableError(WebSearchError):
    error_code = "web_search_unavailable"
    default_message = "Public web search is temporarily unavailable."


class WebSearchTimeoutError(WebSearchError):
    error_code = "web_search_timeout"
    default_message = "Public web search timed out."


class WebSearchResponseError(WebSearchError):
    error_code = "web_search_invalid_response"
    default_message = "Public web search returned an invalid response."
