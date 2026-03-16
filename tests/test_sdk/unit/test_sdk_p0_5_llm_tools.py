# ruff: noqa: E402
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrbot.core.sdk_bridge import capability_bridge as capability_bridge_module
from astrbot_sdk.llm.agents import AgentSpec
from astrbot_sdk.llm.entities import LLMToolSpec, ProviderMeta, ProviderRequest
from astrbot_sdk.runtime.loader import (
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
    assert [item.name for item in await manager.list_registered()] == ["sdk_static_note"]
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
    async def invoke_capability(self, _capability: str, _payload: dict, *, request_id: str):
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
