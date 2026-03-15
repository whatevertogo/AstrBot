# ruff: noqa: E402
from __future__ import annotations

import shutil
import sys
import types
import uuid
from pathlib import Path
from types import SimpleNamespace

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
from astrbot.core.platform.message_type import MessageType
from astrbot.core.sdk_bridge import plugin_bridge as plugin_bridge_module
from astrbot.core.sdk_bridge.plugin_bridge import SdkPluginBridge


class _FakeCronManager:
    def __init__(self) -> None:
        self.jobs: dict[str, object] = {}

    async def add_basic_job(self, **kwargs):
        job_id = f"sdk-cron-{uuid.uuid4().hex}"
        self.jobs[job_id] = kwargs["handler"]
        return SimpleNamespace(job_id=job_id)

    async def delete_job(self, job_id: str) -> None:
        self.jobs.pop(job_id, None)


class _FakeSharedPreferences:
    def __init__(self) -> None:
        self._values: dict[tuple[str, str, str], object] = {}

    async def get_async(self, scope: str, scope_id: str, key: str, default=None):
        return self._values.get((scope, scope_id, key), default)

    async def put_async(self, scope: str, scope_id: str, key: str, value) -> None:
        self._values[(scope, scope_id, key)] = value

    async def remove_async(self, scope: str, scope_id: str, key: str) -> None:
        self._values.pop((scope, scope_id, key), None)

    async def range_get_async(
        self, scope: str, scope_id: str | None = None, key: str | None = None
    ):
        return []


class _FakeStarContext:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []
        self.sdk_plugin_bridge = None
        self.registered_web_apis = []
        self.cron_manager = _FakeCronManager()

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
    def __init__(self, text: str, *, message_type: str = "private") -> None:
        self._text = text
        self._message_type = message_type
        self._stopped = False
        self._has_send_oper = False
        self._messages = [Plain(text, convert=False)]
        self.call_llm = False
        self.is_wake = True
        self.is_at_or_wake_command = True
        self.unified_msg_origin = "test-platform:friend:local-session"

    def get_message_type(self) -> MessageType:
        if self._message_type == "group":
            return MessageType.GROUP_MESSAGE
        return MessageType.FRIEND_MESSAGE

    def get_group_id(self) -> str:
        return "group-1" if self._message_type == "group" else ""

    def get_sender_id(self) -> str:
        return "user-1"

    def get_platform_name(self) -> str:
        return "test-platform"

    def get_platform_id(self) -> str:
        return "test-platform"

    def get_self_id(self) -> str:
        return "bot-self"

    def get_message_str(self) -> str:
        return self._text

    def get_sender_name(self) -> str:
        return "SDK Tester"

    def get_message_outline(self) -> str:
        return self._text

    def get_messages(self):
        return list(self._messages)

    def get_extra(self, key=None, default=None):
        return {} if key is None else default

    def is_admin(self) -> bool:
        return False

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
async def test_sdk_p0_3_routing_plugin_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    temp_data_dir = tmp_path / "data"
    sdk_plugins_dir = temp_data_dir / "sdk_plugins"
    sdk_plugins_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        Path("data/sdk_plugins/sdk_demo_routing"),
        sdk_plugins_dir / "sdk_demo_routing",
    )

    fake_sp = _FakeSharedPreferences()
    fake_context = _FakeStarContext()

    monkeypatch.setattr(
        plugin_bridge_module,
        "get_astrbot_data_path",
        lambda: str(temp_data_dir),
    )

    bridge = SdkPluginBridge(fake_context)
    capability_bridge_module = sys.modules[
        bridge.capability_bridge.__class__.__module__
    ]
    monkeypatch.setattr(capability_bridge_module, "_get_runtime_sp", lambda: fake_sp)
    bridge.env_manager.plan = lambda plugins: None
    bridge.env_manager.prepare_environment = lambda plugin: Path(sys.executable)

    await bridge.start()
    try:
        plugins = bridge.list_plugins()
        assert [plugin["name"] for plugin in plugins] == ["sdk_demo_routing"]

        alias_event = _FakeEvent("sdkalias")
        alias_result = await bridge.dispatch_message(alias_event)
        assert alias_result.sent_message is True
        assert fake_context.sent_messages[-1]["text"] == "sdk alias ok"

        group_miss = await bridge.dispatch_message(_FakeEvent("sdkgroup"))
        assert group_miss.sent_message is False
        assert group_miss.skipped_reason == "no_match"

        group_hit = await bridge.dispatch_message(
            _FakeEvent("sdkgroup", message_type="group")
        )
        assert group_hit.sent_message is True
        assert fake_context.sent_messages[-1]["text"] == "sdk group only"

        filtered_miss = await bridge.dispatch_message(_FakeEvent("sdkfilter blocked"))
        assert filtered_miss.sent_message is False
        assert filtered_miss.executed_handlers

        filtered_hit = await bridge.dispatch_message(_FakeEvent("sdkfilter pass"))
        assert filtered_hit.sent_message is True
        assert fake_context.sent_messages[-1]["text"] == "sdk custom filter pass"

        group_command = await bridge.dispatch_message(_FakeEvent("sdka say hello sdk"))
        assert group_command.sent_message is True
        assert fake_context.sent_messages[-1]["text"] == "sdk group echo: hello sdk"

        typed = await bridge.dispatch_message(_FakeEvent("sdkbool yes 3"))
        assert typed.sent_message is True
        assert fake_context.sent_messages[-1]["text"] == "enabled=True amount=3"

        assert len(fake_context.cron_manager.jobs) == 1
        job_handler = next(iter(fake_context.cron_manager.jobs.values()))
        await job_handler()

        scheduled = await bridge.dispatch_message(_FakeEvent("sdkschedulecount"))
        assert scheduled.sent_message is True
        assert fake_context.sent_messages[-1]["text"] == "schedule_count=1"

        await bridge.reload_plugin("sdk_demo_routing")
        assert len(fake_context.cron_manager.jobs) == 1

        await bridge.turn_off_plugin("sdk_demo_routing")
        assert fake_context.cron_manager.jobs == {}
    finally:
        await bridge.stop()
