# ruff: noqa: E402
from __future__ import annotations

import sys
import types
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

from astrbot_sdk import MessageEvent
from astrbot_sdk import message_components as sdk_message_components
from astrbot.core.message.components import File as CoreFile
from astrbot_sdk.context import Context
from astrbot_sdk.message_components import (
    File,
    Image,
    Plain,
    UnknownComponent,
    payloads_to_components,
)
from astrbot_sdk.message_result import EventResultType, MessageChain, MessageEventResult
from astrbot_sdk.protocol.descriptors import SessionRef
from astrbot_sdk.runtime.handler_dispatcher import HandlerDispatcher


class _DummyPeer:
    def __init__(self) -> None:
        self.remote_peer = {"name": "dummy-core"}
        self.remote_capability_map = {
            "platform.send": SimpleNamespace(supports_stream=False),
            "platform.send_chain": SimpleNamespace(supports_stream=False),
            "system.event.react": SimpleNamespace(supports_stream=False),
            "system.event.send_typing": SimpleNamespace(supports_stream=False),
            "system.event.send_streaming": SimpleNamespace(supports_stream=False),
            "system.event.send_streaming_chunk": SimpleNamespace(
                supports_stream=False
            ),
            "system.event.send_streaming_close": SimpleNamespace(
                supports_stream=False
            ),
        }
        self.sent_messages: list[dict] = []
        self.event_actions: list[dict] = []
        self._open_streams: dict[str, dict] = {}

    async def invoke(self, capability: str, payload: dict, *, stream: bool = False):
        if stream:
            raise ValueError("stream unsupported in dummy peer")
        if capability == "platform.send":
            self.sent_messages.append(
                {
                    "kind": "text",
                    "session": payload.get("session"),
                    "text": payload.get("text"),
                }
            )
            return {"message_id": "text-1"}
        if capability == "platform.send_chain":
            self.sent_messages.append(
                {
                    "kind": "chain",
                    "session": payload.get("session"),
                    "chain": payload.get("chain"),
                }
            )
            return {"message_id": "chain-1"}
        if capability == "system.event.react":
            self.event_actions.append(
                {"action": "react", "emoji": payload.get("emoji")}
            )
            return {"supported": True}
        if capability == "system.event.send_typing":
            self.event_actions.append({"action": "send_typing"})
            return {"supported": True}
        if capability == "system.event.send_streaming":
            stream_id = f"stream-{len(self._open_streams) + 1}"
            self._open_streams[stream_id] = {
                "chunks": [],
                "use_fallback": payload.get("use_fallback"),
            }
            return {"supported": True, "stream_id": stream_id}
        if capability == "system.event.send_streaming_chunk":
            stream_id = str(payload.get("stream_id"))
            self._open_streams[stream_id]["chunks"].append(
                {"chain": payload.get("chain")}
            )
            return {}
        if capability == "system.event.send_streaming_close":
            stream_id = str(payload.get("stream_id"))
            stream = self._open_streams.pop(stream_id)
            self.event_actions.append(
                {
                    "action": "send_streaming",
                    "chunks": stream["chunks"],
                    "use_fallback": stream["use_fallback"],
                }
            )
            return {"supported": True}
        raise AssertionError(f"unexpected capability: {capability}")

    async def invoke_stream(self, capability: str, payload: dict):
        raise AssertionError(f"unexpected stream capability: {capability}")


@pytest.mark.unit
def test_payload_to_components_and_event_local_state() -> None:
    event = MessageEvent.from_payload(
        {
            "text": "hello",
            "session_id": "demo:private:user-1",
            "platform": "demo",
            "platform_id": "demo",
            "message_type": "private",
            "message_outline": "hello [UnknownComponent]",
            "messages": [
                {"type": "text", "data": {"text": "hello"}},
                {"type": "mystery", "data": {"payload": 1}},
            ],
            "extras": {"seed": "value"},
        }
    )

    messages = event.get_messages()
    assert len(messages) == 2
    assert isinstance(messages[0], Plain)
    assert isinstance(messages[1], UnknownComponent)
    assert event.get_message_outline() == "hello [UnknownComponent]"
    assert event.get_extra("seed") == "value"

    event.set_extra("local", 42)
    assert event.get_extra("local") == 42
    assert event.get_extra()["local"] == 42
    event.clear_extra()
    assert event.get_extra("local", "missing") == "missing"

    empty_result = event.make_result()
    assert empty_result.type is EventResultType.EMPTY
    assert empty_result.chain.components == []

    image_result = event.image_result("https://example.com/a.png")
    assert image_result.type is EventResultType.CHAIN
    assert isinstance(image_result.chain.components[0], Image)

    chain_result = event.chain_result([Plain("sdk", convert=False)])
    assert chain_result.type is EventResultType.CHAIN
    assert chain_result.chain.get_plain_text() == "sdk"


