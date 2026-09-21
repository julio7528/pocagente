"""Approved composition entry point for the initial LLM provider."""

from __future__ import annotations

from .config import load_deepseek_config
from .deepseek import DeepSeekProvider


def create_deepseek_provider() -> DeepSeekProvider:
    """Create the initial provider without introducing agent orchestration."""

    return DeepSeekProvider(load_deepseek_config())
