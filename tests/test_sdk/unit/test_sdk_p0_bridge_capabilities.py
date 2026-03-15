# ruff: noqa: E402
from __future__ import annotations

import sys
import types
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
