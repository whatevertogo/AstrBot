"""SDK parameter helper types."""

from __future__ import annotations


class GreedyStr(str):
    """Consume the remaining command text as one argument."""


__all__ = ["GreedyStr"]
