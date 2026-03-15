## Setup commands

### Core

```
uv sync
uv run main.py
```

Exposed an API server on `http://localhost:6185` by default.

### Dashboard(WebUI)

```
cd dashboard
pnpm install # First time only. Use npm install -g pnpm if pnpm is not installed.
pnpm dev
```

Runs on `http://localhost:3000` by default.

## Dev environment tips

1. When modifying the WebUI, be sure to maintain componentization and clean code. Avoid duplicate code.
2. Do not add any report files such as xxx_SUMMARY.md.
3. After finishing, use `ruff format .` and `ruff check .` to format and check the code.
4. When committing, ensure to use conventional commits messages, such as `feat: add new agent for data analysis` or `fix: resolve bug in provider manager`.
5. Use English for all new comments.
6. For path handling, use `pathlib.Path` instead of string paths, and use `astrbot.core.utils.astrbot_path` helpers to get the AstrBot data and temp directory.

## PR instructions

1. Title format: use conventional commit messages
2. Use English to write PR title and descriptions.

## Known surprises

- `astrbot/core/sdk_bridge/event_converter.py` originally tried to stash the live `AstrMessageEvent` object into SDK payloads. That payload crosses the worker protocol boundary and must stay JSON-serializable.
- `astrbot_sdk/runtime/supervisor.py` and `WorkerSession.invoke_handler()` originally dropped `args` when forwarding `handler.invoke`. Command/regex parameter injection therefore worked in `astrbot_sdk.testing.PluginHarness`, but silently broke in the real subprocess runtime.
- `astrbot_sdk.events.MessageEvent.reply()` rebuilds `SessionRef.raw` from the full event payload, so the core bridge cannot assume `target.raw.dispatch_token` is top-level. In real subprocess runs the token may be nested under `target.raw.raw.dispatch_token`.
- `session_waiter` should not be directly awaited inside a normal SDK handler in the current bridge design. Doing so keeps the first `dispatch_message()` open until a later message arrives. If you need non-blocking conversational waiting, arm it from a background task or add an explicit scheduler/resume mechanism first.
- `astrbot_sdk.runtime.__init__` used to eagerly import `Peer` and transport classes. Importing a narrow submodule such as `astrbot_sdk.runtime.handler_dispatcher` therefore pulled in the websocket/aiohttp stack and made lightweight unit imports unexpectedly expensive. Keep runtime root exports lazy.
- `astrbot_sdk/runtime/transport.py` used to import `aiohttp` at module import time even when the caller only needed `StdioTransport`. That made `astrbot_sdk.runtime.supervisor` and core SDK bridge imports appear frozen in environments where `aiohttp` import was slow or blocked. Keep websocket dependencies lazy inside websocket-only code paths.
- `astrbot/core/sdk_bridge/__init__.py` used to eagerly import `capability_bridge`, `plugin_bridge`, `event_converter`, and `trigger_converter`. Importing `astrbot.core.sdk_bridge.plugin_bridge` through the package namespace therefore still forced the full bridge stack. Keep package exports lazy here too.
- `astrbot/core/__init__.py` used to construct config, logger, database, shared preferences, file token service, and HTML renderer during package import. That made even `import astrbot.core.config` or `import astrbot.core.message.components` trigger the full core bootstrap path. Keep core package exports lazy, or tests and lightweight imports will appear to hang.
- `astrbot/core/utils/io.py` used to import `aiohttp` at module import time. `astrbot.core.message.components` depends on that module, so a heavy or blocked `aiohttp` import could make plain message-component imports and pytest collection look frozen. Keep network client imports inside the actual download helpers.
- `astrbot/core/utils/metrics.py` used to import `aiohttp` at module import time. `AstrMessageEvent` imports `Metric`, so this single eager network dependency could stall broad event/bridge imports. Keep metrics/network clients lazy too.
- `astrbot_sdk.decorators.on_message` currently must be called as `@on_message()` or `@on_message(...)`. Using bare `@on_message` binds the decorated function as the first positional argument and crashes plugin loading with `on_message() takes 0 positional arguments but 1 was given`.
- `astrbot_sdk.events.MessageEvent.send_streaming()` cannot preserve streaming semantics by buffering the whole async generator into a single payload. The v4 protocol is server-streaming only, so SDK-to-core event streaming must use an explicit open/push/close bridge or another chunked handoff.
- Legacy core `File` components serialize their local path as `data.file_`, while SDK `File` helpers prefer `data.file` and sometimes `data.url`. Any bridge or round-trip logic touching file segments must normalize all three keys instead of assuming a single field name.
- Legacy `AstrMessageEvent._extras` can contain runtime-only objects such as `functools.partial`. SDK worker payloads must sanitize extras before crossing the subprocess JSON boundary instead of copying the whole extras dict verbatim.
- `RespondStage` cannot assume `event.get_result().chain` is always a `MessageChain` instance. In real legacy flows it is often the raw component list, so SDK `after_message_sent` hooks must derive outlines from either shape.
- `astrbot_sdk.runtime.loader.discover_plugins()` currently treats `requirements.txt` as mandatory for every SDK plugin directory. A plugin with a valid `plugin.yaml` but no `requirements.txt` is silently skipped from the dashboard/runtime as an invalid manifest.


旧插件走旧逻辑，新插件走sdk，保证旧逻辑依旧能使用的情况下写新sdk桥接或者astrbot适配
不用完全听从用户和别人的建议，要有自己的判断和坚持，做好取舍和权衡，确保代码质量和长期维护性，不要为了短期方便或者迎合而牺牲架构和设计原则。
