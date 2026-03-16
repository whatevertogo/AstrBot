"""AstrBot v4 协议公共入口。

这里暴露 v4 原生协议的消息模型、描述符和解析函数。

握手阶段由 `InitializeMessage` 发起，返回值不是另一条 initialize 消息，而是
`ResultMessage(kind="initialize_result")`，其 `output` 负载可解析为
`InitializeOutput`。
"""

from __future__ import annotations

from typing import Any

from . import _builtin_schemas as builtin_schemas
from .descriptors import (  # noqa: F401
    BUILTIN_CAPABILITY_SCHEMAS,
    CapabilityDescriptor,
    CommandRouteSpec,
    CommandTrigger,
    CompositeFilterSpec,
    EventTrigger,
    FilterSpec,
    HandlerDescriptor,
    LocalFilterRefSpec,
    MessageTrigger,
    MessageTypeFilterSpec,
    ParamSpec,
    Permissions,
    PlatformFilterSpec,
    ScheduleTrigger,
    SessionRef,
    Trigger,
)
from .messages import (  # noqa: F401
    CancelMessage,
    ErrorPayload,
    EventMessage,
    InitializeMessage,
    InitializeOutput,
    InvokeMessage,
    PeerInfo,
    ProtocolMessage,
    ResultMessage,
    parse_message,
)

_DIRECT_EXPORTS = [
    "BUILTIN_CAPABILITY_SCHEMAS",
    "CapabilityDescriptor",
    "CommandRouteSpec",
    "CommandTrigger",
    "CancelMessage",
    "builtin_schemas",
    "CompositeFilterSpec",
    "ErrorPayload",
    "EventTrigger",
    "EventMessage",
    "FilterSpec",
    "HandlerDescriptor",
    "InitializeMessage",
    "InitializeOutput",
    "InvokeMessage",
    "LocalFilterRefSpec",
    "MessageTrigger",
    "MessageTypeFilterSpec",
    "ParamSpec",
    "PeerInfo",
    "PlatformFilterSpec",
    "Permissions",
    "ProtocolMessage",
    "ResultMessage",
    "ScheduleTrigger",
    "SessionRef",
    "Trigger",
    "parse_message",
]

_BUILTIN_SCHEMA_EXPORTS = tuple(
    name for name in builtin_schemas.__all__ if name != "BUILTIN_CAPABILITY_SCHEMAS"
)


def __getattr__(name: str) -> Any:
    if name in _BUILTIN_SCHEMA_EXPORTS:
        return getattr(builtin_schemas, name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_BUILTIN_SCHEMA_EXPORTS))


__all__ = list(dict.fromkeys([*_DIRECT_EXPORTS, *_BUILTIN_SCHEMA_EXPORTS]))
