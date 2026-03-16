# ruff: noqa: E402
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrbot.core.sdk_bridge import capability_bridge as capability_bridge_module
from astrbot_sdk.context import CancelToken
from astrbot_sdk.context import Context as RuntimeContext
from astrbot_sdk.events import MessageEvent
from astrbot_sdk.llm.agents import AgentSpec
from astrbot_sdk.llm.entities import LLMToolSpec, ProviderMeta, ProviderRequest
from astrbot_sdk.runtime.capability_dispatcher import CapabilityDispatcher
from astrbot_sdk.runtime.loader import (
    LoadedLLMTool,
    load_plugin,
    load_plugin_spec,
    validate_plugin_spec,
)
from astrbot_sdk.testing import MockContext


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mock_context_p0_5_provider_queries_and_tool_manager() -> None:
    ctx = MockContext(plugin_id="sdk_demo_agent_tools")
    ctx.router.set_provider_catalog(
        "chat",
        [
            ProviderMeta(
                id="chat-provider-1",
                model="gpt-test",
                type="mock",
                provider_type="chat_completion",
            ).to_payload()
        ],
        active_id="chat-provider-1",
    )
    ctx.router.set_plugin_llm_tools(
        "sdk_demo_agent_tools",
        [
            LLMToolSpec(
                name="sdk_static_note",
                description="static tool",
                parameters_schema={"type": "object", "properties": {}},
                active=True,
            ).to_payload()
        ],
    )
    ctx.router.set_plugin_agents(
        "sdk_demo_agent_tools",
        [
            AgentSpec(
                name="sdk_demo_note_agent",
                description="demo agent",
                tool_names=["sdk_static_note"],
                runner_class="demo.Agent",
            ).to_payload()
        ],
    )

    current = await ctx.get_using_provider()
    assert current is not None
    assert current.id == "chat-provider-1"
    assert await ctx.get_current_chat_provider_id() == "chat-provider-1"
    assert [item.id for item in await ctx.get_all_providers()] == ["chat-provider-1"]

    manager = ctx.get_llm_tool_manager()
    assert [item.name for item in await manager.list_registered()] == [
        "sdk_static_note"
    ]
    assert [item.name for item in await manager.list_active()] == ["sdk_static_note"]
    assert await ctx.deactivate_llm_tool("sdk_static_note") is True
    assert await manager.list_active() == []
    assert await ctx.activate_llm_tool("sdk_static_note") is True

    added = await ctx.add_llm_tools(
        LLMToolSpec(
            name="sdk_dynamic_note",
            description="dynamic tool",
            parameters_schema={"type": "object", "properties": {}},
            active=True,
        )
    )
    assert added == ["sdk_dynamic_note"]
    assert sorted(item.name for item in await manager.list_registered()) == [
        "sdk_dynamic_note",
        "sdk_static_note",
    ]

    response = await ctx.tool_loop_agent(
        ProviderRequest(prompt="hello", tool_names=["sdk_static_note"])
    )
    assert response.text == "Mock tool loop: hello tools=sdk_static_note"


@pytest.mark.unit
def test_loader_discovers_p0_5_demo_tools_and_agents() -> None:
    plugin_dir = Path("data/sdk_plugins/sdk_demo_agent_tools")
    plugin = load_plugin_spec(plugin_dir)
    validate_plugin_spec(plugin)
    loaded = load_plugin(plugin)

    assert sorted(tool.spec.name for tool in loaded.llm_tools) == ["sdk_static_note"]
    assert sorted(agent.spec.name for agent in loaded.agents) == ["sdk_demo_note_agent"]


