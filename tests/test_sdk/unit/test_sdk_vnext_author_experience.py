# ruff: noqa: E402
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from pydantic import BaseModel, Field

from astrbot.core.sdk_bridge.plugin_bridge import SdkPluginBridge
from astrbot_sdk._command_model import (
    parse_command_model_remainder,
    resolve_command_model_param,
)
from astrbot_sdk.cli import EXIT_RUNTIME, _run_sync_entrypoint
from astrbot_sdk.context import CancelToken, Context
from astrbot_sdk.conversation import ConversationSession, ConversationState
from astrbot_sdk.decorators import (
    ConversationMeta,
    LimiterMeta,
    cooldown,
    conversation_command,
    get_handler_meta,
    group_only,
    message_types,
    on_command,
    on_event,
    on_message,
    platforms,
    rate_limit,
    private_only,
)
from astrbot_sdk.errors import AstrBotError, ErrorCodes
from astrbot_sdk.events import MessageEvent
from astrbot_sdk.message_components import File, Image, MediaHelper, Record
from astrbot_sdk.message_result import MessageBuilder, MessageChain
from astrbot_sdk.protocol.descriptors import CommandTrigger, HandlerDescriptor, SessionRef
from astrbot_sdk.runtime.handler_dispatcher import HandlerDispatcher
from astrbot_sdk.runtime.loader import LoadedHandler, discover_plugins
from astrbot_sdk.star import Star


class _Peer:
    def __init__(self) -> None:
        descriptor = SimpleNamespace(supports_stream=False)
        self.remote_peer = {"name": "dummy-core"}
        self.remote_capability_map = {
            "platform.send": descriptor,
            "platform.send_chain": descriptor,
            "platform.send_by_session": descriptor,
            "system.session_waiter.register": descriptor,
            "system.session_waiter.unregister": descriptor,
        }
        self.sent_messages: list[dict[str, object]] = []
        self.waiter_ops: list[dict[str, object]] = []

    async def invoke(
        self,
        capability: str,
        payload: dict[str, object],
        *,
        stream: bool = False,
        request_id: str | None = None,
    ) -> dict[str, object]:
        if stream:
            raise AssertionError("unexpected stream invoke")
        if capability == "platform.send":
            self.sent_messages.append(
                {
                    "kind": "text",
                    "session": payload.get("session"),
                    "text": payload.get("text"),
                }
            )
            return {"message_id": f"text-{len(self.sent_messages)}"}
        if capability in {"platform.send_chain", "platform.send_by_session"}:
            self.sent_messages.append(
                {
                    "kind": "chain",
                    "session": payload.get("session"),
                    "chain": payload.get("chain"),
                }
            )
            return {"message_id": f"chain-{len(self.sent_messages)}"}
        if capability in {
            "system.session_waiter.register",
            "system.session_waiter.unregister",
        }:
            self.waiter_ops.append({"capability": capability, **payload})
            return {}
        raise AssertionError(f"unexpected capability: {capability}")


def _event_payload(text: str, *, session_id: str = "demo:private:user-1") -> dict[str, object]:
    return {
        "text": text,
        "session_id": session_id,
        "user_id": "user-1",
        "group_id": None,
        "platform": "demo",
        "platform_id": "demo",
        "message_type": "private",
        "target": SessionRef(conversation_id=session_id, platform="demo").to_payload(),
    }


class _BridgeStarContext:
    def __init__(self) -> None:
        self.registered_web_apis = []
        self.cron_manager = None

    def get_all_stars(self) -> list[object]:
        return []


class _ReplyCollector:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply(self, text: str) -> None:
        self.replies.append(text)


@pytest.mark.unit
def test_decorator_alias_and_conflict_rules() -> None:
    @on_command(["echo", "repeat", "say"])
    async def echo(event: MessageEvent, ctx: Context) -> None: ...

    meta = get_handler_meta(echo)
    assert meta is not None
    assert isinstance(meta.trigger, CommandTrigger)
    assert meta.trigger.command == "echo"
    assert meta.trigger.aliases == ["repeat", "say"]

    with pytest.raises(ValueError, match="platforms"):
        @platforms("qq")
        @on_message(platforms=["wechat"])
        async def _platform_conflict(event: MessageEvent, ctx: Context) -> None: ...

    with pytest.raises(ValueError, match="消息类型约束"):
        @group_only()
        @private_only()
        async def _scope_conflict(event: MessageEvent, ctx: Context) -> None: ...

    with pytest.raises(ValueError, match="不能叠加"):
        @rate_limit(1, 60)
        @cooldown(10)
        async def _limiter_conflict(event: MessageEvent, ctx: Context) -> None: ...

    with pytest.raises(ValueError, match="只适用于 on_command/on_message"):
        @on_event("ready")
        @rate_limit(1, 60)
        async def _event_limiter_conflict(ctx: Context) -> None: ...

    @conversation_command("quiz", timeout=12, mode="reject", busy_message="busy")
    async def quiz(
        event: MessageEvent,
        conversation: ConversationSession,
        ctx: Context,
    ) -> None: ...

    conversation_meta = get_handler_meta(quiz)
    assert conversation_meta is not None
    assert conversation_meta.conversation == ConversationMeta(
        timeout=12,
        mode="reject",
        busy_message="busy",
        grace_period=1.0,
    )


