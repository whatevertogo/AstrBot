"""事件转换器。

实现 AstrMessageEvent (Core) 与 SDK payload 之间的双向转换。

转换映射：
- AstrMessageEvent.message_str → payload.text
- AstrMessageEvent.get_sender_id() → payload.user_id
- AstrMessageEvent.get_group_id() → payload.group_id
- AstrMessageEvent.get_platform_name() → payload.platform
- AstrMessageEvent.unified_msg_origin → payload.session_id
- AstrMessageEvent.is_admin() → payload.is_admin
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from astrbot.core.platform.astr_message_event import AstrMessageEvent


class EventConverter:
    """Core 与 SDK 事件双向转换器。"""

    @staticmethod
    def core_to_sdk(event: "AstrMessageEvent") -> dict[str, Any]:
        """将 Core 的 AstrMessageEvent 转换为 SDK MessageEvent payload。

        Args:
            event: Core 的消息事件对象

        Returns:
            SDK MessageEvent 可用的 payload 字典
        """
        # 获取消息类型信息
        message_type = event.get_message_type()
        is_group = message_type.name not in (
            "FRIEND_MESSAGE",
            "GROUP_MESSAGE",
        ) or message_type.name == "GROUP_MESSAGE"

        # 构建基础 payload
        payload: dict[str, Any] = {
            # 基础字段
            "text": event.message_str,
            "user_id": event.get_sender_id(),
            "group_id": event.get_group_id() if is_group else None,
            "platform": event.get_platform_name(),
            "session_id": event.unified_msg_origin,
            # 扩展字段
            "is_admin": event.is_admin(),
            "is_wake": event.is_wake,
            "is_at_or_wake_command": event.is_at_or_wake_command,
            "message_type": message_type.name if message_type else None,
            "sender_name": event.get_sender_name(),
            "platform_id": event.get_platform_id(),
            # 保留原始消息对象的引用（用于需要访问完整消息链的场景）
            "_raw_event": event,
            # 消息链概要
            "message_outline": event.get_message_outline(),
        }

        # 添加 extras
        extras = event.get_extra()
        if extras:
            payload["_extras"] = extras

        # 添加 target 信息（SDK 的 SessionRef 格式）
        payload["target"] = {
            "conversation_id": event.unified_msg_origin,
            "platform": event.get_platform_name(),
        }

        return payload

    @staticmethod
    def sdk_to_core_payload(event: "AstrMessageEvent", result: dict[str, Any]) -> dict[str, Any]:
        """将 SDK handler 返回的结果转换为 Core 可用的格式。

        SDK handler 可能返回：
        - {"text": "回复内容"} - 纯文本回复
        - {"chain": [...]} - 消息链
        - {"stop": True} - 停止事件传播

        Args:
            event: 原始 Core 事件（用于构建回复目标）
            result: SDK handler 返回的结果

        Returns:
            Core 可用的回复数据
        """
        # 如果结果为空，返回空字典
        if not result:
            return {}

        # 提取文本回复
        text = result.get("text", "")

        # 提取消息链（如果有）
        chain = result.get("chain")

        # 提取停止标志
        stop = result.get("stop", False)

        return {
            "text": text,
            "chain": chain,
            "stop": stop,
            "session": event.unified_msg_origin,
        }

    @staticmethod
    def extract_handler_result(sdk_result: dict[str, Any] | None) -> dict[str, Any]:
        """从 SDK handler 执行结果中提取有效信息。

        Args:
            sdk_result: SDK handler 返回的结果

        Returns:
            标准化的结果字典，包含：
            - text: 回复文本
            - stop: 是否停止事件传播
            - call_llm: 是否调用 LLM
        """
        if not sdk_result:
            return {"text": "", "stop": False, "call_llm": False}

        return {
            "text": sdk_result.get("text", ""),
            "stop": sdk_result.get("stop", False),
            "call_llm": sdk_result.get("call_llm", False),
        }