class _SlowSession:
    async def invoke_capability(
        self, _capability: str, _payload: dict, *, request_id: str
    ):
        await asyncio.sleep(0.05)
        return {"request_id": request_id}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sdk_tool_bridge_wraps_timeout_as_failed_tool_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = object.__new__(capability_bridge_module.CoreCapabilityBridge)
    bridge._plugin_bridge = SimpleNamespace(
        _records={"sdk_demo_agent_tools": SimpleNamespace(session=_SlowSession())},
        _get_dispatch_token=lambda _event: "dispatch-token",
    )
    monkeypatch.setattr(
        capability_bridge_module.EventConverter,
        "core_to_sdk",
        lambda *_args, **_kwargs: {"session_id": "local-session", "text": "hello"},
    )

    handler = bridge._make_sdk_tool_handler(
        plugin_id="sdk_demo_agent_tools",
        tool_spec=LLMToolSpec(
            name="sdk_static_note",
            description="static tool",
            parameters_schema={"type": "object", "properties": {}},
            handler_ref="sdk_static_note",
            active=True,
        ),
        tool_call_timeout=0.01,
    )

    output = await handler(object(), query="slow")
    assert isinstance(output, str)
    payload = json.loads(output)
    assert payload["tool_name"] == "sdk_static_note"
    assert payload["success"] is False
    assert "timeout" in payload["content"].lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_registered_llm_tool_rejects_non_mapping_tool_args() -> None:
    async def required_tool(required_text: str) -> str:
        return required_text

    dispatcher = CapabilityDispatcher(
        plugin_id="sdk_demo_agent_tools",
        peer=object(),
        capabilities=[],
        llm_tools=[
            LoadedLLMTool(
                spec=LLMToolSpec(
                    name="required_tool",
                    description="requires a string argument",
                    parameters_schema={"type": "object", "properties": {}},
                    active=True,
                ),
                callable=required_tool,
                owner=object(),
                plugin_id="sdk_demo_agent_tools",
            )
        ],
    )

    message = SimpleNamespace(
        id="tool-call-1",
        capability="internal.llm_tool.execute",
        input={
            "plugin_id": "sdk_demo_agent_tools",
            "tool_name": "required_tool",
            "tool_args": "not-a-dict",
            "event": "invalid-event-payload",
        },
    )

    with pytest.raises(TypeError, match="missing required argument 'required_text'"):
        await dispatcher.invoke(message, CancelToken())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_registered_llm_tool_injects_pep604_optional_event_and_context() -> None:
    async def optional_tool(
        event: MessageEvent | None = None,
        ctx: RuntimeContext | None = None,
    ) -> str:
        assert event is not None
        assert ctx is not None
        return f"{ctx.plugin_id}:{event.session_id}"

    dispatcher = CapabilityDispatcher(
        plugin_id="sdk_demo_agent_tools",
        peer=object(),
        capabilities=[],
        llm_tools=[
            LoadedLLMTool(
                spec=LLMToolSpec(
                    name="optional_tool",
                    description="uses optional event/context injections",
                    parameters_schema={"type": "object", "properties": {}},
                    active=True,
                ),
                callable=optional_tool,
                owner=object(),
                plugin_id="sdk_demo_agent_tools",
            )
        ],
    )

    message = SimpleNamespace(
        id="tool-call-2",
        capability="internal.llm_tool.execute",
        input={
            "plugin_id": "sdk_demo_agent_tools",
            "tool_name": "optional_tool",
            "tool_args": {},
            "event": {"session_id": "session-42", "text": "hello"},
        },
    )

    output = await dispatcher.invoke(message, CancelToken())
    assert output == {
        "content": "sdk_demo_agent_tools:session-42",
        "success": True,
    }


@pytest.mark.unit
def test_provider_to_payload_normalizes_core_provider_type_enum() -> None:
    from astrbot.core.provider.entities import ProviderMeta as CoreProviderMeta
    from astrbot.core.provider.entities import ProviderType as CoreProviderType

    provider = SimpleNamespace(
        meta=lambda: CoreProviderMeta(
            id="provider-1",
            model="gpt-test",
            type="openai",
            provider_type=CoreProviderType.CHAT_COMPLETION,
        )
    )

    payload = capability_bridge_module.CoreCapabilityBridge._provider_to_payload(
        provider
    )
    assert payload is not None
    assert payload["provider_type"] == "chat_completion"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_agent_tool_loop_run_accepts_dict_contexts_from_sdk_payload() -> None:
    bridge = object.__new__(capability_bridge_module.CoreCapabilityBridge)
    captured: dict[str, object] = {}

    class _FakeStarContext:
        async def tool_loop_agent(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                completion_text="done",
                usage=None,
                tools_call_ids=[],
                role="assistant",
                reasoning_content="",
                reasoning_signature=None,
                to_openai_tool_calls=lambda: [],
            )

    bridge._star_context = _FakeStarContext()
    bridge._resolve_plugin_id = lambda _request_id: "sdk_demo_agent_tools"
    bridge._resolve_event_request_context = lambda _request_id, _payload: (
        SimpleNamespace(event="fake-event")
    )
    bridge._resolve_current_chat_provider_id = lambda _request_context: "provider-1"
    bridge._build_sdk_toolset = lambda **_kwargs: None

    payload = {
        "prompt": "hello",
        "contexts": [{"role": "user", "content": "from-sdk"}],
    }
    output = await bridge._agent_tool_loop_run("request-1", payload, None)

    assert output["text"] == "done"
    assert captured["contexts"] == payload["contexts"]
