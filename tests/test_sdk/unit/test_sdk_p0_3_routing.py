# ruff: noqa: E402
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrbot_sdk.commands import print_cmd_tree
from astrbot_sdk.context import CancelToken
from astrbot_sdk.filters import (
    CustomFilter,
    LocalFilterBinding,
    MessageTypeFilter,
    PlatformFilter,
    all_of,
)
from astrbot_sdk.protocol.descriptors import (
    LocalFilterRefSpec,
    MessageTypeFilterSpec,
)
from astrbot_sdk.runtime.handler_dispatcher import HandlerDispatcher
from astrbot_sdk.runtime.loader import (
    load_plugin,
    load_plugin_spec,
    validate_plugin_spec,
)
from astrbot_sdk.testing import MockCapabilityRouter, MockPeer

PLUGIN_DIR = Path("data/sdk_plugins/sdk_demo_routing")


def _load_demo_plugin():
    plugin = load_plugin_spec(PLUGIN_DIR)
    validate_plugin_spec(plugin)
    return load_plugin(plugin)


@pytest.mark.unit
def test_message_types_compile_to_filter_spec() -> None:
    loaded = _load_demo_plugin()
    handler = next(
        item for item in loaded.handlers if item.callable.__name__ == "sdk_group_only"
    )

    assert any(
        isinstance(filter_spec, MessageTypeFilterSpec)
        and filter_spec.message_types == ["group"]
        for filter_spec in handler.descriptor.filters
    )


@pytest.mark.unit
def test_custom_filter_stays_local_and_descriptor_serializable() -> None:
    loaded = _load_demo_plugin()
    handler = next(
        item for item in loaded.handlers if item.callable.__name__ == "sdk_local_filter"
    )

    assert any(
        isinstance(filter_spec, LocalFilterRefSpec)
        for filter_spec in handler.descriptor.filters
    )
    assert handler.local_filters
    assert isinstance(handler.local_filters[0], LocalFilterBinding)
    dumped = handler.descriptor.model_dump()
    assert "callable" not in str(dumped)


@pytest.mark.unit
def test_command_group_is_flattened_and_printable() -> None:
    loaded = _load_demo_plugin()
    spec = importlib.util.spec_from_file_location(
        "sdk_demo_routing_main_test",
        PLUGIN_DIR / "main.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["sdk_demo_routing_main_test"] = module
    spec.loader.exec_module(module)
    tree = print_cmd_tree(module.ADMIN_GROUP)
    handler = next(
        item for item in loaded.handlers if item.callable.__name__ == "sdk_group_echo"
    )

    assert "sdkadmin" in tree
    assert "echo" in tree
    assert handler.descriptor.trigger.command == "sdkadmin echo"
    assert sorted(handler.descriptor.trigger.aliases) == sorted(
        ["sdkadmin say", "sdka echo", "sdka say"]
    )
    assert handler.descriptor.command_route is not None
    assert handler.descriptor.command_route.display_command == "sdkadmin echo"


@pytest.mark.unit
def test_composite_filter_keeps_descriptor_serializable() -> None:
    binding = all_of(
        PlatformFilter(["qq"]),
        MessageTypeFilter(["group"]),
        CustomFilter(lambda *, event: event.text == "ok", filter_id="demo.filter"),
    )
    spec, local_bindings = binding.compile()

    assert isinstance(spec, LocalFilterRefSpec)
    assert local_bindings


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dispatcher_applies_local_filters_and_parses_types() -> None:
    loaded = _load_demo_plugin()
    router = MockCapabilityRouter()
    peer = MockPeer(router)
    dispatcher = HandlerDispatcher(
        plugin_id="sdk_demo_routing",
        peer=peer,
        handlers=[
            item
            for item in loaded.handlers
            if item.callable.__name__ in {"sdk_local_filter", "sdk_bool"}
        ],
    )

    blocked = await dispatcher.invoke(
        SimpleNamespace(
            id="req-blocked",
            input={
                "handler_id": next(
                    item.descriptor.id
                    for item in loaded.handlers
                    if item.callable.__name__ == "sdk_local_filter"
                ),
                "event": {
                    "text": "sdkfilter blocked",
                    "session_id": "test-session",
                    "user_id": "test-user",
                    "platform": "test",
                    "message_type": "private",
                },
            },
        ),
        CancelToken(),
    )
    assert blocked == {"sent_message": False, "stop": False, "call_llm": False}

    await dispatcher.invoke(
        SimpleNamespace(
            id="req-passed",
            input={
                "handler_id": next(
                    item.descriptor.id
                    for item in loaded.handlers
                    if item.callable.__name__ == "sdk_local_filter"
                ),
                "event": {
                    "text": "sdkfilter pass",
                    "session_id": "test-session",
                    "user_id": "test-user",
                    "platform": "test",
                    "message_type": "private",
                },
            },
        ),
        CancelToken(),
    )
    assert router.platform_sink.records[-1].text == "sdk custom filter pass"

    await dispatcher.invoke(
        SimpleNamespace(
            id="req-typed",
            input={
                "handler_id": next(
                    item.descriptor.id
                    for item in loaded.handlers
                    if item.callable.__name__ == "sdk_bool"
                ),
                "event": {
                    "text": "sdkbool yes 3",
                    "session_id": "test-session",
                    "user_id": "test-user",
                    "platform": "test",
                    "message_type": "private",
                },
            },
        ),
        CancelToken(),
    )
    assert router.platform_sink.records[-1].text == "enabled=True amount=3"


@pytest.mark.unit
def test_greedy_str_non_last_fails_at_load_time(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "bad_plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "requirements.txt").write_text("", encoding="utf-8")
    (plugin_dir / "plugin.yaml").write_text(
        "\n".join(
            [
                "name: bad_plugin",
                "runtime:",
                '  python: "3.11"',
                "components:",
                "  - class: main:BadPlugin",
            ]
        ),
        encoding="utf-8",
    )
    (plugin_dir / "main.py").write_text(
        "\n".join(
            [
                "from astrbot_sdk import Star",
                "from astrbot_sdk.decorators import on_command",
                "from astrbot_sdk.events import MessageEvent",
                "from astrbot_sdk.types import GreedyStr",
                "",
                "class BadPlugin(Star):",
                '    @on_command("broken")',
                "    async def broken(self, event: MessageEvent, phrase: GreedyStr, extra: str):",
                '        await event.reply("never")',
            ]
        ),
        encoding="utf-8",
    )

    plugin = load_plugin_spec(plugin_dir)
    validate_plugin_spec(plugin)
    with pytest.raises(ValueError, match="GreedyStr"):
        load_plugin(plugin)
