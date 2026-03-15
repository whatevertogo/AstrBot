# ruff: noqa: E402
from __future__ import annotations

import json
import shutil
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from quart import Quart, jsonify, request
from quart import Response as QuartResponse


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

from astrbot.core.message.components import Plain
from astrbot.core.platform.message_type import MessageType
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
        self.sdk_plugin_bridge = None
        self.registered_web_apis: list[tuple[str, object, list[str], str]] = []

    async def send_message(self, session: str, message_chain) -> None:
        self.sent_messages.append(
            {
                "session": session,
                "message_chain": message_chain,
                "text": message_chain.get_plain_text(),
            }
        )
        if self.sdk_plugin_bridge is not None:
            session_parts = session.split(":", 2)
            await self.sdk_plugin_bridge.dispatch_system_event(
                "after_message_sent",
                {
                    "session_id": session,
                    "platform": session_parts[0] if len(session_parts) == 3 else "",
                    "platform_id": session_parts[0] if len(session_parts) == 3 else "",
                    "message_type": session_parts[1] if len(session_parts) == 3 else "",
                    "message_outline": message_chain.get_plain_text(
                        with_other_comps_mark=True
                    ),
                },
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
        self._messages = [Plain(text, convert=False)]
        self.call_llm = False
        self.is_wake = True
        self.is_at_or_wake_command = True
        self.unified_msg_origin = "test-platform:friend:local-session"
        self.reactions: list[str] = []
        self.typing_calls = 0
        self.streaming_chunks: list[str] = []

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

    def get_self_id(self) -> str:
        return "bot-self-id"

    def get_message_str(self) -> str:
        return self._text

    def get_sender_name(self) -> str:
        return "SDK Tester"

    def is_admin(self) -> bool:
        return False

    def get_message_outline(self) -> str:
        return self._text

    def get_messages(self):
        return list(self._messages)

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

    async def react(self, emoji: str) -> None:
        self.reactions.append(emoji)
        self._has_send_oper = True

    async def send_typing(self) -> None:
        self.typing_calls += 1

    async def send_streaming(self, generator, use_fallback: bool = False) -> None:
        async for chain in generator:
            self.streaming_chunks.append(
                chain.get_plain_text(with_other_comps_mark=True)
            )
        self._has_send_oper = True


def _build_sdk_plugin_response(output: dict) -> QuartResponse:
    status = int(output.get("status", 200))
    headers = output.get("headers")
    if headers is None:
        headers = {}
    if not isinstance(headers, dict):
        raise ValueError("SDK HTTP handler headers must be an object")

    body = output.get("body")
    if isinstance(body, (dict, list)):
        response = jsonify(body)
        response.status_code = status
        response.headers.setdefault("Content-Type", "application/json")
    elif isinstance(body, str):
        response = QuartResponse(
            body,
            status=status,
            content_type="text/plain; charset=utf-8",
        )
    elif body is None:
        response = QuartResponse("", status=status)
    else:
        raise ValueError("SDK HTTP handler body must be object, array, string or null")

    for key, value in headers.items():
        response.headers[str(key)] = str(value)
    return response


def _build_dashboard_with_sdk_route(fake_context, bridge: SdkPluginBridge):
    app = Quart("sdk-dashboard-e2e")
    lifecycle = SimpleNamespace(
        star_context=fake_context,
        sdk_plugin_bridge=bridge,
    )

    async def srv_plug_route(subpath, *args, **kwargs):
        for route, view_handler, methods, _ in fake_context.registered_web_apis:
            if route == f"/{subpath}" and request.method in methods:
                return await view_handler(*args, **kwargs)
        output = await lifecycle.sdk_plugin_bridge.dispatch_http_request(
            f"/{subpath}",
            request.method,
        )
        if output is not None:
            return _build_sdk_plugin_response(output)
        return jsonify({"status": "error", "message": "未找到该路由"})

    app.add_url_rule(
        "/api/plug/<path:subpath>",
        view_func=srv_plug_route,
        methods=["GET", "POST"],
    )
    return SimpleNamespace(app=app, core_lifecycle=lifecycle)


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

    bridge = SdkPluginBridge(fake_context)
    capability_bridge_module = sys.modules[
        bridge.capability_bridge.__class__.__module__
    ]
    monkeypatch.setattr(
        capability_bridge_module,
        "_get_runtime_sp",
        lambda: fake_sp,
    )
    bridge.env_manager.plan = lambda plugins: None
    bridge.env_manager.prepare_environment = lambda plugin: Path(sys.executable)
    fake_context.sdk_plugin_bridge = bridge

    await bridge.start()
    try:
        plugins = bridge.list_plugins()
        assert [plugin["name"] for plugin in plugins] == ["sdk_demo_echo"]
        assert plugins[0]["runtime_kind"] == "sdk"
        assert plugins[0]["state"] == "enabled"
        assert bridge.list_http_apis("sdk_demo_echo") == [
            {
                "route": "/sdk-demo-echo",
                "methods": ["GET", "POST"],
                "handler_capability": "sdk_demo_echo.http_echo",
                "description": "SDK demo echo endpoint",
            }
        ]

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

        chain_event = _FakeEvent("sdkchain")
        chain_result = await bridge.dispatch_message(chain_event)
        assert chain_result.sent_message is True
        assert chain_result.executed_handlers[0]["handler_id"].endswith("sdkchain")
        chain_message = fake_context.sent_messages[-1]["message_chain"]
        assert chain_message.get_plain_text(with_other_comps_mark=True).startswith(
            "sdk chain"
        )

        messages_event = _FakeEvent("sdkmessages")
        messages_result = await bridge.dispatch_message(messages_event)
        assert messages_result.sent_message is True
        assert "outline=sdkmessages" in str(fake_context.sent_messages[-1]["text"])
        assert "count=1" in str(fake_context.sent_messages[-1]["text"])
        assert "first=Plain" in str(fake_context.sent_messages[-1]["text"])

        extras_event = _FakeEvent("sdkextras")
        extras_result = await bridge.dispatch_message(extras_event)
        assert extras_result.sent_message is True
        assert (
            fake_context.sent_messages[-1]["text"]
            == "before=value size=1 after=missing"
        )

        typing_event = _FakeEvent("sdktyping")
        typing_result = await bridge.dispatch_message(typing_event)
        assert typing_result.sent_message is True
        assert typing_event.typing_calls == 1
        assert fake_context.sent_messages[-1]["text"] == "sdk typing supported=True"

        react_event = _FakeEvent("sdkreact")
        react_result = await bridge.dispatch_message(react_event)
        assert react_result.sent_message is True
        assert react_event.reactions == ["👍"]
        assert fake_context.sent_messages[-1]["text"] == "sdk react supported=True"

        stream_event = _FakeEvent("sdkstream")
        stream_result = await bridge.dispatch_message(stream_event)
        assert stream_result.sent_message is True
        assert stream_event.streaming_chunks == ["sdk", " stream"]
        assert fake_context.sent_messages[-1]["text"] == "sdk stream supported=True"

        await bridge.dispatch_system_event("astrbot_loaded")
        await bridge.dispatch_system_event(
            "platform_loaded",
            {"platform": "test-platform", "platform_id": "test-platform-id"},
        )
        events_event = _FakeEvent("sdkevents")
        events_result = await bridge.dispatch_message(events_event)
        assert events_result.sent_message is True
        assert "astrbot_loaded=astrbot_loaded" in str(
            fake_context.sent_messages[-1]["text"]
        )
        assert "platform_loaded=test-platform-id" in str(
            fake_context.sent_messages[-1]["text"]
        )
        assert "after_message_sent_count=" in str(
            fake_context.sent_messages[-1]["text"]
        )
        assert "data_dir=" in str(fake_context.sent_messages[-1]["text"])

        wait_start_event = _FakeEvent("sdkwait")
        wait_start_result = await bridge.dispatch_message(wait_start_event)
        assert wait_start_result.sent_message is True
        assert fake_context.sent_messages[-1]["text"] == "sdk waiter armed"

        waiter_followup = _FakeEvent("follow-up message")
        waiter_result = await bridge.dispatch_message(waiter_followup)
        assert waiter_result.sent_message is True
        assert waiter_result.executed_handlers == [
            {"plugin_id": "sdk_demo_echo", "handler_id": "__sdk_session_waiter__"}
        ]
        assert (
            fake_context.sent_messages[-1]["text"]
            == "sdk waiter received: follow-up message"
        )

        app = Quart(__name__)
        async with app.test_request_context(
            "/sdk-demo-echo?name=astrbot",
            method="POST",
            json={"hello": "world"},
        ):
            output = await bridge.dispatch_http_request("/sdk-demo-echo", "POST")
        assert output["status"] == 200
        assert output["body"]["plugin_id"] == "sdk_demo_echo"
        assert output["body"]["method"] == "POST"
        assert output["body"]["route"] == "/sdk-demo-echo"
        assert output["body"]["query"] == {"name": ["astrbot"]}
        assert output["body"]["json_body"] == {"hello": "world"}
        assert json.loads(output["body"]["text_body"]) == {"hello": "world"}

        await bridge.turn_off_plugin("sdk_demo_echo")
        plugins = bridge.list_plugins()
        assert plugins[0]["state"] == "disabled"
        assert plugins[0]["activated"] is False
        assert bridge.list_http_apis("sdk_demo_echo") == []

        disabled_event = _FakeEvent("sdkhello")
        disabled_result = await bridge.dispatch_message(disabled_event)
        assert disabled_result.sent_message is False
        assert disabled_result.executed_handlers == []
        assert disabled_result.skipped_reason == "no_match"

        await bridge.turn_on_plugin("sdk_demo_echo")
        plugins = bridge.list_plugins()
        assert plugins[0]["state"] == "enabled"
        assert plugins[0]["activated"] is True
        assert bridge.list_http_apis("sdk_demo_echo")[0]["route"] == "/sdk-demo-echo"

        reenabled_event = _FakeEvent("sdkhello")
        reenabled_result = await bridge.dispatch_message(reenabled_event)
        assert reenabled_result.sent_message is True
        assert reenabled_result.executed_handlers[0]["handler_id"].endswith("sdkhello")
    finally:
        await bridge.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dashboard_sdk_plug_route_end_to_end(
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

    bridge = SdkPluginBridge(fake_context)
    capability_bridge_module = sys.modules[
        bridge.capability_bridge.__class__.__module__
    ]
    monkeypatch.setattr(
        capability_bridge_module,
        "_get_runtime_sp",
        lambda: fake_sp,
    )
    bridge.env_manager.plan = lambda plugins: None
    bridge.env_manager.prepare_environment = lambda plugin: Path(sys.executable)
    fake_context.sdk_plugin_bridge = bridge

    await bridge.start()
    try:
        dashboard = _build_dashboard_with_sdk_route(fake_context, bridge)
        client = dashboard.app.test_client()

        sdk_response = await client.post(
            "/api/plug/sdk-demo-echo?name=astrbot",
            json={"hello": "world"},
        )
        assert sdk_response.status_code == 200
        assert sdk_response.headers["Content-Type"].startswith("application/json")
        sdk_payload = await sdk_response.get_json()
        assert sdk_payload["plugin_id"] == "sdk_demo_echo"
        assert sdk_payload["method"] == "POST"
        assert sdk_payload["route"] == "/sdk-demo-echo"
        assert sdk_payload["query"] == {"name": ["astrbot"]}
        assert sdk_payload["json_body"] == {"hello": "world"}
        assert json.loads(sdk_payload["text_body"]) == {"hello": "world"}

        async def legacy_get_handler(*_args, **_kwargs):
            return "legacy-first"

        fake_context.registered_web_apis = [
            ("/sdk-demo-echo", legacy_get_handler, ["GET"], "legacy test route")
        ]
        legacy_response = await client.get("/api/plug/sdk-demo-echo")
        assert legacy_response.status_code == 200
        assert await legacy_response.get_data(as_text=True) == "legacy-first"

        await bridge.turn_off_plugin("sdk_demo_echo")
        disabled_response = await client.post("/api/plug/sdk-demo-echo")
        disabled_payload = await disabled_response.get_json()
        assert disabled_response.status_code == 200
        assert disabled_payload["status"] == "error"
        assert disabled_payload["message"] == "未找到该路由"

        fake_context.registered_web_apis = []
        await bridge.turn_on_plugin("sdk_demo_echo")
        restored_response = await client.post(
            "/api/plug/sdk-demo-echo",
            json={"restored": True},
        )
        restored_payload = await restored_response.get_json()
        assert restored_response.status_code == 200
        assert restored_payload["plugin_id"] == "sdk_demo_echo"
        assert restored_payload["json_body"] == {"restored": True}

        missing_response = await client.get("/api/plug/not-found")
        missing_payload = await missing_response.get_json()
        assert missing_response.status_code == 200
        assert missing_payload["status"] == "error"
        assert missing_payload["message"] == "未找到该路由"
    finally:
        await bridge.stop()
