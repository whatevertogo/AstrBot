## Known surprises

- `astrbot/core/sdk_bridge/event_converter.py` originally tried to stash the live `AstrMessageEvent` object into SDK payloads. That payload crosses the worker protocol boundary and must stay JSON-serializable.
- `astrbot_sdk/runtime/supervisor.py` and `WorkerSession.invoke_handler()` originally dropped `args` when forwarding `handler.invoke`. Command/regex parameter injection therefore worked in `astrbot_sdk.testing.PluginHarness`, but silently broke in the real subprocess runtime.
- `astrbot_sdk.events.MessageEvent.reply()` rebuilds `SessionRef.raw` from the full event payload, so the core bridge cannot assume `target.raw.dispatch_token` is top-level. In real subprocess runs the token may be nested under `target.raw.raw.dispatch_token`.
