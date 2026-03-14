# ruff: noqa: E402
from __future__ import annotations

import shutil
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

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
    install("aiocqhttp", {"CQHttp": MagicMock, "Event": MagicMock})
    install("aiocqhttp.exceptions", {"ActionFailed": Exception})
    install("telegram", {"Bot": MagicMock, "Update": MagicMock})
    install(
        "telegram.constants",
        {
            "ParseMode": type(
                "ParseMode",
                (),
                {"HTML": "HTML", "MARKDOWN_V2": "MARKDOWN_V2"},
            )
        },
    )
    install("telegram.error", {"TelegramError": Exception})
    install(
        "telegram.ext",
        {
            "Application": MagicMock,
            "ApplicationBuilder": MagicMock,
            "ContextTypes": MagicMock,
            "MessageHandler": MagicMock,
            "filters": MagicMock(),
            "CommandHandler": MagicMock,
            "CallbackQueryHandler": MagicMock,
        },
    )
    install(
        "discord",
        {
            "Client": MagicMock,
            "Intents": MagicMock,
            "Message": MagicMock,
            "Attachment": MagicMock,
            "File": MagicMock,
            "Embed": MagicMock,
        },
    )
    install("discord.ext", {})
    install(
        "discord.ext.commands",
        {
            "Bot": MagicMock,
            "Cog": MagicMock,
            "Context": MagicMock,
            "command": lambda *args, **kwargs: lambda func: func,
        },
    )


_install_optional_dependency_stubs()

from astrbot.core.platform.message_type import MessageType
from astrbot.core.sdk_bridge import capability_bridge as capability_bridge_module
from astrbot.core.sdk_bridge import plugin_bridge as plugin_bridge_module
from astrbot.core.sdk_bridge.plugin_bridge import SdkPluginBridge


class _FakeSharedPreferences:
    def __init__(self) -> None:
        self._values: dict[tuple[str, str, str], object] = {}

    async def get_async(
        self,
        scope: str,
        scope_id: str,
        key: str,
        default=None,
    ):
        return self._values.get((scope, scope_id, key), default)

    async def put_async(
        self,
        scope: str,
        scope_id: str,
        key: str,
        value,
    ) -> None:
        self._values[(scope, scope_id, key)] = value

    async def remove_async(self, scope: str, scope_id: str, key: str) -> None:
        self._values.pop((scope, scope_id, key), None)

    async def range_get_async(
        self,
        scope: str,
        scope_id: str | None = None,
        key: str | None = None,
    ) -> list[SimpleNamespace]:
        items: list[SimpleNamespace] = []
        for (item_scope, item_scope_id, item_key), value in self._values.items():
            if item_scope != scope:
                continue
            if scope_id is not None and item_scope_id != scope_id:
                continue
            if key is not None and item_key != key:
                continue
            items.append(SimpleNamespace(key=item_key, value={"val": value}))
        return items


class _FakeStarContext:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []

    async def send_message(self, session: str, message_chain) -> None:
        self.sent_messages.append(
            {
                "session": session,
                "message_chain": message_chain,
                "text": message_chain.get_plain_text(),
            }
        )

    def get_all_stars(self) -> list:
        return []

    def get_using_provider(self, umo: str | None = None):
        return None


