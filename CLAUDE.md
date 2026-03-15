## Known surprises

- `astrbot/core/sdk_bridge/event_converter.py` originally tried to stash the live `AstrMessageEvent` object into SDK payloads. That payload crosses the worker protocol boundary and must stay JSON-serializable.
- `astrbot_sdk/runtime/supervisor.py` and `WorkerSession.invoke_handler()` originally dropped `args` when forwarding `handler.invoke`. Command/regex parameter injection therefore worked in `astrbot_sdk.testing.PluginHarness`, but silently broke in the real subprocess runtime.
- `astrbot_sdk.events.MessageEvent.reply()` rebuilds `SessionRef.raw` from the full event payload, so the core bridge cannot assume `target.raw.dispatch_token` is top-level. In real subprocess runs the token may be nested under `target.raw.raw.dispatch_token`.
- `session_waiter` should not be directly awaited inside a normal SDK handler in the current bridge design. Doing so keeps the first `dispatch_message()` open until a later message arrives. If you need non-blocking conversational waiting, arm it from a background task or add an explicit scheduler/resume mechanism first.
