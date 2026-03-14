# Code Review — feat/sdk-integration

## Summary
Files reviewed: 41 | New issues: 12 (0 critical, 3 high, 5 medium, 4 low) | Perspectives: 4/4

---

## 🔒 Security

**未发现满足条件的安全漏洞。**

审查了以下安全敏感区域：
- 危险函数使用（eval/exec/pickle）：未发现
- 环境变量处理：预期行为
- 子进程命令构建：参数内部可控，无注入风险
- 模板渲染：有输入净化
- 路径遍历：有 `_path_within_root` 防护
- JSON/YAML 解析：使用安全 API（`yaml.safe_load`）

---

## 📝 Code Quality

| Sev | Issue | File:Line | Consequence |
|-----|-------|-----------|-------------|
| **High** | 缺失模块导致 ImportError | `astrbot/core/sdk_bridge/__init__.py` | 应用无法启动 |
| Medium | 属性名不一致 (`stop` vs `stopped`) | `event_converter.py:53` vs `stage.py:236` | 运行时 AttributeError |
| Low | WebSocket 竞态条件 | `transport.py:10371-10382` | 极端并发下状态不一致 |
| Low | Windows 信号处理限制未完全处理 | `supervisor.py:9366-9372` | Windows 上优雅关闭可能失效 |

**详细分析**:

### [CODE-001] 缺失模块导致 ImportError（严重）

`__init__.py` 导入了三个模块但 diff 中未包含：
```python
from .capability_bridge import CoreCapabilityBridge
from .plugin_bridge import SdkPluginBridge
from .trigger_converter import TriggerConverter
```

根据实际文件检查，这些文件**已存在**于工作目录中（属于未跟踪文件），但不在 diff 中。这意味着代码实际上是完整的，只是 diff 未包含所有文件。

**建议**: 确保所有相关文件都被添加到 git 并包含在 PR 中。

### [CODE-002] 属性名不一致

`EventConverter.extract_handler_result` 返回 `"stop"` 键，但 `stage.py` 访问 `stopped` 属性。

---

## ✅ Tests

**Run results**: 现有测试 `test_sdk_bridge.py` 仅 3 个用例

| Sev | Untested scenario | Location |
|-----|------------------|----------|
| **High** | SDK 模块核心路径未测试 | `astrbot_sdk/runtime/` |
| **High** | `SdkPluginBridge.dispatch_message` 核心流程 | `plugin_bridge.py:244-357` |
| **High** | `CoreCapabilityBridge` 能力实现 | `capability_bridge.py` |
| **High** | Supervisor/Worker 进程通信 | `supervisor.py`, `worker.py` |
| **High** | Peer 握手和协议版本协商 | `peer.py` |
| Medium | `TriggerConverter` 分支覆盖不完整 | `trigger_converter.py` |
| Medium | `EventConverter` 转换逻辑 | `event_converter.py` |
| Medium | Transport 层（Stdio/WebSocket） | `transport.py` |
| Medium | CoreLifecycle SDK 集成 | `core_lifecycle.py` |
| Medium | ProcessStage SDK dispatch | `stage.py` |

**建议优先添加**:
1. `SdkPluginBridge.dispatch_message` 单元测试
2. `CoreCapabilityBridge` 能力实现测试（使用 mock）
3. `SupervisorRuntime` 与 `WorkerSession` 集成测试

---

## 🏗️ Architecture

| Sev | Inconsistency | Files |
|-----|--------------|-------|
| **High** | Memory 能力 Core 端未实现 | `capability_bridge.py` |
| Medium | PyYAML 依赖未显式声明 | `pyproject.toml` |
| Medium | SDK CLI 入口点未添加 | `pyproject.toml` |
| Medium | 文档能力映射表状态过时 | `SDK_INTEGRATION_PLAN.md` |
| Low | 缺少 py.typed 标记文件 | `astrbot_sdk/` |
| Low | CancelToken 类型未导出 | `__init__.py` |

**详细分析**:

### [ARCH-001] Memory 能力 Core 端未实现

SDK 端 `MemoryClient` 暴露了完整的 `memory.*` API，但 Core 端 `CoreCapabilityBridge` 未实现 `_register_memory_capabilities()`，导致使用父类的默认字典存储而非 Core 的持久化存储。

**建议**: 实现 `_register_memory_capabilities()` 或在 MVP 阶段返回"不支持"错误。

### [ARCH-002] SDK CLI 入口点未添加

`pyproject.toml` 的 `[project.scripts]` 仅定义了 `astrbot`，未定义 `astrbot-sdk`。

**修复**:
```toml
[project.scripts]
astrbot = "astrbot.cli.__main__:cli"
astrbot-sdk = "astrbot_sdk.cli:cli"
```

---

## 🚨 Must Fix Before Merge

1. **[CODE-001]** 确保所有 SDK bridge 模块文件已添加到 git — `astrbot/core/sdk_bridge/`
   - Impact: 缺失文件会导致应用无法启动
   - Fix: `git add astrbot/core/sdk_bridge/capability_bridge.py plugin_bridge.py trigger_converter.py`

2. **[CODE-002]** 属性名不一致 (`stop` vs `stopped`) — `event_converter.py` + `stage.py`
   - Impact: 运行时 AttributeError
   - Fix: 统一命名

3. **[ARCH-001]** Memory 能力 Core 端未实现 — `capability_bridge.py`
   - Impact: 使用非持久化存储
   - Fix: 实现或返回"不支持"

4. **[TEST-001]** SDK 模块缺少测试覆盖 — `astrbot_sdk/`
   - Impact: 无法验证实现正确性
   - Fix: 添加核心路径测试

---

## 📎 Pre-Existing Issues (not blocking)

- `astrbot/core/star/context.py` 中 `Context` 类已很大，添加 `sdk_plugin_bridge` 增加了耦合
- `.serena/` 目录应添加到 `.gitignore`

---

## 🤔 Low-Confidence Observations

1. `peer.py` 协议版本协商逻辑复杂，可能有边缘情况未覆盖
2. `loader.py` `_purge_plugin_modules` 可能无法正确清理嵌套导入
3. `plugin_bridge.py` `dispatch_message` 返回 `SdkDispatchResult` 但调用方可能未正确处理所有状态
4. WebSocket 竞态条件在实际场景中触发概率极低

---

## 📊 Review Statistics

- **Total lines added**: 12,391
- **Total lines deleted**: 4
- **Files reviewed**: 41
- **Perspectives applied**: Security, Code Quality, Tests, Architecture
- **Confidence level**: High

---

## ✅ Positive Findings

1. **良好的安全实践**: 使用安全 API，有输入净化和路径遍历防护
2. **清晰的架构设计**: SDK 与 Core 分离，进程隔离架构设计合理
3. **完整的协议定义**: 消息模型定义完整，Core 与 SDK 端一致
4. **良好的错误处理**: 统一的 `AstrBotError` 错误模型
5. **生命周期管理完整**: start/stop/reload 流程设计清晰
