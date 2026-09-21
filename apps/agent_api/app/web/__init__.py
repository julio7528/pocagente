"""Provider-neutral controlled public web-search boundary."""

from .config import TavilyConfig, load_tavily_config
from .errors import (
    WebSearchConfigurationError,
    WebSearchError,
    WebSearchResponseError,
    WebSearchTimeoutError,
    WebSearchUnavailableError,
)
from .factory import create_tavily_web_search_provider
from .models import WebEvidence, WebSearchRequest, WebSearchResult, WebSearchStatus
from .tavily import TavilyWebSearchProvider

__all__ = [
    "TavilyConfig",
    "TavilyWebSearchProvider",
    "WebEvidence",
    "WebSearchConfigurationError",
    "WebSearchError",
    "WebSearchRequest",
    "WebSearchResponseError",
    "WebSearchResult",
    "WebSearchStatus",
    "WebSearchTimeoutError",
    "WebSearchUnavailableError",
    "load_tavily_config",
    "create_tavily_web_search_provider",
]
