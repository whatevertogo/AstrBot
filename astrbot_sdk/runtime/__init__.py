"""AstrBot SDK runtime public exports.

Keep runtime imports lazy so submodule users do not pay the websocket/aiohttp import
cost unless they actually need transport primitives.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .capability_router import CapabilityRouter, StreamExecution
    from .handler_dispatcher import HandlerDispatcher
    from .peer import Peer
    from .transport import (
        MessageHandler,
        StdioTransport,
        Transport,
        WebSocketClientTransport,
        WebSocketServerTransport,
    )

__all__ = [
    "CapabilityRouter",
    "HandlerDispatcher",
    "MessageHandler",
    "Peer",
    "StdioTransport",
    "StreamExecution",
    "Transport",
    "WebSocketClientTransport",
    "WebSocketServerTransport",
]


def __getattr__(name: str) -> Any:
    if name in {"CapabilityRouter", "StreamExecution"}:
        module = import_module(".capability_router", __name__)
        return getattr(module, name)
    if name == "HandlerDispatcher":
        module = import_module(".handler_dispatcher", __name__)
        return getattr(module, name)
    if name == "Peer":
        module = import_module(".peer", __name__)
        return getattr(module, name)
    if name in {
        "MessageHandler",
        "StdioTransport",
        "Transport",
        "WebSocketClientTransport",
        "WebSocketServerTransport",
    }:
        module = import_module(".transport", __name__)
        return getattr(module, name)
    raise AttributeError(name)
