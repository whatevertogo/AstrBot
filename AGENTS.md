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
