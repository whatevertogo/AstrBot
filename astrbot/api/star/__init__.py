from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from astrbot.core.star import Context, Star, StarTools
    from astrbot.core.star.config import load_config, put_config, update_config
    from astrbot.core.star.register import register_star as register
else:
    Context: Any
    Star: Any
    StarTools: Any
    load_config: Any
    put_config: Any
    register: Any
    update_config: Any

__all__ = [
    "Context",
    "Star",
    "StarTools",
    "load_config",
    "put_config",
    "register",
    "update_config",
]


def __getattr__(name: str) -> Any:
    if name in {"Context", "Star", "StarTools"}:
        return getattr(import_module("astrbot.core.star"), name)
    if name == "register":
        return import_module("astrbot.core.star.register").register_star
    if name in {"load_config", "put_config", "update_config"}:
        return getattr(import_module("astrbot.core.star.config"), name)
    raise AttributeError(name)
