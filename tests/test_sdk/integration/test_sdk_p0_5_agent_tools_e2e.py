# ruff: noqa: E402
from __future__ import annotations

import shutil
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

from astrbot.core.message.components import Plain
from astrbot.core.platform.message_type import MessageType
from astrbot.core.provider.entities import LLMResponse as CoreLLMResponse
from astrbot.core.provider.entities import ProviderMeta as CoreProviderMeta
from astrbot.core.provider.entities import ProviderType as CoreProviderType
from astrbot.core.provider.entities import TokenUsage
from astrbot.core.sdk_bridge import plugin_bridge as plugin_bridge_module
from astrbot.core.sdk_bridge.plugin_bridge import SdkPluginBridge


class _FakeProvider:
    def __init__(
        self,
        provider_id: str,
        provider_type: CoreProviderType,
        *,
        adapter_type: str,
        model: str,
    ) -> None:
        self._meta = CoreProviderMeta(
            id=provider_id,
            model=model,
            type=adapter_type,
            provider_type=provider_type,
        )

    def meta(self) -> CoreProviderMeta:
        return self._meta


class _FakeStarContext:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []
        self.sdk_plugin_bridge = None
        self.registered_web_apis = []
        self.chat_provider = _FakeProvider(
            "chat-provider-1",
            CoreProviderType.CHAT_COMPLETION,
            adapter_type="mock-chat",
            model="gpt-test",
        )
        self.tts_provider = _FakeProvider(
            "tts-provider-1",
            CoreProviderType.TEXT_TO_SPEECH,
            adapter_type="mock-tts",
            model="tts-test",
        )
        self.stt_provider = _FakeProvider(
            "stt-provider-1",
            CoreProviderType.SPEECH_TO_TEXT,
            adapter_type="mock-stt",
            model="stt-test",
        )
        self.embedding_provider = _FakeProvider(
            "embedding-provider-1",
            CoreProviderType.EMBEDDING,
            adapter_type="mock-embedding",
            model="embedding-test",
        )
        self.tool_loop_calls: list[dict[str, object]] = []

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
        return self.chat_provider

    def get_all_providers(self) -> list:
        return [self.chat_provider]

    def get_all_tts_providers(self) -> list:
        return [self.tts_provider]

    def get_all_stt_providers(self) -> list:
        return [self.stt_provider]

    def get_all_embedding_providers(self) -> list:
        return [self.embedding_provider]

    def get_using_tts_provider(self, umo: str | None = None):
        return self.tts_provider

    def get_using_stt_provider(self, umo: str | None = None):
        return self.stt_provider

    async def tool_loop_agent(
        self,
        *,
        event,
        chat_provider_id: str,
        prompt: str | None = None,
        image_urls=None,
        tools=None,
        system_prompt: str = "",
        contexts=None,
        max_steps: int = 30,
        tool_call_timeout: int = 60,
        **kwargs,
    ):
        tool_name = None
        tool_output = None
        if tools is not None and not tools.empty():
            tool = next(iter(tools))
            tool_name = tool.name
            if tool.handler is not None:
                tool_output = await tool.handler(event, query=prompt or "")
        self.tool_loop_calls.append(
            {
                "chat_provider_id": chat_provider_id,
                "prompt": prompt or "",
                "tool_name": tool_name,
                "tool_output": tool_output,
                "tool_call_timeout": tool_call_timeout,
                "max_steps": max_steps,
                "system_prompt": system_prompt,
                "contexts": list(contexts or []),
                "image_urls": list(image_urls or []),
            }
        )
        final_text = str(tool_output or f"fallback:{prompt or ''}")
        return CoreLLMResponse(
            role="assistant",
            completion_text=final_text,
            usage=TokenUsage(input_other=len(prompt or ""), output=len(final_text)),
        )


