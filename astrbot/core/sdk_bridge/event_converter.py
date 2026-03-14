from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from astrbot.core.platform.astr_message_event import AstrMessageEvent


class EventConverter:
    """Convert legacy AstrBot events into SDK payloads."""

    @staticmethod
    def core_to_sdk(
        event: AstrMessageEvent,
        *,
        dispatch_token: str,
        plugin_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        message_type = event.get_message_type()
        raw = {
            "dispatch_token": dispatch_token,
            "plugin_id": plugin_id,
            "request_id": request_id,
            "platform_id": event.get_platform_id(),
        }
        payload: dict[str, Any] = {
            "text": event.get_message_str(),
            "user_id": event.get_sender_id(),
            "group_id": event.get_group_id() or None,
            "platform": event.get_platform_name(),
            "platform_id": event.get_platform_id(),
            "session_id": event.unified_msg_origin,
            "message_type": getattr(message_type, "value", None),
            "sender_name": event.get_sender_name(),
            "is_admin": event.is_admin(),
            "is_wake": event.is_wake,
            "is_at_or_wake_command": event.is_at_or_wake_command,
            "message_outline": event.get_message_outline(),
            "raw": raw,
            "target": {
                "conversation_id": event.unified_msg_origin,
                "platform": event.get_platform_name(),
                "raw": raw,
            },
        }
        extras = event.get_extra()
        if isinstance(extras, dict) and extras:
            payload["extras"] = dict(extras)
        return payload

    @staticmethod
    def extract_handler_result(sdk_result: dict[str, Any] | None) -> dict[str, Any]:
        if not sdk_result:
            return {"sent_message": False, "stop": False, "call_llm": False}
        return {
            "sent_message": bool(sdk_result.get("sent_message", False)),
            "stop": bool(sdk_result.get("stop", False)),
            "call_llm": bool(sdk_result.get("call_llm", False)),
        }
