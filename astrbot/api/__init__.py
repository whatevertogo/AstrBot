from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from astrbot import logger as logger
    from astrbot.core import html_renderer as html_renderer
    from astrbot.core import sp as sp
    from astrbot.core.agent.tool import FunctionTool, ToolSet
    from astrbot.core.agent.tool_executor import BaseFunctionToolExecutor
    from astrbot.core.config.astrbot_config import AstrBotConfig
    from astrbot.core.star.register import register_agent as agent
    from astrbot.core.star.register import register_llm_tool as llm_tool
else:
    AstrBotConfig: Any
    BaseFunctionToolExecutor: Any
    FunctionTool: Any
    ToolSet: Any
    agent: Any
    html_renderer: Any
    llm_tool: Any
    logger: Any
    sp: Any

__all__ = [
    "AstrBotConfig",
    "BaseFunctionToolExecutor",
    "FunctionTool",
    "ToolSet",
    "agent",
    "html_renderer",
    "llm_tool",
    "logger",
    "sp",
]


def __getattr__(name: str) -> Any:
    if name == "logger":
        return import_module("astrbot").logger
    if name in {"html_renderer", "sp"}:
        return getattr(import_module("astrbot.core"), name)
    if name in {"FunctionTool", "ToolSet"}:
        return getattr(import_module("astrbot.core.agent.tool"), name)
    if name == "BaseFunctionToolExecutor":
        return import_module(
            "astrbot.core.agent.tool_executor"
        ).BaseFunctionToolExecutor
    if name == "AstrBotConfig":
        return import_module("astrbot.core.config.astrbot_config").AstrBotConfig
    if name == "agent":
        return import_module("astrbot.core.star.register").register_agent
    if name == "llm_tool":
        return import_module("astrbot.core.star.register").register_llm_tool
    raise AttributeError(name)
