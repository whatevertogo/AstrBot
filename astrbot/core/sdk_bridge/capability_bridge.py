from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from astrbot.api import sp
from astrbot.core.agent.tool import FunctionTool, ToolSet
from astrbot.core.message.components import ComponentTypes, Image, Plain
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.provider.entities import LLMResponse
from astrbot_sdk._invocation_context import current_caller_plugin_id
from astrbot_sdk.errors import AstrBotError
from astrbot_sdk.runtime.capability_router import CapabilityRouter, StreamExecution

if TYPE_CHECKING:
    from astrbot.core.star.context import Context as StarContext


class CoreCapabilityBridge(CapabilityRouter):
    def __init__(self, *, star_context: StarContext, plugin_bridge) -> None:
        self._star_context = star_context
        self._plugin_bridge = plugin_bridge
        super().__init__()

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
        tool_set = ToolSet()
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
                FunctionTool(
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
            "value": await sp.get_async(
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
        await sp.put_async(
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
        await sp.remove_async("plugin", plugin_id, str(payload.get("key", "")))
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
        items = await sp.range_get_async("plugin", plugin_id, None)
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
                    "value": await sp.get_async("plugin", plugin_id, key_text, None),
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
            await sp.put_async(
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
                file_value = str(data.get("file", ""))
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
        await self._star_context.send_message(session, MessageChain(components))
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
            call_handler=self._http_unsupported,
        )
        self.register(
            self._builtin_descriptor("http.unregister_api", "Unregister http route"),
            call_handler=self._http_unsupported,
        )
        self.register(
            self._builtin_descriptor("http.list_apis", "List http routes"),
            call_handler=self._http_unsupported,
        )

    async def _http_unsupported(
        self,
        _request_id: str,
        _payload: dict[str, Any],
        _token,
    ) -> dict[str, Any]:
        raise AstrBotError.invalid_input(
            "SDK HTTP APIs are unsupported in AstrBot MVP",
            hint="Do not use http.register_api/http.unregister_api/http.list_apis in MVP",
        )

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