class _FakeEvent:
    def __init__(self, text: str) -> None:
        self._text = text
        self._stopped = False
        self._extras: dict[str, object] = {}
        self._has_send_oper = False
        self.call_llm = False
        self.is_wake = True
        self.is_at_or_wake_command = True
        self.unified_msg_origin = "test-platform:friend:local-session"

    def get_message_type(self) -> MessageType:
        return MessageType.FRIEND_MESSAGE

    def get_group_id(self) -> str:
        return ""

    def get_sender_id(self) -> str:
        return "user-1"

    def get_platform_name(self) -> str:
        return "test-platform"

    def get_platform_id(self) -> str:
        return "test-platform-id"

    def get_message_str(self) -> str:
        return self._text

    def get_sender_name(self) -> str:
        return "SDK Tester"

    def is_admin(self) -> bool:
        return False

    def get_message_outline(self) -> str:
        return self._text

    def get_extra(self, key: str | None = None, default=None):
        if key is None:
            return self._extras
        return self._extras.get(key, default)

    def is_stopped(self) -> bool:
        return self._stopped

    def stop_event(self) -> None:
        self._stopped = True

    def should_call_llm(self, call_llm: bool) -> None:
        self.call_llm = call_llm

    async def get_group(self):
        return None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sdk_bridge_dispatches_demo_plugin_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    temp_data_dir = tmp_path / "data"
    sdk_plugins_dir = temp_data_dir / "sdk_plugins"
    sdk_plugins_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        Path("data/sdk_plugins/sdk_demo_echo"),
        sdk_plugins_dir / "sdk_demo_echo",
    )

    fake_sp = _FakeSharedPreferences()
    fake_context = _FakeStarContext()

    monkeypatch.setattr(
        plugin_bridge_module,
        "get_astrbot_data_path",
        lambda: str(temp_data_dir),
    )
    monkeypatch.setattr(capability_bridge_module, "sp", fake_sp)

    bridge = SdkPluginBridge(fake_context)
    bridge.env_manager.prepare_environment = lambda plugin: Path(sys.executable)

    await bridge.start()
    try:
        plugins = bridge.list_plugins()
        assert [plugin["name"] for plugin in plugins] == ["sdk_demo_echo"]
        assert plugins[0]["runtime_kind"] == "sdk"
        assert plugins[0]["state"] == "enabled"

        hello_event = _FakeEvent("sdkhello")
        hello_result = await bridge.dispatch_message(hello_event)
        assert hello_result.sent_message is True
        assert hello_result.stopped is False
        assert hello_result.skipped_reason is None
        assert hello_result.executed_handlers[0]["plugin_id"] == "sdk_demo_echo"
        assert hello_result.executed_handlers[0]["handler_id"].endswith("sdkhello")
        assert hello_event._has_send_oper is True
        assert hello_event.call_llm is True
        assert (
            fake_context.sent_messages[-1]["session"] == hello_event.unified_msg_origin
        )
        assert (
            fake_context.sent_messages[-1]["text"]
            == "hello from sdk, session=test-platform:friend:local-session, plugin=sdk_demo_echo"
        )

        count_event_1 = _FakeEvent("sdkcount")
        count_result_1 = await bridge.dispatch_message(count_event_1)
        assert count_result_1.sent_message is True
        assert count_result_1.executed_handlers[0]["handler_id"].endswith("sdkcount")
        assert fake_context.sent_messages[-1]["text"] == "sdk count = 1"

        count_event_2 = _FakeEvent("sdkcount")
        count_result_2 = await bridge.dispatch_message(count_event_2)
        assert count_result_2.sent_message is True
        assert fake_context.sent_messages[-1]["text"] == "sdk count = 2"

        keyword_event = _FakeEvent("please sdk ping now")
        keyword_result = await bridge.dispatch_message(keyword_event)
        assert keyword_result.sent_message is True
        assert keyword_result.executed_handlers[0]["handler_id"].endswith("sdk_ping")
        assert fake_context.sent_messages[-1]["text"] == "sdk pong: please sdk ping now"

        await bridge.turn_off_plugin("sdk_demo_echo")
        plugins = bridge.list_plugins()
        assert plugins[0]["state"] == "disabled"
        assert plugins[0]["activated"] is False

        disabled_event = _FakeEvent("sdkhello")
        disabled_result = await bridge.dispatch_message(disabled_event)
        assert disabled_result.sent_message is False
        assert disabled_result.executed_handlers == []
        assert disabled_result.skipped_reason == "no_match"

        await bridge.turn_on_plugin("sdk_demo_echo")
        plugins = bridge.list_plugins()
        assert plugins[0]["state"] == "enabled"
        assert plugins[0]["activated"] is True

        reenabled_event = _FakeEvent("sdkhello")
        reenabled_result = await bridge.dispatch_message(reenabled_event)
        assert reenabled_result.sent_message is True
        assert reenabled_result.executed_handlers[0]["handler_id"].endswith("sdkhello")
    finally:
        await bridge.stop()