@pytest.mark.unit
def test_payloads_to_components_unknown_fallback() -> None:
    components = payloads_to_components(
        [
            {"type": "text", "data": {"text": "hi"}},
            {"type": "unknown-segment", "data": {"foo": "bar"}},
        ]
    )

    assert isinstance(components[0], Plain)
    assert isinstance(components[1], UnknownComponent)
    assert components[1].toDict() == {
        "type": "unknown-segment",
        "data": {"foo": "bar"},
    }


@pytest.mark.unit
def test_file_component_roundtrip_accepts_legacy_core_payload() -> None:
    payload = sdk_message_components.component_to_payload_sync(
        CoreFile(name="sample.txt", file="C:/tmp/sample.txt")
    )

    component = sdk_message_components.payload_to_component(payload)

    assert isinstance(component, File)
    assert component.file == "C:/tmp/sample.txt"
    assert component.toDict() == {
        "type": "file",
        "data": {"name": "sample.txt", "file": "C:/tmp/sample.txt"},
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_message_component_file_methods(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")

    image = Image.fromFileSystem(str(sample))
    assert await image.convert_to_file_path() == str(sample.resolve())

    file_component = File(name="sample.txt", file=str(sample))
    assert await file_component.get_file() == str(sample.resolve())

    async def fake_register_file_to_service(path: str) -> str:
        assert path == str(sample.resolve())
        return "https://callback.example/api/file/token-123"

    monkeypatch.setattr(
        sdk_message_components,
        "_register_file_to_service",
        fake_register_file_to_service,
    )

    assert (
        await image.register_to_file_service()
        == "https://callback.example/api/file/token-123"
    )
    assert (
        await file_component.register_to_file_service()
        == "https://callback.example/api/file/token-123"
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_event_actions_and_send_chain_with_mock_context() -> None:
    peer = _DummyPeer()
    ctx = Context(peer=peer, plugin_id="sdk-demo")
    event = MessageEvent.from_payload(
        {
            "text": "hello",
            "session_id": "demo:private:user-1",
            "platform": "demo",
            "platform_id": "demo",
            "message_type": "private",
            "target": SessionRef(conversation_id="demo:private:user-1").to_payload(),
        },
        context=ctx,
    )

    assert await event.react("👍") is True
    assert await event.send_typing() is True

    async def generator():
        yield "sdk"
        yield [Plain(" stream", convert=False)]

    assert await event.send_streaming(generator(), use_fallback=True) is True

    await ctx.platform.send_chain(event.session_id, MessageChain([Plain("chain")]))

    assert [item["action"] for item in peer.event_actions] == [
        "react",
        "send_typing",
        "send_streaming",
    ]
    assert peer.event_actions[-1]["chunks"] == [
        {"chain": [{"type": "text", "data": {"text": "sdk"}}]},
        {"chain": [{"type": "text", "data": {"text": " stream"}}]},
    ]
    assert peer.sent_messages[-1]["kind"] == "chain"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_send_streaming_pushes_chunks_incrementally() -> None:
    peer = _DummyPeer()
    ctx = Context(peer=peer, plugin_id="sdk-demo")
    event = MessageEvent.from_payload(
        {
            "text": "hello",
            "session_id": "demo:private:user-1",
            "platform": "demo",
            "platform_id": "demo",
            "message_type": "private",
            "target": SessionRef(conversation_id="demo:private:user-1").to_payload(),
        },
        context=ctx,
    )

    async def generator():
        yield "sdk"
        assert peer._open_streams["stream-1"]["chunks"] == [
            {"chain": [{"type": "text", "data": {"text": "sdk"}}]}
        ]
        yield [Plain(" stream", convert=False)]

    assert await event.send_streaming(generator(), use_fallback=True) is True
    assert peer.event_actions[-1]["chunks"] == [
        {"chain": [{"type": "text", "data": {"text": "sdk"}}]},
        {"chain": [{"type": "text", "data": {"text": " stream"}}]},
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handler_dispatcher_normalizes_sdk_result_objects() -> None:
    dispatcher = HandlerDispatcher.__new__(HandlerDispatcher)
    peer = _DummyPeer()
    ctx = Context(peer=peer, plugin_id="sdk-demo")
    event = MessageEvent.from_payload(
        {
            "text": "hello",
            "session_id": "demo:private:user-1",
            "platform": "demo",
            "platform_id": "demo",
            "message_type": "private",
            "target": SessionRef(conversation_id="demo:private:user-1").to_payload(),
        },
        context=ctx,
    )

    assert (
        await dispatcher._send_result(  # noqa: SLF001
            MessageEventResult(
                type=EventResultType.CHAIN,
                chain=MessageChain([Plain("from-result")]),
            ),
            event,
            ctx,
        )
        is True
    )
    assert (
        await dispatcher._send_result(  # noqa: SLF001
            MessageChain([Plain("from-chain")]),
            event,
            ctx,
        )
        is True
    )
    assert (
        await dispatcher._send_result(  # noqa: SLF001
            [Plain("from-list")],
            event,
            ctx,
        )
        is True
    )

    assert [item["kind"] for item in peer.sent_messages] == ["chain", "chain", "chain"]