class _FakeEvent:
    def __init__(self, text: str) -> None:
        self._text = text
        self._stopped = False
        self._has_send_oper = False
        self._messages = [Plain(text, convert=False)]
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
async def test_sdk_p0_5_agent_tools_plugin_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    temp_data_dir = tmp_path / "data"
    sdk_plugins_dir = temp_data_dir / "sdk_plugins"
    sdk_plugins_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        Path("data/sdk_plugins/sdk_demo_agent_tools"),
        sdk_plugins_dir / "sdk_demo_agent_tools",
    )

    fake_context = _FakeStarContext()

    monkeypatch.setattr(
        plugin_bridge_module,
        "get_astrbot_data_path",
        lambda: str(temp_data_dir),
    )

    bridge = SdkPluginBridge(fake_context)
    bridge.env_manager.plan = lambda plugins: None
    bridge.env_manager.prepare_environment = lambda plugin: Path(sys.executable)
    fake_context.sdk_plugin_bridge = bridge

    await bridge.start()
    try:
        plugins = bridge.list_plugins()
        assert [plugin["name"] for plugin in plugins] == ["sdk_demo_agent_tools"]
        record = bridge._records["sdk_demo_agent_tools"]
        assert sorted(record.llm_tools.keys()) == ["sdk_static_note"]
        assert sorted(record.agents.keys()) == ["sdk_demo_note_agent"]

        providers = await bridge.dispatch_message(_FakeEvent("sdkproviders"))
        assert providers.sent_message is True
        assert (
            fake_context.sent_messages[-1]["text"]
            == "current=chat-provider-1 | current_id=chat-provider-1 | chat=1 | tts=1 | stt=1 | embedding=1"
        )

        tool_state = await bridge.dispatch_message(_FakeEvent("sdktoolstate"))
        assert tool_state.sent_message is True
        assert (
            fake_context.sent_messages[-1]["text"]
            == "registered=sdk_static_note active=sdk_static_note"
        )

        tool_loop = await bridge.dispatch_message(_FakeEvent("sdktoolloop hello"))
        assert tool_loop.sent_message is True
        assert (
            fake_context.sent_messages[-1]["text"]
            == "sdk_demo_agent_tools:test-platform:friend:local-session:hello"
        )
        assert fake_context.tool_loop_calls[-1]["tool_name"] == "sdk_static_note"
        assert fake_context.tool_loop_calls[-1]["tool_output"] == (
            "sdk_demo_agent_tools:test-platform:friend:local-session:hello"
        )

        tool_add = await bridge.dispatch_message(_FakeEvent("sdktooladd"))
        assert tool_add.sent_message is True
        assert fake_context.sent_messages[-1]["text"] == "added=sdk_dynamic_note"

        dynamic_state = await bridge.dispatch_message(_FakeEvent("sdktoolstate"))
        assert dynamic_state.sent_message is True
        assert (
            fake_context.sent_messages[-1]["text"]
            == "registered=sdk_dynamic_note,sdk_static_note active=sdk_dynamic_note,sdk_static_note"
        )

        dynamic_loop = await bridge.dispatch_message(_FakeEvent("sdkdynamicloop world"))
        assert dynamic_loop.sent_message is True
        assert fake_context.sent_messages[-1]["text"] == "dynamic:world"
        assert fake_context.tool_loop_calls[-1]["tool_name"] == "sdk_dynamic_note"
        assert fake_context.tool_loop_calls[-1]["tool_output"] == "dynamic:world"

        disable = await bridge.dispatch_message(_FakeEvent("sdktooldisable"))
        assert disable.sent_message is True
        assert fake_context.sent_messages[-1]["text"] == "deactivated=True"
        assert record.active_llm_tools == {"sdk_dynamic_note"}

        enable = await bridge.dispatch_message(_FakeEvent("sdktoolenable"))
        assert enable.sent_message is True
        assert fake_context.sent_messages[-1]["text"] == "activated=True"
        assert record.active_llm_tools == {"sdk_dynamic_note", "sdk_static_note"}
    finally:
        await bridge.stop()
