# ruff: noqa: E402
from __future__ import annotations

import sys
import types
from functools import partial
from pathlib import Path

import pytest


def _install_optional_dependency_stubs() -> None:
    def install(name: str, attrs: dict[str, object]) -> None:
        if name in sys.modules:
            return
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[name] = module

    install(
        "faiss",
        {
            "read_index": lambda *args, **kwargs: None,
            "write_index": lambda *args, **kwargs: None,
            "IndexFlatL2": type("IndexFlatL2", (), {}),
            "IndexIDMap": type("IndexIDMap", (), {}),
            "normalize_L2": lambda *args, **kwargs: None,
        },
    )
    install("pypdf", {"PdfReader": type("PdfReader", (), {})})
    install(
        "jieba",
        {
            "cut": lambda text, *args, **kwargs: text.split(),
            "lcut": lambda text, *args, **kwargs: text.split(),
        },
    )
    install("rank_bm25", {"BM25Okapi": type("BM25Okapi", (), {})})


_install_optional_dependency_stubs()

from astrbot.core.message.components import Plain
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.pipeline.respond.stage import RespondStage
from astrbot.core.sdk_bridge.event_converter import EventConverter
from astrbot_sdk import MessageSession
from astrbot_sdk.events import MessageEvent
from astrbot_sdk.testing import MockContext


@pytest.mark.unit
def test_message_event_extensions_and_local_stop_control() -> None:
    event = MessageEvent.from_payload(
        {
            "text": "hello",
            "session_id": "test-platform:private:user-1",
            "platform": "test-platform",
            "platform_id": "test-platform-id",
            "message_type": "private",
            "self_id": "bot-1",
            "sender_name": "Tester",
            "is_admin": True,
        }
    )

    assert event.unified_msg_origin == "test-platform:private:user-1"
    assert event.get_session_id() == "test-platform:private:user-1"
    assert event.get_platform_id() == "test-platform-id"
    assert event.get_message_type() == "private"
    assert event.is_private_chat() is True
    assert event.is_admin() is True

    event.stop_event()
    assert event.is_stopped() is True
    event.continue_event()
    assert event.is_stopped() is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mock_context_system_tools_and_memory_stats() -> None:
    ctx = MockContext(plugin_id="sdk-demo")

    data_dir = await ctx.get_data_dir()
    assert isinstance(data_dir, Path)
    assert data_dir.name == "sdk-demo"

    image_result = await ctx.text_to_image("hello sdk")
    assert image_result == "mock://text_to_image/hello sdk"

    html_result = await ctx.html_render("card.html", {"title": "AstrBot"})
    assert html_result == "mock://html_render/card.html"

    await ctx.memory.save("profile", {"name": "AstrBot"})
    await ctx.memory.save_with_ttl("temp", {"value": "cached"}, 60)
    stats = await ctx.memory.stats()

    assert stats["total_items"] == 2
    assert stats["plugin_id"] == "sdk-demo"
    assert stats["ttl_entries"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_platform_client_accepts_message_session() -> None:
    ctx = MockContext(plugin_id="sdk-demo")
    session = MessageSession(
        platform_id="test-platform",
        message_type="private",
        session_id="user-42",
    )

    await ctx.platform.send(session, "hello session")

    assert len(ctx.sent_messages) == 1
    assert ctx.sent_messages[0].session_id == "test-platform:private:user-42"
    assert ctx.sent_messages[0].text == "hello session"


@pytest.mark.unit
def test_message_session_round_trip() -> None:
    session = MessageSession.from_str("demo-platform:group:room-7")

    assert session.platform_id == "demo-platform"
    assert session.message_type == "group"
    assert session.session_id == "room-7"
    assert str(session) == "demo-platform:group:room-7"


class _EventConverterProbe:
    def __init__(self) -> None:
        self.is_wake = False
        self.is_at_or_wake_command = False
        self.unified_msg_origin = "demo-platform:private:user-1"
        self._extras = {
            "serializable": {"value": 1},
            "callback": partial(str.upper, "demo"),
        }

    def get_message_type(self):
        return types.SimpleNamespace(value="private")

    def get_platform_id(self) -> str:
        return "demo-platform-id"

    def get_message_str(self) -> str:
        return "demo text"

    def get_sender_id(self) -> str:
        return "user-1"

    def get_group_id(self) -> str | None:
        return None

    def get_platform_name(self) -> str:
        return "demo-platform"

    def get_self_id(self) -> str:
        return "bot-1"

    def get_sender_name(self) -> str:
        return "Tester"

    def is_admin(self) -> bool:
        return False

    def get_message_outline(self) -> str:
        return "demo outline"

    def get_extra(self, key: str | None = None, default=None):
        if key is None:
            return self._extras
        return self._extras.get(key, default)

    def get_messages(self):
        return [Plain("demo", convert=False)]


@pytest.mark.unit
def test_event_converter_sanitizes_non_serializable_extras() -> None:
    payload = EventConverter.core_to_sdk(
        _EventConverterProbe(),
        dispatch_token="dispatch-1",
        plugin_id="sdk-demo",
        request_id="req-1",
    )

    assert payload["extras"] == {"serializable": {"value": 1}}
    assert "callback" not in payload["extras"]


@pytest.mark.unit
def test_respond_stage_sdk_outline_supports_list_and_message_chain() -> None:
    chain_list = [Plain("hello", convert=False), Plain(" world", convert=False)]

    assert RespondStage._message_outline_for_sdk_event(chain_list) == "hello  world"
    assert (
        RespondStage._message_outline_for_sdk_event(MessageChain(chain_list))
        == "hello  world"
    )
    assert RespondStage._message_outline_for_sdk_event(None) == ""
