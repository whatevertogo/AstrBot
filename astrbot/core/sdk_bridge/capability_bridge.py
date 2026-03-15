from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from astrbot.core.message.components import ComponentTypes, Image, Plain
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.utils.astrbot_path import get_astrbot_data_path
from astrbot_sdk._invocation_context import current_caller_plugin_id
from astrbot_sdk.errors import AstrBotError
from astrbot_sdk.runtime.capability_router import CapabilityRouter, StreamExecution

if TYPE_CHECKING:
    from astrbot.core.agent.tool import ToolSet
    from astrbot.core.provider.entities import LLMResponse
    from astrbot.core.star.context import Context as StarContext


def _get_runtime_sp():
    from astrbot.core import sp

    return sp


def _get_runtime_html_renderer():
    from astrbot.core import html_renderer

    return html_renderer


def _get_runtime_tool_types():
    from astrbot.core.agent.tool import FunctionTool, ToolSet

    return FunctionTool, ToolSet


@dataclass(slots=True)
class _EventStreamState:
    request_context: Any
    queue: asyncio.Queue[MessageChain | None]
    task: asyncio.Task[None]


class CoreCapabilityBridge(CapabilityRouter):
    MEMORY_SCOPE = "sdk_memory"

    def __init__(self, *, star_context: StarContext, plugin_bridge) -> None:
        self._star_context = star_context
        self._plugin_bridge = plugin_bridge
        self._event_streams: dict[str, _EventStreamState] = {}
        super().__init__()
        self._register_system_capabilities()

    def _register_llm_capabilities(self) -> None:
        self.register(
            self._builtin_descriptor("llm.chat", "Send chat request"),
            call_handler=self._llm_chat,
        )
        self.register(
            self._builtin_descriptor(
                "llm.chat_raw",
                "Send chat request and return raw response",
            ),
            call_handler=self._llm_chat_raw,
        )
        self.register(
            self._builtin_descriptor(
                "llm.stream_chat",
                "Stream chat response",
                supports_stream=True,
                cancelable=True,
            ),
            stream_handler=self._llm_stream_chat,
        )

    async def _llm_chat(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        response = await self._call_llm(payload, request_id=request_id)
        return {"text": response.completion_text}

    async def _llm_chat_raw(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        response = await self._call_llm(payload, request_id=request_id)
        usage = None
        if response.usage is not None:
            usage = {
                "input_tokens": response.usage.input,
                "output_tokens": response.usage.output,
                "total_tokens": response.usage.total,
            }
        return {
            "text": response.completion_text,
            "usage": usage,
            "finish_reason": "tool_calls" if response.tools_call_ids else "stop",
            "tool_calls": response.to_openai_tool_calls(),
            "role": response.role,
            "reasoning_content": response.reasoning_content or None,
            "reasoning_signature": response.reasoning_signature,
        }

    async def _llm_stream_chat(
        self,
        request_id: str,
        payload: dict[str, Any],
        token,
    ) -> StreamExecution:
        provider, request_kwargs = self._resolve_llm_request(
            payload,
            request_id=request_id,
        )

        async def fallback_iterator() -> AsyncIterator[dict[str, Any]]:
            response = await provider.text_chat(**request_kwargs)
            for char in response.completion_text:
                token.raise_if_cancelled()
                await asyncio.sleep(0)
                yield {"text": char}

        async def iterator() -> AsyncIterator[dict[str, Any]]:
            try:
                stream = provider.text_chat_stream(**request_kwargs)
                yielded_text = False
                async for response in stream:
                    token.raise_if_cancelled()
                    text = response.completion_text
                    if response.is_chunk:
                        if text:
                            yielded_text = True
                            yield {"text": text}
                        continue
                    if text:
                        if yielded_text:
                            yield {"_final_text": text}
                        else:
                            yielded_text = True
                            yield {"text": text, "_final_text": text}
                    else:
                        yield {"_final_text": text}
            except NotImplementedError:
                async for item in fallback_iterator():
                    yield item

        def finalize(chunks: list[dict[str, Any]]) -> dict[str, Any]:
            final_text = None
            for item in reversed(chunks):
                if "_final_text" in item:
                    final_text = str(item.get("_final_text", ""))
                    break
            if final_text is None:
                final_text = "".join(str(item.get("text", "")) for item in chunks)
            return {"text": final_text}

        return StreamExecution(
            iterator=iterator(),
            finalize=finalize,
        )

    async def _call_llm(
        self,
        payload: dict[str, Any],
        *,
        request_id: str,
    ) -> LLMResponse:
        provider, request_kwargs = self._resolve_llm_request(
            payload,
            request_id=request_id,
        )
        return await provider.text_chat(**request_kwargs)

    def _resolve_llm_request(
        self,
        payload: dict[str, Any],
        *,
        request_id: str,
    ) -> tuple[Any, dict[str, Any]]:
        request_context = self._plugin_bridge.resolve_request_session(request_id)
        provider_id = payload.get("provider_id")
        if provider_id:
            provider = self._star_context.get_provider_by_id(str(provider_id))
        else:
            provider = self._star_context.get_using_provider(
                request_context.event.unified_msg_origin
                if request_context is not None
                else None,
            )
        if provider is None:
            raise AstrBotError.internal_error(
                "No active chat provider is available",
                hint="Please configure a chat provider in AstrBot first",
            )
        return provider, self._normalize_llm_payload(payload)

    @staticmethod
    def _normalize_llm_payload(payload: dict[str, Any]) -> dict[str, Any]:
        contexts_payload = payload.get("contexts")
        if contexts_payload is None:
            contexts_payload = payload.get("history")
        contexts = (
            [dict(item) for item in contexts_payload]
            if isinstance(contexts_payload, list)
            else None
        )
        image_urls = payload.get("image_urls")
        tool_calls_result = payload.get("tool_calls_result")
        tools_payload = payload.get("tools")
        request_kwargs: dict[str, Any] = {
            "prompt": str(payload.get("prompt", "")),
            "image_urls": (
                [str(item) for item in image_urls]
                if isinstance(image_urls, list)
                else None
            ),
            "func_tool": (
                CoreCapabilityBridge._build_toolset(tools_payload)
                if isinstance(tools_payload, list)
                else None
            ),
            "contexts": contexts,
            "tool_calls_result": (
                [dict(item) for item in tool_calls_result]
                if isinstance(tool_calls_result, list)
                else None
            ),
            "system_prompt": str(payload.get("system", "")),
            "model": (str(payload["model"]) if payload.get("model") else None),
            "temperature": payload.get("temperature"),
        }
        return request_kwargs

    @staticmethod
    def _build_toolset(tools_payload: list[Any]) -> ToolSet:
        function_tool_cls, tool_set_cls = _get_runtime_tool_types()
        tool_set = tool_set_cls()
        for item in tools_payload:
            if not isinstance(item, dict):
                raise AstrBotError.invalid_input("llm tools items must be objects")
            if str(item.get("type", "function")) != "function":
                raise AstrBotError.invalid_input(
                    "Only function tools are supported in AstrBot SDK MVP"
                )
            function_payload = item.get("function")
            if not isinstance(function_payload, dict):
                raise AstrBotError.invalid_input(
                    "llm tools items must contain a function object"
                )
            name = str(function_payload.get("name", "")).strip()
            if not name:
                raise AstrBotError.invalid_input(
                    "llm function tool name must not be empty"
                )
            description = str(function_payload.get("description", "") or "")
            parameters = function_payload.get("parameters")
            if not isinstance(parameters, dict):
                parameters = {"type": "object", "properties": {}}
            tool_set.add_tool(
                function_tool_cls(
                    name=name,
                    description=description,
                    parameters=parameters,
                    handler=None,
                )
            )
        return tool_set

    def _register_db_capabilities(self) -> None:
        self.register(
            self._builtin_descriptor("db.get", "Read plugin kv"),
            call_handler=self._db_get,
        )
        self.register(
            self._builtin_descriptor("db.set", "Write plugin kv"),
            call_handler=self._db_set,
        )
        self.register(
            self._builtin_descriptor("db.delete", "Delete plugin kv"),
            call_handler=self._db_delete,
        )
        self.register(
            self._builtin_descriptor("db.list", "List plugin kv"),
            call_handler=self._db_list,
        )
        self.register(
            self._builtin_descriptor("db.get_many", "Read plugin kv in batch"),
            call_handler=self._db_get_many,
        )
        self.register(
            self._builtin_descriptor("db.set_many", "Write plugin kv in batch"),
            call_handler=self._db_set_many,
        )
        self.register(
            self._builtin_descriptor(
                "db.watch",
                "Watch plugin kv",
                supports_stream=True,
                cancelable=True,
            ),
            stream_handler=self._db_watch,
        )

    async def _db_get(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        return {
            "value": await _get_runtime_sp().get_async(
                "plugin",
                plugin_id,
                str(payload.get("key", "")),
                None,
            )
        }

    async def _db_set(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        await _get_runtime_sp().put_async(
            "plugin",
            plugin_id,
            str(payload.get("key", "")),
            payload.get("value"),
        )
        return {}

    async def _db_delete(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        await _get_runtime_sp().remove_async(
            "plugin",
            plugin_id,
            str(payload.get("key", "")),
        )
        return {}

    async def _db_list(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        prefix = payload.get("prefix")
        prefix_value = str(prefix) if isinstance(prefix, str) else None
        items = await _get_runtime_sp().range_get_async("plugin", plugin_id, None)
        keys = sorted(
            item.key
            for item in items
            if prefix_value is None or item.key.startswith(prefix_value)
        )
        return {"keys": keys}

    async def _db_get_many(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        keys_payload = payload.get("keys")
        if not isinstance(keys_payload, list):
            raise AstrBotError.invalid_input("db.get_many requires a keys array")
        items = []
        for key in keys_payload:
            key_text = str(key)
            items.append(
                {
                    "key": key_text,
                    "value": await _get_runtime_sp().get_async(
                        "plugin",
                        plugin_id,
                        key_text,
                        None,
                    ),
                }
            )
        return {"items": items}

    async def _db_set_many(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        items_payload = payload.get("items")
        if not isinstance(items_payload, list):
            raise AstrBotError.invalid_input("db.set_many requires an items array")
        for item in items_payload:
            if not isinstance(item, dict):
                raise AstrBotError.invalid_input("db.set_many items must be objects")
            await _get_runtime_sp().put_async(
                "plugin",
                plugin_id,
                str(item.get("key", "")),
                item.get("value"),
            )
        return {}

    async def _db_watch(
        self,
        _request_id: str,
        _payload: dict[str, Any],
        _token,
    ) -> StreamExecution:
        raise AstrBotError.invalid_input(
            "db.watch is unsupported in AstrBot SDK MVP",
            hint="Use db.get/list polling in MVP",
        )

    def _register_memory_capabilities(self) -> None:
        self.register(
            self._builtin_descriptor("memory.search", "Search plugin memory"),
            call_handler=self._memory_search,
        )
        self.register(
            self._builtin_descriptor("memory.save", "Save plugin memory"),
            call_handler=self._memory_save,
        )
        self.register(
            self._builtin_descriptor("memory.get", "Get plugin memory"),
            call_handler=self._memory_get,
        )
        self.register(
            self._builtin_descriptor("memory.delete", "Delete plugin memory"),
            call_handler=self._memory_delete,
        )
        self.register(
            self._builtin_descriptor(
                "memory.save_with_ttl",
                "Save plugin memory with ttl metadata",
            ),
            call_handler=self._memory_save_with_ttl,
        )
        self.register(
            self._builtin_descriptor("memory.get_many", "Get plugin memories"),
            call_handler=self._memory_get_many,
        )
        self.register(
            self._builtin_descriptor("memory.delete_many", "Delete plugin memories"),
            call_handler=self._memory_delete_many,
        )
        self.register(
            self._builtin_descriptor("memory.stats", "Get plugin memory stats"),
            call_handler=self._memory_stats,
        )

    async def _memory_search(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        query = str(payload.get("query", ""))
        entries = await self._load_memory_entries(plugin_id)
        items = [
            {"key": key, "value": value}
            for key, value in entries.items()
            if query in key or query in json.dumps(value, ensure_ascii=False)
        ]
        return {"items": items}

    async def _memory_save(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        value = payload.get("value")
        if not isinstance(value, dict):
            raise AstrBotError.invalid_input("memory.save requires an object value")
        await _get_runtime_sp().put_async(
            self.MEMORY_SCOPE,
            plugin_id,
            str(payload.get("key", "")),
            value,
        )
        return {}

    async def _memory_get(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        value = await _get_runtime_sp().get_async(
            self.MEMORY_SCOPE,
            plugin_id,
            str(payload.get("key", "")),
            None,
        )
        return {"value": value}

    async def _memory_delete(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        await _get_runtime_sp().remove_async(
            self.MEMORY_SCOPE,
            plugin_id,
            str(payload.get("key", "")),
        )
        return {}

    async def _memory_save_with_ttl(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        value = payload.get("value")
        if not isinstance(value, dict):
            raise AstrBotError.invalid_input(
                "memory.save_with_ttl requires an object value"
            )
        ttl_seconds = int(payload.get("ttl_seconds", 0))
        await _get_runtime_sp().put_async(
            self.MEMORY_SCOPE,
            plugin_id,
            str(payload.get("key", "")),
            {"value": value, "ttl_seconds": ttl_seconds},
        )
        return {}

    async def _memory_get_many(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        keys_payload = payload.get("keys")
        if not isinstance(keys_payload, list):
            raise AstrBotError.invalid_input("memory.get_many requires a keys array")
        items = []
        for key in keys_payload:
            key_text = str(key)
            stored = await _get_runtime_sp().get_async(
                self.MEMORY_SCOPE,
                plugin_id,
                key_text,
                None,
            )
            if (
                isinstance(stored, dict)
                and "value" in stored
                and "ttl_seconds" in stored
            ):
                stored = stored["value"]
            items.append({"key": key_text, "value": stored})
        return {"items": items}

    async def _memory_delete_many(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        keys_payload = payload.get("keys")
        if not isinstance(keys_payload, list):
            raise AstrBotError.invalid_input("memory.delete_many requires a keys array")
        deleted_count = 0
        for key in keys_payload:
            key_text = str(key)
            existing = await _get_runtime_sp().get_async(
                self.MEMORY_SCOPE,
                plugin_id,
                key_text,
                None,
            )
            if existing is None:
                continue
            await _get_runtime_sp().remove_async(
                self.MEMORY_SCOPE,
                plugin_id,
                key_text,
            )
            deleted_count += 1
        return {"deleted_count": deleted_count}

    async def _memory_stats(
        self,
        request_id: str,
        _payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        entries = await self._load_memory_entries(plugin_id)
        ttl_entries = sum(
            1
            for value in entries.values()
            if isinstance(value, dict) and "value" in value and "ttl_seconds" in value
        )
        total_bytes = sum(
            len(str(key)) + len(str(value)) for key, value in entries.items()
        )
        return {
            "total_items": len(entries),
            "total_bytes": total_bytes,
            "plugin_id": plugin_id,
            "ttl_entries": ttl_entries,
        }

    def _register_platform_capabilities(self) -> None:
        self.register(
            self._builtin_descriptor("platform.send", "Send plain text"),
            call_handler=self._platform_send,
        )
        self.register(
            self._builtin_descriptor("platform.send_image", "Send image"),
            call_handler=self._platform_send_image,
        )
        self.register(
            self._builtin_descriptor("platform.send_chain", "Send message chain"),
            call_handler=self._platform_send_chain,
        )
        self.register(
            self._builtin_descriptor("platform.get_members", "Get group members"),
            call_handler=self._platform_get_members,
        )

    async def _platform_send(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        session, dispatch_token = self._resolve_dispatch_target(request_id, payload)
        self._plugin_bridge.before_platform_send(dispatch_token)
        await self._star_context.send_message(
            session,
            MessageChain([Plain(str(payload.get("text", "")), convert=False)]),
        )
        return {"message_id": self._plugin_bridge.mark_platform_send(dispatch_token)}

    async def _platform_send_image(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        session, dispatch_token = self._resolve_dispatch_target(request_id, payload)
        self._plugin_bridge.before_platform_send(dispatch_token)
        image_url = str(payload.get("image_url", ""))
        component = (
            Image.fromURL(image_url)
            if image_url.startswith(("http://", "https://"))
            else Image.fromFileSystem(image_url)
        )
        await self._star_context.send_message(session, MessageChain([component]))
        return {"message_id": self._plugin_bridge.mark_platform_send(dispatch_token)}

    async def _platform_send_chain(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        session, dispatch_token = self._resolve_dispatch_target(request_id, payload)
        self._plugin_bridge.before_platform_send(dispatch_token)
        chain_payload = payload.get("chain")
        if not isinstance(chain_payload, list):
            raise AstrBotError.invalid_input(
                "platform.send_chain requires a chain array"
            )
        await self._star_context.send_message(
            session,
            self._build_core_message_chain(chain_payload),
        )
        return {"message_id": self._plugin_bridge.mark_platform_send(dispatch_token)}

    async def _platform_get_members(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        _session, dispatch_token = self._resolve_dispatch_target(request_id, payload)
        request_context = self._plugin_bridge.get_request_context_by_token(
            dispatch_token
        )
        if request_context is None:
            return {"members": []}
        group = await request_context.event.get_group()
        if group is None:
            return {"members": []}
        members = []
        for member in getattr(group, "member_list", []) or []:
            user_id = getattr(member, "user_id", None)
            if user_id is None:
                continue
            members.append(
                {
                    "user_id": str(user_id),
                    "nickname": str(getattr(member, "nickname", "")),
                    "role": str(getattr(member, "role", "")),
                }
            )
        return {"members": members}

    def _register_http_capabilities(self) -> None:
        self.register(
            self._builtin_descriptor("http.register_api", "Register http route"),
            call_handler=self._http_register_api,
        )
        self.register(
            self._builtin_descriptor("http.unregister_api", "Unregister http route"),
            call_handler=self._http_unregister_api,
        )
        self.register(
            self._builtin_descriptor("http.list_apis", "List http routes"),
            call_handler=self._http_list_apis,
        )

    async def _http_register_api(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        methods = payload.get("methods")
        if not isinstance(methods, list) or not all(
            isinstance(item, str) for item in methods
        ):
            raise AstrBotError.invalid_input(
                "http.register_api requires a string methods array"
            )
        self._plugin_bridge.register_http_api(
            plugin_id=plugin_id,
            route=str(payload.get("route", "")),
            methods=methods,
            handler_capability=str(payload.get("handler_capability", "")),
            description=str(payload.get("description", "")),
        )
        return {}

    async def _http_unregister_api(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        methods = payload.get("methods")
        if not isinstance(methods, list) or not all(
            isinstance(item, str) for item in methods
        ):
            raise AstrBotError.invalid_input(
                "http.unregister_api requires a string methods array"
            )
        self._plugin_bridge.unregister_http_api(
            plugin_id=plugin_id,
            route=str(payload.get("route", "")),
            methods=methods,
        )
        return {}

    async def _http_list_apis(
        self,
        request_id: str,
        _payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        return {"apis": self._plugin_bridge.list_http_apis(plugin_id)}

    def _register_metadata_capabilities(self) -> None:
        self.register(
            self._builtin_descriptor("metadata.get_plugin", "Get plugin metadata"),
            call_handler=self._metadata_get_plugin,
        )
        self.register(
            self._builtin_descriptor("metadata.list_plugins", "List plugins metadata"),
            call_handler=self._metadata_list_plugins,
        )
        self.register(
            self._builtin_descriptor(
                "metadata.get_plugin_config",
                "Get current plugin config",
            ),
            call_handler=self._metadata_get_plugin_config,
        )

    async def _metadata_get_plugin(
        self,
        _request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin = self._plugin_bridge.get_plugin_metadata(str(payload.get("name", "")))
        return {"plugin": plugin}

    async def _metadata_list_plugins(
        self,
        _request_id: str,
        _payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        return {"plugins": self._plugin_bridge.list_plugin_metadata()}

    async def _metadata_get_plugin_config(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        requested = str(payload.get("name", ""))
        if requested != plugin_id:
            return {"config": None}
        return {"config": self._plugin_bridge.get_plugin_config(plugin_id)}

    def _resolve_plugin_id(self, request_id: str) -> str:
        plugin_id = current_caller_plugin_id()
        if plugin_id:
            return plugin_id
        return self._plugin_bridge.resolve_request_plugin_id(request_id)

    async def _load_memory_entries(self, plugin_id: str) -> dict[str, Any]:
        items = await _get_runtime_sp().range_get_async(
            self.MEMORY_SCOPE,
            plugin_id,
            None,
        )
        entries: dict[str, Any] = {}
        for item in items:
            key = str(getattr(item, "key", ""))
            if not key:
                continue
            entries[key] = await _get_runtime_sp().get_async(
                self.MEMORY_SCOPE,
                plugin_id,
                key,
                None,
            )
        return entries

    def _register_system_capabilities(self) -> None:
        self.register(
            self._builtin_descriptor("system.get_data_dir", "Get plugin data dir"),
            call_handler=self._system_get_data_dir,
            exposed=False,
        )
        self.register(
            self._builtin_descriptor("system.text_to_image", "Render text to image"),
            call_handler=self._system_text_to_image,
            exposed=False,
        )
        self.register(
            self._builtin_descriptor("system.html_render", "Render html template"),
            call_handler=self._system_html_render,
            exposed=False,
        )
        self.register(
            self._builtin_descriptor(
                "system.session_waiter.register",
                "Register sdk session waiter",
            ),
            call_handler=self._system_session_waiter_register,
            exposed=False,
        )
        self.register(
            self._builtin_descriptor(
                "system.session_waiter.unregister",
                "Unregister sdk session waiter",
            ),
            call_handler=self._system_session_waiter_unregister,
            exposed=False,
        )
        self.register(
            self._builtin_descriptor("system.event.react", "Send sdk event reaction"),
            call_handler=self._system_event_react,
            exposed=False,
        )
        self.register(
            self._builtin_descriptor(
                "system.event.send_typing",
                "Send sdk event typing state",
            ),
            call_handler=self._system_event_send_typing,
            exposed=False,
        )
        self.register(
            self._builtin_descriptor(
                "system.event.send_streaming",
                "Send sdk event streaming chunks",
            ),
            call_handler=self._system_event_send_streaming,
            exposed=False,
        )
        self.register(
            self._builtin_descriptor(
                "system.event.send_streaming_chunk",
                "Push sdk event streaming chunk",
            ),
            call_handler=self._system_event_send_streaming_chunk,
            exposed=False,
        )
        self.register(
            self._builtin_descriptor(
                "system.event.send_streaming_close",
                "Close sdk event streaming session",
            ),
            call_handler=self._system_event_send_streaming_close,
            exposed=False,
        )

    async def _system_get_data_dir(
        self,
        request_id: str,
        _payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        data_dir = Path(get_astrbot_data_path()) / "plugin_data" / plugin_id
        data_dir.mkdir(parents=True, exist_ok=True)
        return {"path": str(data_dir.resolve())}

    async def _system_text_to_image(
        self,
        _request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        config_obj = self._star_context.get_config()
        template_name = None
        if hasattr(config_obj, "get"):
            try:
                template_name = config_obj.get("t2i_active_template")
            except Exception:
                template_name = None
        result = await _get_runtime_html_renderer().render_t2i(
            str(payload.get("text", "")),
            return_url=bool(payload.get("return_url", True)),
            template_name=template_name,
        )
        return {"result": result}

    async def _system_html_render(
        self,
        _request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        data = payload.get("data")
        if not isinstance(data, dict):
            raise AstrBotError.invalid_input("system.html_render requires object data")
        options = payload.get("options")
        if options is not None and not isinstance(options, dict):
            raise AstrBotError.invalid_input(
                "system.html_render options must be an object or null"
            )
        result = await _get_runtime_html_renderer().render_custom_template(
            str(payload.get("tmpl", "")),
            data,
            return_url=bool(payload.get("return_url", True)),
            options=options,
        )
        return {"result": result}

    async def _system_session_waiter_register(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        self._plugin_bridge.register_session_waiter(
            plugin_id=plugin_id,
            session_key=str(payload.get("session_key", "")),
        )
        return {}

    async def _system_session_waiter_unregister(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        plugin_id = self._resolve_plugin_id(request_id)
        self._plugin_bridge.unregister_session_waiter(
            plugin_id=plugin_id,
            session_key=str(payload.get("session_key", "")),
        )
        return {}

    async def _system_event_react(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        request_context = self._resolve_event_request_context(request_id, payload)
        if request_context is None or request_context.cancelled:
            return {"supported": False}
        self._plugin_bridge.before_platform_send(request_context.dispatch_token)
        await request_context.event.react(str(payload.get("emoji", "")))
        return {
            "supported": bool(
                self._plugin_bridge.mark_platform_send(request_context.dispatch_token)
            )
        }

    async def _system_event_send_typing(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        request_context = self._resolve_event_request_context(request_id, payload)
        if request_context is None or request_context.cancelled:
            return {"supported": False}
        if type(request_context.event).send_typing is AstrMessageEvent.send_typing:
            return {"supported": False}
        await request_context.event.send_typing()
        return {"supported": True}

    async def _system_event_send_streaming(
        self,
        request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        request_context = self._resolve_event_request_context(request_id, payload)
        if request_context is None or request_context.cancelled:
            return {"supported": False}
        if (
            type(request_context.event).send_streaming
            is AstrMessageEvent.send_streaming
        ):
            return {"supported": False}
        self._plugin_bridge.before_platform_send(request_context.dispatch_token)
        queue: asyncio.Queue[MessageChain | None] = asyncio.Queue()

        async def iterator() -> AsyncIterator[MessageChain]:
            while True:
                chunk = await queue.get()
                if chunk is None or request_context.cancelled:
                    return
                yield chunk
                await asyncio.sleep(0)

        stream_id = uuid.uuid4().hex
        task = asyncio.create_task(
            request_context.event.send_streaming(
                iterator(),
                use_fallback=bool(payload.get("use_fallback", False)),
            )
        )
        self._event_streams[stream_id] = _EventStreamState(
            request_context=request_context,
            queue=queue,
            task=task,
        )
        return {"supported": True, "stream_id": stream_id}

    async def _system_event_send_streaming_chunk(
        self,
        _request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        stream_state = self._event_streams.get(str(payload.get("stream_id", "")))
        if stream_state is None:
            raise AstrBotError.invalid_input("Unknown sdk event streaming session")
        if stream_state.request_context.cancelled:
            raise AstrBotError.cancelled("The SDK request has been cancelled")
        chain_payload = payload.get("chain")
        if not isinstance(chain_payload, list):
            raise AstrBotError.invalid_input(
                "system.event.send_streaming_chunk requires a chain array"
            )
        await stream_state.queue.put(self._build_core_message_chain(chain_payload))
        return {}

    async def _system_event_send_streaming_close(
        self,
        _request_id: str,
        payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        stream_id = str(payload.get("stream_id", ""))
        stream_state = self._event_streams.pop(stream_id, None)
        if stream_state is None:
            raise AstrBotError.invalid_input("Unknown sdk event streaming session")
        await stream_state.queue.put(None)
        try:
            await stream_state.task
        finally:
            self._event_streams.pop(stream_id, None)
        return {
            "supported": bool(
                self._plugin_bridge.mark_platform_send(
                    stream_state.request_context.dispatch_token
                )
            )
        }

    def _resolve_dispatch_target(
        self,
        request_id: str,
        payload: dict[str, Any],
    ) -> tuple[str, str]:
        target_payload = payload.get("target")
        dispatch_token = ""
        if isinstance(target_payload, dict):
            raw_payload = target_payload.get("raw")
            if isinstance(raw_payload, dict):
                dispatch_token = str(raw_payload.get("dispatch_token", ""))
                if not dispatch_token:
                    nested_raw_payload = raw_payload.get("raw")
                    if isinstance(nested_raw_payload, dict):
                        dispatch_token = str(
                            nested_raw_payload.get("dispatch_token", "")
                        )
        if not dispatch_token:
            request_context = self._plugin_bridge.resolve_request_session(request_id)
            if request_context is None:
                raise AstrBotError.invalid_input(
                    "Missing dispatch token for platform send"
                )
            dispatch_token = request_context.dispatch_token
        session = str(payload.get("session", ""))
        return session, dispatch_token

    def _resolve_event_request_context(
        self,
        request_id: str,
        payload: dict[str, Any],
    ):
        target_payload = payload.get("target")
        dispatch_token = ""
        if isinstance(target_payload, dict):
            raw_payload = target_payload.get("raw")
            if isinstance(raw_payload, dict):
                dispatch_token = str(raw_payload.get("dispatch_token", ""))
                if not dispatch_token:
                    nested_raw = raw_payload.get("raw")
                    if isinstance(nested_raw, dict):
                        dispatch_token = str(nested_raw.get("dispatch_token", ""))
        if dispatch_token:
            return self._plugin_bridge.get_request_context_by_token(dispatch_token)
        return self._plugin_bridge.resolve_request_session(request_id)

    @staticmethod
    def _build_core_message_chain(chain_payload: list[dict[str, Any]]) -> MessageChain:
        components = []
        for item in chain_payload:
            if not isinstance(item, dict):
                continue
            comp_type = str(item.get("type", "")).lower()
            data = item.get("data", {})
            if comp_type in {"text", "plain"} and isinstance(data, dict):
                components.append(Plain(str(data.get("text", "")), convert=False))
                continue
            if comp_type == "image" and isinstance(data, dict):
                file_value = str(data.get("file") or data.get("url") or "")
                if file_value.startswith(("http://", "https://")):
                    components.append(Image.fromURL(file_value))
                elif file_value:
                    file_path = (
                        file_value[8:]
                        if file_value.startswith("file:///")
                        else file_value
                    )
                    components.append(Image.fromFileSystem(file_path))
                continue
            component_cls = ComponentTypes.get(comp_type)
            if component_cls is None:
                components.append(
                    Plain(json.dumps(item, ensure_ascii=False), convert=False)
                )
                continue
            try:
                if isinstance(data, dict):
                    components.append(component_cls(**data))
                else:
                    components.append(Plain(str(item), convert=False))
            except Exception:
                components.append(
                    Plain(json.dumps(item, ensure_ascii=False), convert=False)
                )
        return MessageChain(components)
