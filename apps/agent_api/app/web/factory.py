"""Composition for the initial Tavily adapter without coupling higher layers to it."""

from __future__ import annotations

from .config import load_tavily_config
from .tavily import TavilyWebSearchProvider


def create_tavily_web_search_provider() -> TavilyWebSearchProvider:
    """Compose only the concrete adapter from validated local runtime configuration."""

    return TavilyWebSearchProvider(load_tavily_config())
