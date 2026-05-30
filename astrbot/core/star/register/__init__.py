from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .star import register_star
    from .star_handler import (
        register_after_message_sent,
        register_agent,
        register_command,
        register_command_group,
        register_custom_filter,
        register_event_message_type,
        register_llm_tool,
        register_on_agent_begin,
        register_on_agent_done,
        register_on_astrbot_loaded,
        register_on_decorating_result,
        register_on_llm_request,
        register_on_llm_response,
        register_on_llm_tool_respond,
        register_on_platform_loaded,
        register_on_plugin_error,
        register_on_plugin_loaded,
        register_on_plugin_unloaded,
        register_on_using_llm_tool,
        register_on_waiting_llm_request,
        register_permission_type,
        register_platform_adapter_type,
        register_regex,
    )
else:
    register_after_message_sent: Any
    register_agent: Any
    register_command: Any
    register_command_group: Any
    register_custom_filter: Any
    register_event_message_type: Any
    register_llm_tool: Any
    register_on_agent_begin: Any
    register_on_agent_done: Any
    register_on_astrbot_loaded: Any
    register_on_decorating_result: Any
    register_on_llm_request: Any
    register_on_llm_response: Any
    register_on_llm_tool_respond: Any
    register_on_platform_loaded: Any
    register_on_plugin_error: Any
    register_on_plugin_loaded: Any
    register_on_plugin_unloaded: Any
    register_on_using_llm_tool: Any
    register_on_waiting_llm_request: Any
    register_permission_type: Any
    register_platform_adapter_type: Any
    register_regex: Any
    register_star: Any

__all__ = [
    "register_after_message_sent",
    "register_agent",
    "register_command",
    "register_command_group",
    "register_custom_filter",
    "register_event_message_type",
    "register_llm_tool",
    "register_on_agent_begin",
    "register_on_agent_done",
    "register_on_astrbot_loaded",
    "register_on_decorating_result",
    "register_on_llm_request",
    "register_on_llm_response",
    "register_on_plugin_error",
    "register_on_plugin_loaded",
    "register_on_plugin_unloaded",
    "register_on_platform_loaded",
    "register_on_waiting_llm_request",
    "register_permission_type",
    "register_platform_adapter_type",
    "register_regex",
    "register_star",
    "register_on_using_llm_tool",
    "register_on_llm_tool_respond",
]


def __getattr__(name: str) -> Any:
    if name == "register_star":
        return import_module(".star", __name__).register_star
    if name in __all__:
        return getattr(import_module(".star_handler", __name__), name)
    raise AttributeError(name)
