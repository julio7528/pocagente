"""Small runtime helpers for local real-database integration tests."""

from __future__ import annotations

import asyncio
import selectors
from collections.abc import Coroutine
from typing import Any, TypeVar


_ResultT = TypeVar("_ResultT")


def run_async(coroutine: Coroutine[Any, Any, _ResultT]) -> _ResultT:
    """Run Psycopg async work on its required Windows-compatible event loop."""

    return asyncio.run(
        coroutine,
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )
