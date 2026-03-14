from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from astrbot.core import logger
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.utils.astrbot_path import get_astrbot_data_path
from astrbot_sdk.errors import AstrBotError
from astrbot_sdk.protocol.descriptors import (
    CommandTrigger,
    EventTrigger,
    HandlerDescriptor,
    MessageTrigger,
    ScheduleTrigger,
)
from astrbot_sdk.runtime.loader import (
    PluginEnvironmentManager,
    PluginSpec,
    discover_plugins,
    load_plugin_config,
)
from astrbot_sdk.runtime.supervisor import WorkerSession

from .capability_bridge import CoreCapabilityBridge
from .event_converter import EventConverter
from .trigger_converter import TriggerConverter, TriggerMatch

SDK_STATE_ENABLED = "enabled"
SDK_STATE_DISABLED = "disabled"
SDK_STATE_RELOADING = "reloading"
SDK_STATE_FAILED = "failed"
SDK_STATE_UNSUPPORTED_PARTIAL = "unsupported_partial"

SKIP_LEGACY_STOPPED = "legacy_stopped"
SKIP_LEGACY_REPLIED = "legacy_replied"
SKIP_SDK_RELOADING = "sdk_reloading"
SKIP_NO_MATCH = "no_match"
SKIP_WORKER_FAILED = "worker_failed"


@dataclass(slots=True)
class SdkHandlerRef:
    descriptor: HandlerDescriptor
    declaration_order: int

    @property
    def handler_id(self) -> str:
        return self.descriptor.id

    @property
    def handler_name(self) -> str:
        return self.descriptor.id.rsplit(".", 1)[-1]


@dataclass(slots=True)
class SdkDispatchResult:
    matched_handlers: list[dict[str, str]] = field(default_factory=list)
    executed_handlers: list[dict[str, str]] = field(default_factory=list)
    sent_message: bool = False
    stopped: bool = False
    skipped_reason: str | None = None


@dataclass(slots=True)
class _DispatchState:
    event: AstrMessageEvent
    sent_message: bool = False
    stopped: bool = False


@dataclass(slots=True)
class _RequestContext:
    plugin_id: str
    request_id: str
    dispatch_token: str
    dispatch_state: _DispatchState
    cancelled: bool = False

    @property
    def event(self) -> AstrMessageEvent:
        return self.dispatch_state.event


@dataclass(slots=True)
class _InFlightRequest:
    request_id: str
    dispatch_token: str
    task: asyncio.Task[dict[str, Any]]
    logical_cancelled: bool = False


@dataclass(slots=True)
class SdkPluginRecord:
    plugin: PluginSpec
    load_order: int
    state: str
    unsupported_features: list[str]
    config: dict[str, Any]
    handlers: list[SdkHandlerRef]
    session: WorkerSession | None = None
    restart_attempted: bool = False
    failure_reason: str = ""

    @property
    def plugin_id(self) -> str:
        return self.plugin.name