class _EchoInput(BaseModel):
    text: str = Field(description="echo text")
    times: int = Field(default=1, ge=1, le=5)
    loud: bool | None = None


async def _echo_handler(
    event: MessageEvent,
    params: _EchoInput,
    ctx: Context,
) -> None:
    for _ in range(params.times):
        await event.reply(params.text.upper() if params.loud else params.text)


@pytest.mark.unit
def test_command_model_parser_help_and_duplicates() -> None:
    model_param = resolve_command_model_param(_echo_handler)
    assert model_param is not None

    parsed = parse_command_model_remainder(
        remainder="hello --times 2 --loud",
        model_param=model_param,
        command_name="echo",
    )
    assert parsed.help_text is None
    assert parsed.model is not None
    assert parsed.model.model_dump() == {"text": "hello", "times": 2, "loud": True}

    help_result = parse_command_model_remainder(
        remainder="--help --unknown nope",
        model_param=model_param,
        command_name="echo",
    )
    assert help_result.model is None
    assert help_result.help_text is not None
    assert "用法: /echo" in help_result.help_text

    with pytest.raises(AstrBotError, match="Duplicate field"):
        parse_command_model_remainder(
            remainder="--text a --text b",
            model_param=model_param,
            command_name="echo",
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_plugin_logger_watch_and_default_on_error_render_details() -> None:
    ctx = Context(peer=_Peer(), plugin_id="sdk-demo")
    watcher = ctx.logger.watch()
    bound_logger = ctx.logger.bind(
        request_id="req-1",
        handler_ref="sdk-demo:test.handle",
        session_id="demo:private:user-1",
        event_type="message",
    )

    async def _next_entry():
        return await watcher.__anext__()

    pending = asyncio.create_task(_next_entry())
    await asyncio.sleep(0)
    bound_logger.info("hello {}", "sdk")
    entry = await pending

    assert entry.plugin_id == "sdk-demo"
    assert entry.message == "hello sdk"
    assert entry.context == {
        "request_id": "req-1",
        "handler_ref": "sdk-demo:test.handle",
        "session_id": "demo:private:user-1",
        "event_type": "message",
    }

    await watcher.aclose()

    error = AstrBotError.invalid_input(
        "bad input",
        hint="fix it",
        docs_url="https://docs.astrbot.org/sdk/errors#invalid-input",
        details={"field": "name"},
    )
    event = _ReplyCollector()

    await Star().on_error(error, event, ctx)

    assert event.replies == [
        "fix it\n文档：https://docs.astrbot.org/sdk/errors#invalid-input\n详情：{\"field\": \"name\"}"
    ]


@pytest.mark.unit
def test_discovery_issue_surfaces_to_dashboard_failed_item(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "plugins"
    broken_dir = plugins_dir / "broken"
    broken_dir.mkdir(parents=True)
    (broken_dir / "plugin.yaml").write_text(
        "\n".join(
            [
                "name: broken",
                'runtime:',
                '  python: "3.11"',
                "components:",
                "  - class: main:BrokenPlugin",
            ]
        ),
        encoding="utf-8",
    )

    discovered = discover_plugins(plugins_dir)

    assert discovered.plugins == []
    assert "broken" in discovered.skipped_plugins
    assert len(discovered.issues) == 1
    issue = discovered.issues[0]
    assert issue.plugin_id == "broken"
    assert issue.phase == "discovery"
    assert "requirements.txt" in issue.details

    bridge = SdkPluginBridge(_BridgeStarContext())
    bridge._set_discovery_issues(discovered.issues)  # noqa: SLF001

    dashboard_items = bridge.list_plugins()
    assert dashboard_items == [
        {
            "name": "broken",
            "repo": "",
            "author": "",
            "desc": "插件发现失败",
            "version": "0.0.0",
            "reserved": False,
            "activated": False,
            "online_vesion": "",
            "handlers": [],
            "display_name": "broken",
            "logo": None,
            "support_platforms": [],
            "astrbot_version": "",
            "installed_at": None,
            "runtime_kind": "sdk",
            "source_kind": "local_dir",
            "managed_by": "sdk_bridge",
            "state": "failed",
            "trigger_summary": [],
            "unsupported_features": [],
            "failure_reason": issue.details,
            "issues": [issue.to_payload()],
        }
    ]

    metadata = bridge.get_plugin_metadata("broken")
    assert metadata is not None
    assert metadata["enabled"] is False
    assert metadata["runtime_kind"] == "sdk"
    assert metadata["issues"] == [issue.to_payload()]


@pytest.mark.unit
def test_cli_error_render_includes_docs_details_and_context(
    capsys: pytest.CaptureFixture[str],
) -> None:
    CliRunner()  # keep click testing dependency exercised in the SDK test env

    def _boom() -> None:
        raise AstrBotError.invalid_input(
            "bad input",
            hint="fix it",
            docs_url="https://docs.astrbot.org/sdk/errors#invalid-input",
            details={"field": "name"},
        )

    with pytest.raises(SystemExit) as exc_info:
        _run_sync_entrypoint(
            _boom,
            log_message="run test entrypoint",
            context={"plugin_dir": Path("demo-plugin")},
        )

    assert exc_info.value.code == EXIT_RUNTIME
    captured = capsys.readouterr()
    assert "Error[invalid_input]: bad input" in captured.err
    assert "Suggestion: fix it" in captured.err
    assert "Docs: https://docs.astrbot.org/sdk/errors#invalid-input" in captured.err
    assert "Details: {'field': 'name'}" in captured.err
    assert "plugin_dir: demo-plugin" in captured.err


class _LimiterPlugin(Star):
    async def handle(self, event: MessageEvent, ctx: Context) -> None:
        await event.reply("ok")


async def _invoke_handler(
    dispatcher: HandlerDispatcher,
    *,
    handler_id: str,
    text: str,
    request_id: str,
    session_id: str = "demo:private:user-1",
) -> dict[str, object]:
    message = SimpleNamespace(
        id=request_id,
        input={
            "handler_id": handler_id,
            "event": _event_payload(text, session_id=session_id),
            "args": {},
        },
    )
    return await dispatcher.invoke(message, CancelToken())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rate_limit_and_cooldown_behaviors() -> None:
    peer = _Peer()
    owner = _LimiterPlugin()
    handler_id = "sdk-demo:test.handle"

    limited = LoadedHandler(
        descriptor=HandlerDescriptor(
            id=handler_id,
            trigger=CommandTrigger(command="ping"),
        ),
        callable=owner.handle,
        owner=owner,
        plugin_id="sdk-demo",
        limiter=LimiterMeta(kind="rate_limit", limit=1, window=60),
    )
    dispatcher = HandlerDispatcher(
        plugin_id="sdk-demo",
        peer=peer,
        handlers=[limited],
    )

    await _invoke_handler(dispatcher, handler_id=handler_id, text="ping", request_id="r1")
    await _invoke_handler(dispatcher, handler_id=handler_id, text="ping", request_id="r2")

    assert peer.sent_messages[0]["text"] == "ok"
    assert peer.sent_messages[1]["text"] == "操作过于频繁，请稍后再试。"

    cooldown_loaded = LoadedHandler(
        descriptor=HandlerDescriptor(
            id="sdk-demo:test.cooldown",
            trigger=CommandTrigger(command="cool"),
        ),
        callable=owner.handle,
        owner=owner,
        plugin_id="sdk-demo",
        limiter=LimiterMeta(
            kind="cooldown",
            limit=1,
            window=30,
            behavior="error",
        ),
    )
    cooldown_dispatcher = HandlerDispatcher(
        plugin_id="sdk-demo",
        peer=_Peer(),
        handlers=[cooldown_loaded],
    )

    await _invoke_handler(
        cooldown_dispatcher,
        handler_id="sdk-demo:test.cooldown",
        text="cool",
        request_id="c1",
    )
    with pytest.raises(AstrBotError) as exc_info:
        await _invoke_handler(
            cooldown_dispatcher,
            handler_id="sdk-demo:test.cooldown",
            text="cool",
            request_id="c2",
        )
    assert exc_info.value.code == ErrorCodes.COOLDOWN_ACTIVE


@pytest.mark.unit
@pytest.mark.asyncio
async def test_message_builder_event_helpers_and_media_helper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chain = (
        MessageBuilder()
        .text("hello")
        .at("123")
        .image("https://example.com/a.png")
        .build()
    )
    assert isinstance(chain, MessageChain)
    assert chain.plain_text(with_other_comps_mark=True) == "hello [At] [Image]"

    event = MessageEvent.from_payload(
        {
            **_event_payload("hello"),
            "message_type": "group",
            "group_id": "room-1",
            "messages": [
                {"type": "text", "data": {"text": "hello"}},
                {"type": "at", "data": {"qq": "123"}},
                {"type": "image", "data": {"file": "https://example.com/a.png"}},
                {"type": "file", "data": {"name": "a.txt", "file": "https://example.com/a.txt"}},
            ],
        }
    )
    assert event.is_group_chat() is True
    assert event.has_component(Image) is True
    assert len(event.get_images()) == 1
    assert len(event.get_files()) == 1
    assert event.extract_plain_text() == "hello"
    assert event.get_at_users() == ["123"]

    assert isinstance(await MediaHelper.from_url("https://example.com/a.png"), Image)
    assert isinstance(await MediaHelper.from_url("https://example.com/a.mp3"), Record)
    assert isinstance(await MediaHelper.from_url("https://example.com/a.bin"), File)

    with pytest.raises(AstrBotError) as invalid_exc:
        await MediaHelper.download("ftp://example.com/a.bin", tmp_path)
    assert invalid_exc.value.code == ErrorCodes.INVALID_INPUT

    file_save_dir = tmp_path / "existing-file"
    file_save_dir.write_text("x", encoding="utf-8")
    with pytest.raises(AstrBotError) as internal_exc:
        await MediaHelper.download("https://example.com/a.bin", file_save_dir)
    assert internal_exc.value.code == ErrorCodes.INTERNAL_ERROR

    def _boom(url: str, filename: str | Path):
        raise OSError("network")

    monkeypatch.setattr("astrbot_sdk.message_components.urlretrieve", _boom)
    with pytest.raises(AstrBotError) as network_exc:
        await MediaHelper.download("https://example.com/a.bin", tmp_path / "downloads")
    assert network_exc.value.code == ErrorCodes.NETWORK_ERROR


class _ConversationPlugin(Star):
    def __init__(self, states: list[ConversationState]) -> None:
        super().__init__()
        self.states = states

    async def run(
        self,
        event: MessageEvent,
        conversation: ConversationSession,
        ctx: Context,
    ) -> None:
        try:
            answer = await conversation.ask("question?")
            await conversation.reply(f"answer:{answer.text}")
        finally:
            self.states.append(conversation.state)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_conversation_reject_and_replace_modes() -> None:
    async def _exercise(mode: str) -> tuple[HandlerDispatcher, _Peer, list[ConversationState]]:
        peer = _Peer()
        states: list[ConversationState] = []
        owner = _ConversationPlugin(states)
        handler = LoadedHandler(
            descriptor=HandlerDescriptor(
                id=f"sdk-demo:test.{mode}",
                trigger=CommandTrigger(command="quiz"),
            ),
            callable=owner.run,
            owner=owner,
            plugin_id="sdk-demo",
            conversation=ConversationMeta(
                timeout=30,
                mode=mode,  # type: ignore[arg-type]
                busy_message="busy now",
                grace_period=0.05,
            ),
        )
        dispatcher = HandlerDispatcher(
            plugin_id="sdk-demo",
            peer=peer,
            handlers=[handler],
        )

        await _invoke_handler(
            dispatcher,
            handler_id=handler.descriptor.id,
            text="quiz",
            request_id=f"{mode}-1",
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        await _invoke_handler(
            dispatcher,
            handler_id=handler.descriptor.id,
            text="quiz",
            request_id=f"{mode}-2",
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        waiter_message = SimpleNamespace(
            id=f"{mode}-wait",
            input={
                "handler_id": "__sdk_session_waiter__",
                "event": _event_payload("42"),
            },
        )
        await dispatcher.invoke(waiter_message, CancelToken())
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return dispatcher, peer, states

    reject_dispatcher, reject_peer, reject_states = await _exercise("reject")
    assert [item["text"] for item in reject_peer.sent_messages if item["kind"] == "text"] == [
        "question?",
        "busy now",
        "answer:42",
    ]
    assert not reject_dispatcher._conversations  # noqa: SLF001
    assert ConversationState.REPLACED not in reject_states

    replace_dispatcher, replace_peer, replace_states = await _exercise("replace")
    assert [item["text"] for item in replace_peer.sent_messages if item["kind"] == "text"] == [
        "question?",
        "question?",
        "answer:42",
    ]
    assert not replace_dispatcher._conversations  # noqa: SLF001
    assert ConversationState.REPLACED in replace_states
