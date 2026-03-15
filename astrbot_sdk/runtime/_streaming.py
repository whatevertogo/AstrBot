"""Shared stream execution primitives for runtime internals."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class StreamExecution:
    iterator: AsyncIterator[dict[str, Any]]
    finalize: Callable[[list[dict[str, Any]]], dict[str, Any]]
    collect_chunks: bool = True


__all__ = ["StreamExecution"]