class SdkPluginBridge:
    def __init__(self, star_context) -> None:
        self.star_context = star_context
        self.plugins_dir = Path(get_astrbot_data_path()) / "sdk_plugins"
        self.state_path = Path(get_astrbot_data_path()) / "sdk_plugins_state.json"
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self._started = False
        self._stopping = False
        self._state_overrides = self._load_state_overrides()
        self.env_manager = PluginEnvironmentManager(Path(__file__).resolve().parents[3])
        self.capability_bridge = CoreCapabilityBridge(
            star_context=star_context,
            plugin_bridge=self,
        )
        self._records: dict[str, SdkPluginRecord] = {}
        self._request_contexts: dict[str, _RequestContext] = {}
        self._request_id_to_token: dict[str, str] = {}
        self._plugin_requests: dict[str, dict[str, _InFlightRequest]] = {}

    async def start(self) -> None:
        if self._started:
            return
        await self.reload_all(reset_restart_budget=True)
        self._started = True

    async def stop(self) -> None:
        if not self._started and not self._records:
            return
        self._stopping = True
        for plugin_id in list(self._records.keys()):
            await self._cancel_plugin_requests(plugin_id)
        for record in list(self._records.values()):
            if record.session is not None:
                await record.session.stop()
                record.session = None
        self._records.clear()
        self._request_contexts.clear()
        self._request_id_to_token.clear()
        self._plugin_requests.clear()
        self._started = False
        self._stopping = False

    async def reload_all(self, *, reset_restart_budget: bool = False) -> None:
        discovered = discover_plugins(self.plugins_dir)
        self.env_manager.plan(discovered.plugins)
        known = {plugin.name for plugin in discovered.plugins}
        for plugin_id in list(self._records.keys()):
            if plugin_id not in known:
                await self._teardown_plugin(plugin_id)
                self._records.pop(plugin_id, None)
        for load_order, plugin in enumerate(discovered.plugins):
            await self._load_or_reload_plugin(
                plugin,
                load_order=load_order,
                reset_restart_budget=reset_restart_budget,
            )

    async def reload_plugin(self, plugin_id: str) -> None:
        discovered = discover_plugins(self.plugins_dir)
        self.env_manager.plan(discovered.plugins)
        for load_order, plugin in enumerate(discovered.plugins):
            if plugin.name != plugin_id:
                continue
            await self._load_or_reload_plugin(
                plugin,
                load_order=load_order,
                reset_restart_budget=True,
            )
            return
        raise ValueError(f"SDK plugin not found: {plugin_id}")

    async def turn_off_plugin(self, plugin_id: str) -> None:
        record = self._records.get(plugin_id)
        if record is None:
            raise ValueError(f"SDK plugin not found: {plugin_id}")
        record.state = SDK_STATE_DISABLED
        await self._cancel_plugin_requests(plugin_id)
        await self._teardown_plugin(plugin_id)
        record.failure_reason = ""
        self._set_disabled_override(plugin_id, disabled=True)

    async def turn_on_plugin(self, plugin_id: str) -> None:
        discovered = discover_plugins(self.plugins_dir)
        self.env_manager.plan(discovered.plugins)
        for load_order, plugin in enumerate(discovered.plugins):
            if plugin.name != plugin_id:
                continue
            self._set_disabled_override(plugin_id, disabled=False)
            await self._load_or_reload_plugin(
                plugin,
                load_order=load_order,
                reset_restart_budget=True,
            )
            return
        raise ValueError(f"SDK plugin not found: {plugin_id}")

    def list_plugins(self) -> list[dict[str, Any]]:
        records = sorted(self._records.values(), key=lambda item: item.load_order)
        return [self._record_to_dashboard_item(record) for record in records]

    def get_plugin_metadata(self, plugin_id: str) -> dict[str, Any] | None:
        record = self._records.get(plugin_id)
        if record is not None:
            manifest = record.plugin.manifest_data
            return {
                "name": plugin_id,
                "display_name": str(manifest.get("display_name") or plugin_id),
                "description": str(
                    manifest.get("desc") or manifest.get("description") or ""
                ),
                "author": str(manifest.get("author") or ""),
                "version": str(manifest.get("version") or "0.0.0"),
                "enabled": record.state not in {SDK_STATE_DISABLED, SDK_STATE_FAILED},
                "runtime_kind": "sdk",
            }
        for plugin in self.star_context.get_all_stars():
            if plugin.name == plugin_id:
                return {
                    "name": plugin.name,
                    "display_name": plugin.display_name,
                    "description": plugin.desc,
                    "author": plugin.author,
                    "version": plugin.version,
                    "enabled": plugin.activated,
                    "runtime_kind": "legacy",
                }
        return None

    def list_plugin_metadata(self) -> list[dict[str, Any]]:
        metadata = []
        for plugin in self.star_context.get_all_stars():
            metadata.append(
                {
                    "name": plugin.name,
                    "display_name": plugin.display_name,
                    "description": plugin.desc,
                    "author": plugin.author,
                    "version": plugin.version,
                    "enabled": plugin.activated,
                    "runtime_kind": "legacy",
                }
            )
        for plugin_id in sorted(self._records.keys()):
            plugin_metadata = self.get_plugin_metadata(plugin_id)
            if plugin_metadata is not None:
                metadata.append(plugin_metadata)
        return metadata

    def get_plugin_config(self, plugin_id: str) -> dict[str, Any] | None:
        record = self._records.get(plugin_id)
        if record is None:
            return None
        return dict(record.config)

    async def dispatch_message(self, event: AstrMessageEvent) -> SdkDispatchResult:
        result = SdkDispatchResult()
        if event.is_stopped():
            result.skipped_reason = SKIP_LEGACY_STOPPED
            return result
        if self._legacy_has_replied(event):
            result.skipped_reason = SKIP_LEGACY_REPLIED
            return result

        matches = self._match_handlers(event)
        if not matches:
            result.skipped_reason = SKIP_NO_MATCH
            return result
        result.matched_handlers = [
            {"plugin_id": match.plugin_id, "handler_id": match.handler_id}
            for match in matches
        ]

        dispatch_state = _DispatchState(event=event)
        skipped_reason = None
        for match in matches:
            record = self._records.get(match.plugin_id)
            if record is None:
                continue
            if record.state == SDK_STATE_RELOADING:
                skipped_reason = skipped_reason or SKIP_SDK_RELOADING
                continue
            if (
                record.state in {SDK_STATE_FAILED, SDK_STATE_DISABLED}
                or record.session is None
            ):
                skipped_reason = skipped_reason or SKIP_WORKER_FAILED
                continue

            request_id = f"sdk_{record.plugin_id}_{uuid.uuid4().hex}"
            dispatch_token = uuid.uuid4().hex
            payload = EventConverter.core_to_sdk(
                event,
                dispatch_token=dispatch_token,
                plugin_id=record.plugin_id,
                request_id=request_id,
            )
            task = asyncio.create_task(
                record.session.invoke_handler(
                    match.handler_id,
                    payload,
                    request_id=request_id,
                    args=match.args,
                )
            )
            request_context = _RequestContext(
                plugin_id=record.plugin_id,
                request_id=request_id,
                dispatch_token=dispatch_token,
                dispatch_state=dispatch_state,
            )
            self._request_contexts[dispatch_token] = request_context
            self._request_id_to_token[request_id] = dispatch_token
            self._plugin_requests.setdefault(record.plugin_id, {})[request_id] = (
                _InFlightRequest(
                    request_id=request_id,
                    dispatch_token=dispatch_token,
                    task=task,
                )
            )

            try:
                output = await task
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "SDK handler failed: plugin=%s handler=%s error=%s",
                    record.plugin_id,
                    match.handler_id,
                    exc,
                )
                skipped_reason = skipped_reason or SKIP_WORKER_FAILED
                output = {}
            finally:
                inflight = self._plugin_requests.get(record.plugin_id, {}).pop(
                    request_id,
                    None,
                )
                self._request_contexts.pop(dispatch_token, None)
                self._request_id_to_token.pop(request_id, None)

            if inflight is not None and inflight.logical_cancelled:
                continue

            handler_result = EventConverter.extract_handler_result(
                output if isinstance(output, dict) else {}
            )
            result.executed_handlers.append(
                {"plugin_id": record.plugin_id, "handler_id": match.handler_id}
            )
            dispatch_state.sent_message = (
                dispatch_state.sent_message or handler_result["sent_message"]
            )
            dispatch_state.stopped = dispatch_state.stopped or handler_result["stop"]
            if handler_result["stop"]:
                break

        result.sent_message = dispatch_state.sent_message
        result.stopped = dispatch_state.stopped
        if not result.executed_handlers:
            result.skipped_reason = skipped_reason or SKIP_NO_MATCH
        if result.sent_message:
            event._has_send_oper = True
            event.should_call_llm(True)
        if result.stopped:
            event.stop_event()
            event.should_call_llm(True)
        return result

    def resolve_request_plugin_id(self, request_id: str) -> str:
        token = self._request_id_to_token.get(request_id)
        if token is None or token not in self._request_contexts:
            raise AstrBotError.invalid_input(f"Unknown SDK request id: {request_id}")
        return self._request_contexts[token].plugin_id

    def resolve_request_session(self, request_id: str) -> _RequestContext | None:
        token = self._request_id_to_token.get(request_id)
        if token is None:
            return None
        return self._request_contexts.get(token)

    def get_request_context_by_token(
        self, dispatch_token: str
    ) -> _RequestContext | None:
        return self._request_contexts.get(dispatch_token)

    def before_platform_send(self, dispatch_token: str) -> None:
        request_context = self._request_contexts.get(dispatch_token)
        if request_context is None:
            raise AstrBotError.invalid_input(
                "Unknown SDK dispatch token for platform send"
            )
        if request_context.cancelled:
            raise AstrBotError.cancelled("The SDK request has been cancelled")

    def mark_platform_send(self, dispatch_token: str) -> str:
        request_context = self._request_contexts.get(dispatch_token)
        if request_context is None:
            raise AstrBotError.invalid_input(
                "Unknown SDK dispatch token for platform send"
            )
        if request_context.cancelled:
            raise AstrBotError.cancelled("The SDK request has been cancelled")
        request_context.dispatch_state.sent_message = True
        request_context.event._has_send_oper = True
        return f"sdk_{dispatch_token}"

    @staticmethod
    def _legacy_has_replied(event: AstrMessageEvent) -> bool:
        return getattr(event, "_has_send_oper", False)

    def _match_handlers(self, event: AstrMessageEvent) -> list[TriggerMatch]:
        matches: list[TriggerMatch] = []
        for record in self._records.values():
            if record.state in {SDK_STATE_DISABLED, SDK_STATE_FAILED}:
                continue
            for handler in record.handlers:
                match = TriggerConverter.match_handler(
                    plugin_id=record.plugin_id,
                    descriptor=handler.descriptor,
                    event=event,
                    load_order=record.load_order,
                    declaration_order=handler.declaration_order,
                )
                if match is not None:
                    matches.append(match)
        matches.sort(key=TriggerConverter.sort_key)
        return matches

    async def _load_or_reload_plugin(
        self,
        plugin: PluginSpec,
        *,
        load_order: int,
        reset_restart_budget: bool,
    ) -> None:
        current = self._records.get(plugin.name)
        if current is not None:
            current.state = SDK_STATE_RELOADING
            await self._cancel_plugin_requests(plugin.name)
            await self._teardown_plugin(plugin.name)

        disabled = bool(
            self._state_overrides.get(plugin.name, {}).get("disabled", False)
        )
        record = SdkPluginRecord(
            plugin=plugin,
            load_order=load_order,
            state=SDK_STATE_DISABLED if disabled else SDK_STATE_ENABLED,
            unsupported_features=[],
            config=load_plugin_config(plugin),
            handlers=[],
            restart_attempted=False
            if reset_restart_budget
            else (current.restart_attempted if current is not None else False),
        )
        self._records[plugin.name] = record
        if disabled:
            self._persist_state_overrides()
            return

        try:
            session = WorkerSession(
                plugin=plugin,
                repo_root=Path(__file__).resolve().parents[3],
                env_manager=self.env_manager,
                capability_router=self.capability_bridge,
                on_closed=lambda plugin_id=plugin.name: asyncio.create_task(
                    self._handle_worker_closed(plugin_id)
                ),
            )
            await session.start()
            session.start_close_watch()
            record.session = session
            unsupported_features: set[str] = set()
            for index, descriptor in enumerate(session.handlers):
                if isinstance(descriptor.trigger, EventTrigger):
                    unsupported_features.add("event_trigger")
                if isinstance(descriptor.trigger, ScheduleTrigger):
                    unsupported_features.add("schedule_trigger")
                record.handlers.append(
                    SdkHandlerRef(
                        descriptor=descriptor,
                        declaration_order=index,
                    )
                )
            record.unsupported_features = sorted(unsupported_features)
            record.state = (
                SDK_STATE_UNSUPPORTED_PARTIAL
                if record.unsupported_features
                else SDK_STATE_ENABLED
            )
            record.failure_reason = ""
        except Exception as exc:
            record.session = None
            record.state = SDK_STATE_FAILED
            record.failure_reason = str(exc)
            logger.warning("Failed to start SDK plugin %s: %s", plugin.name, exc)
        finally:
            self._persist_state_overrides()

    async def _teardown_plugin(self, plugin_id: str) -> None:
        record = self._records.get(plugin_id)
        if record is None or record.session is None:
            return
        try:
            await record.session.stop()
        finally:
            record.session = None

    async def _cancel_plugin_requests(self, plugin_id: str) -> None:
        requests = list(self._plugin_requests.get(plugin_id, {}).values())
        for inflight in requests:
            request_context = self._request_contexts.get(inflight.dispatch_token)
            if request_context is not None:
                request_context.cancelled = True
            record = self._records.get(plugin_id)
            if (
                record is not None
                and record.session is not None
                and record.session.peer is not None
                and not inflight.task.done()
            ):
                try:
                    await record.session.cancel(inflight.request_id)
                except Exception:
                    logger.debug(
                        "Failed to forward SDK cancel for %s", inflight.request_id
                    )
                inflight.task.cancel()
            else:
                inflight.logical_cancelled = True
        self._plugin_requests.pop(plugin_id, None)

    async def _handle_worker_closed(self, plugin_id: str) -> None:
        if self._stopping:
            return
        record = self._records.get(plugin_id)
        if record is None:
            return
        record.session = None
        if record.state in {SDK_STATE_RELOADING, SDK_STATE_DISABLED}:
            return
        if not record.restart_attempted:
            record.restart_attempted = True
            logger.warning(
                "SDK plugin worker closed unexpectedly, retrying once: %s",
                plugin_id,
            )
            await self._load_or_reload_plugin(
                record.plugin,
                load_order=record.load_order,
                reset_restart_budget=False,
            )
            return
        record.state = SDK_STATE_FAILED

    def _record_to_dashboard_item(self, record: SdkPluginRecord) -> dict[str, Any]:
        manifest = record.plugin.manifest_data
        installed_at = None
        try:
            installed_at = datetime.fromtimestamp(
                record.plugin.plugin_dir.stat().st_mtime,
                timezone.utc,
            ).isoformat()
        except OSError:
            installed_at = None
        handlers = [
            self._handler_to_dashboard_item(handler) for handler in record.handlers
        ]
        return {
            "name": record.plugin_id,
            "repo": "",
            "author": str(manifest.get("author") or ""),
            "desc": str(manifest.get("desc") or manifest.get("description") or ""),
            "version": str(manifest.get("version") or "0.0.0"),
            "reserved": False,
            "activated": record.state not in {SDK_STATE_DISABLED, SDK_STATE_FAILED},
            "online_vesion": "",
            "handlers": handlers,
            "display_name": str(manifest.get("display_name") or record.plugin_id),
            "logo": None,
            "support_platforms": [],
            "astrbot_version": "",
            "installed_at": installed_at,
            "runtime_kind": "sdk",
            "source_kind": "local_dir",
            "managed_by": "sdk_bridge",
            "state": record.state,
            "trigger_summary": [item["cmd"] for item in handlers],
            "unsupported_features": list(record.unsupported_features),
            "failure_reason": record.failure_reason,
        }

    def _handler_to_dashboard_item(self, handler: SdkHandlerRef) -> dict[str, Any]:
        base = {
            "event_type": "SDKMessageEvent",
            "event_type_h": "SDK 消息触发",
            "handler_full_name": handler.handler_id,
            "desc": "SDK handler",
            "handler_name": handler.handler_name,
            "has_admin": handler.descriptor.permissions.require_admin,
        }
        trigger = handler.descriptor.trigger
        if isinstance(trigger, CommandTrigger):
            return {**base, "type": "指令", "cmd": trigger.command}
        if isinstance(trigger, MessageTrigger):
            if trigger.regex:
                return {**base, "type": "正则匹配", "cmd": trigger.regex}
            if trigger.keywords:
                return {**base, "type": "关键词", "cmd": ", ".join(trigger.keywords)}
            return {**base, "type": "消息", "cmd": "任意消息"}
        if isinstance(trigger, EventTrigger):
            return {**base, "type": "事件", "cmd": trigger.event_type}
        if isinstance(trigger, ScheduleTrigger):
            return {
                **base,
                "type": "定时",
                "cmd": trigger.cron or str(trigger.interval_seconds),
            }
        return {**base, "type": "未知", "cmd": "未知"}

    def _load_state_overrides(self) -> dict[str, dict[str, Any]]:
        if not self.state_path.exists():
            return {}
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        plugins = data.get("plugins")
        return dict(plugins) if isinstance(plugins, dict) else {}

    def _persist_state_overrides(self) -> None:
        self.state_path.write_text(
            json.dumps(
                {"plugins": self._state_overrides}, ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )

    def _set_disabled_override(self, plugin_id: str, *, disabled: bool) -> None:
        plugin_state = dict(self._state_overrides.get(plugin_id, {}))
        if disabled:
            plugin_state["disabled"] = True
            self._state_overrides[plugin_id] = plugin_state
        else:
            plugin_state.pop("disabled", None)
            if plugin_state:
                self._state_overrides[plugin_id] = plugin_state
            else:
                self._state_overrides.pop(plugin_id, None)
        self._persist_state_overrides()
