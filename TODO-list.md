# SDK Parity TODO List

目标：让新 `astrbot_sdk` 在能力上可以完整替代 legacy 插件系统。

说明：
- 只列出 SDK 插件开发者真正需要调用的 API
- 不包含 Core 内部实现细节
- **状态标记**：✅ 已实现 | 🔄 部分实现 | ❌ 未实现 | ⚠️ Core端未支持

---

## 📊 覆盖率总览

| 模块 | 总计 | ✅ | 🔄 | ❌ | ⚠️ | 覆盖率 |
| --- | --- | --- | --- | --- | --- | --- |
| LLM Client | 7 | 3 | 3 | 0 | 1 | 64% |
| DB Client (KV) | 7 | 6 | 0 | 0 | 1 | 86% |
| Platform Client | 6 | 4 | 1 | 1 | 0 | 75% |
| Metadata Client | 4 | 4 | 0 | 0 | 0 | 100% |
| Memory Client | 8 | 0 | 0 | 0 | 8 | 0% |
| HTTP Client | 3 | 0 | 0 | 0 | 3 | 0% |
| MessageEvent | 30 | 9 | 1 | 20 | 0 | 32% |
| 装饰器/触发器 | 17 | 6 | 2 | 5 | 4 | 41% |
| 事件类型 | 14 | 1 | 0 | 13 | 0 | 7% |
| 消息组件 | 13 | 2 | 0 | 11 | 0 | 15% |
| Legacy Context | 22 | 4 | 2 | 16 | 0 | 23% |
| 工具方法 | 6 | 0 | 0 | 6 | 0 | 0% |
| 会话控制 | 5 | 0 | 0 | 5 | 0 | 0% |
| 过滤器 | 5 | 0 | 0 | 5 | 0 | 0% |
| 高级管理器 | 12 | 0 | 0 | 12 | 0 | 0% |
| Provider管理 | 12 | 0 | 0 | 12 | 0 | 0% |
| Provider实体 | 10 | 0 | 0 | 10 | 0 | 0% |
| TTS/STT/Embedding | 6 | 0 | 0 | 6 | 0 | 0% |
| Platform实体 | 6 | 0 | 0 | 6 | 0 | 0% |
| Agent运行器 | 7 | 0 | 0 | 7 | 0 | 0% |
| SDK扩展能力 | 19 | 0 | 0 | 19 | 0 | 0% |
| 其他系统能力 | 52 | 7 | 0 | 44 | 1 | 13% |
| **Star基类扩展** | **8** | **1** | **2** | **5** | **0** | **25%** |
| **命令参数类型** | **8** | **1** | **0** | **7** | **0** | **12%** |
| **过滤器组合** | **5** | **0** | **0** | **5** | **0** | **0%** |
| **StarTools工具集** | **10** | **0** | **0** | **10** | **0** | **0%** |
| **会话级管理** | **6** | **0** | **0** | **6** | **0** | **0%** |
| **命令组系统** | **9** | **0** | **0** | **9** | **0** | **0%** |
| **消息类型过滤** | **7** | **0** | **0** | **7** | **0** | **0%** |
| **PluginKVStoreMixin** | **5** | **0** | **0** | **5** | **0** | **0%** |
| **StarMetadata字段** | **2** | **0** | **0** | **2** | **0** | **0%** |
| **总计** | **271** | **40** | **9** | **209** | **18** | **16%** |

> 注：覆盖率 = `(已实现 + 部分实现 × 0.5) / 总计`，⚠️ 表示SDK已定义但Core端未实现

---

## 更新记录

### 2025-03-15 更新
- 新增 Star基类扩展方法对比（P2.5）
- 新增 命令参数类型系统对比（P2.6）
- 新增 过滤器组合与自定义对比（P2.7）
- 新增 事件系统细节对比（P2.8）
- 新增 平台适配器类型系统（P2.9）
- 新增 StarTools工具集对比（P2.10）
- 新增 会话级插件管理对比（P2.11）
- 新增 命令组系统对比（P2.12）
- 新增 消息类型过滤对比（P2.13）
- 新增 PluginKVStoreMixin对比（P2.14）
- 新增 StarMetadata完整字段对比（P2.15）
- 更新覆盖率总览表格

### 2026-03-15 更新
- LLM Client 新增 `provider_id` / `contexts` / `tool_calls_result` 能力登记
- `llm.stream_chat` 改为真实流式优先，只有 `NotImplementedError` 才降级
- 补充 `Context` / `MessageEvent` / 平台错误跟踪 / 会话级 LLM/TTS 开关等缺口

---

---

## SDK Client 方法

### LLMClient

| 方法 | 状态 | 说明 |
| --- | --- | --- |
| `chat(prompt, system?, history?, model?, temperature?)` | ✅ | 发送聊天，返回文本 |
| `chat_raw(prompt, ...)` | ✅ | 返回完整响应（含 usage、tool_calls，兼容 `role/reasoning_*` 可选扩展） |
| `stream_chat(prompt, ...)` | ✅ | 真实流式优先，仅 `NotImplementedError` 时降级为完整响应切片流 |
| `chat(image_urls=[...])` | 🔄 | 多模态：图片输入 |
| `chat(tools=[...])` | 🔄 | 工具调用 |
| `chat(contexts=[...])` | ✅ | 自定义上下文，且优先于 `history` |
| `chat(provider_id="...")` | ✅ | 显式指定聊天 Provider |
| `chat(tool_calls_result=[...])` | 🔄 | 工具执行结果透传，不校验 tool_call 语义一致性 |
| `chat(audio_urls=[...])` | ❌ | 多模态：音频输入 |

### DBClient (KV 存储)

| 方法 | 状态 | 说明 |
| --- | --- | --- |
| `get(key)` | ✅ | 获取值 |
| `set(key, value)` | ✅ | 设置值 |
| `delete(key)` | ✅ | 删除键 |
| `list(prefix?)` | ✅ | 列出键 |
| `get_many(keys)` | ✅ | 批量获取 |
| `set_many(items)` | ✅ | 批量设置 |
| `watch(prefix?)` | ⚠️ | 订阅变更（SDK已定义，Core端MVP不支持） |

### PlatformClient

| 方法 | 状态 | 说明 |
| --- | --- | --- |
| `send(session, text)` | ✅ | 发送文本 |
| `send_image(session, url)` | ✅ | 发送图片 |
| `send_chain(session, chain)` | ✅ | 发送消息链 |
| `get_members(session)` | 🔄 | 获取群成员（依赖Core端event.get_group()） |
| `send_by_id(platform_id, session_id, ...)` | ❌ | 根据ID发送消息（跨会话发送） |
| `send_by_session(session, chain)` | ❌ | 通过可持久化会话数据发送消息 |

### MetadataClient

| 方法 | 状态 | 说明 |
| --- | --- | --- |
| `get_plugin(name)` | ✅ | 获取插件信息 |
| `list_plugins()` | ✅ | 列出所有插件 |
| `get_current_plugin()` | ✅ | 获取当前插件 |
| `get_plugin_config(name?)` | ✅ | 获取插件配置 |

### MemoryClient

| 方法 | 状态 | 说明 |
| --- | --- | --- |
| `search(query, top_k?)` | ⚠️ | 语义搜索（SDK已定义，Core端用简单字符串匹配实现） |
| `save(key, value)` | ⚠️ | 保存记忆（SDK已定义，Core端MVP不支持） |
| `save_with_ttl(key, value, ttl)` | ⚠️ | 保存（带过期）（SDK已定义，TTL仅记录但不实际过期） |
| `get(key)` | ⚠️ | 获取记忆（SDK已定义，Core端MVP不支持） |
| `get_many(keys)` | ⚠️ | 批量获取（SDK已定义，Core端MVP不支持） |
| `delete(key)` | ⚠️ | 删除记忆（SDK已定义，Core端MVP不支持） |
| `delete_many(keys)` | ⚠️ | 批量删除（SDK已定义，Core端MVP不支持） |
| `stats()` | ⚠️ | 统计信息（SDK已定义，Core端MVP不支持） |

### HTTPClient

| 方法 | 状态 | 说明 |
| --- | --- | --- |
| `register_api(route, handler, methods?)` | ⚠️ | 注册 API（SDK已定义，Core端MVP不支持） |
| `unregister_api(route)` | ⚠️ | 注销 API（SDK已定义，Core端MVP不支持） |
| `list_apis()` | ⚠️ | 列出已注册 API（SDK已定义，Core端MVP不支持） |

---

## MessageEvent

| 属性/方法 | 状态 | 说明 |
| --- | --- | --- |
| `text` | ✅ | 消息文本 |
| `platform` | ✅ | 平台名称 |
| `session_id` | ✅ | 会话 ID |
| `user_id` | ✅ | 发送者 ID |
| `group_id` | ✅ | 群组 ID |
| `raw` | ✅ | 原始数据 |
| `reply(text)` | ✅ | 回复文本 |
| `reply_image(url)` | ✅ | 回复图片 |
| `reply_chain(chain)` | ✅ | 回复消息链 |
| `plain_result(text)` | ✅ | 创建纯文本结果 |
| `platform_id` | ❌ | 平台实例 ID |
| `message_type` | ❌ | 消息类型（group/private） |
| `self_id` | ❌ | 机器人 ID |
| `sender_name` | ❌ | 发送者名称 |
| `unified_msg_origin` | ❌ | 统一消息来源字符串 |
| `is_private_chat()` | ❌ | 是否私聊 |
| `is_admin()` | ❌ | 是否管理员 |
| `is_wake_up()` | ❌ | 是否唤醒 |
| `stop_event()` | ❌ | 停止传播 |
| `continue_event()` | ❌ | 继续传播 |
| `is_stopped()` | ❌ | 是否已停止 |
| `get_messages()` | ❌ | 获取消息链 |
| `get_message_outline()` | ❌ | 获取消息概要 |
| `react(emoji)` | ❌ | 表情回应 |
| `send_typing()` | ❌ | 输入中状态 |
| `send_streaming()` | ❌ | 流式发送消息 |
| `set_extra(k, v)` | ❌ | 设置额外信息 |
| `get_extra(k?)` | ❌ | 获取额外信息 |
| `clear_extra()` | ❌ | 清除额外信息 |
| `image_result(url)` | ❌ | 创建图片结果 |
| `chain_result(chain)` | ❌ | 创建消息链结果 |
| `get_group()` | ❌ | 获取群聊数据 |
| `request_llm()` | ❌ | 触发默认 LLM 请求 |
| `set_result()` | ❌ | 设置处理结果 |
| `get_result()` | ❌ | 获取处理结果 |
| `clear_result()` | ❌ | 清空处理结果 |
| `make_result()` | ❌ | 构造标准结果对象 |
| `should_call_llm()` | ❌ | 标记/查询是否继续默认 LLM |
| `get_platform_id()` | ❌ | 获取平台实例 ID |
| `get_message_type()` | ❌ | 获取消息类型 |
| `get_session_id()` | ❌ | 获取会话 ID |

---

## 装饰器/触发器

| 装饰器 | 状态 | 说明 |
| --- | --- | --- |
| `@on_command("cmd")` | ✅ | 命令触发 |
| `@on_message(regex="...")` | ✅ | 正则触发 |
| `@on_message(keywords=[...])` | ✅ | 关键词触发 |
| `@require_admin` | ✅ | 管理员权限 |
| `@provide_capability(...)` | ✅ | 声明能力 |
| `@on_command(aliases=[...])` | 🔄 | 命令别名 |
| `@on_message(platforms=[...])` | 🔄 | 平台过滤 |
| `@on_event("type")` | ⚠️ | 事件触发（SDK已定义，Core端MVP不支持） |
| `@on_schedule(cron="...")` | ⚠️ | Cron 定时（SDK已定义，Core端MVP不支持） |
| `@on_schedule(interval_seconds=N)` | ⚠️ | 间隔定时（SDK已定义，Core端MVP不支持） |
| `@on_message(message_types=[...])` | ❌ | 消息类型过滤（GROUP/PRIVATE/OTHER） |
| `@register_llm_tool()` | ❌ | LLM 工具注册 |
| `@register_agent()` | ❌ | Agent 注册 |
| `@session_waiter(timeout=30)` | ❌ | 会话等待装饰器 |
| `@custom_filter` | ❌ | 自定义过滤器 |
| 命令组/子命令 | ❌ | 子命令路由（CommandGroupFilter） |
| 命令参数类型解析 | ❌ | 自动解析 int/float/bool/str 类型参数 |

---

## 事件类型

| 事件 | 状态 | 说明 |
| --- | --- | --- |
| 消息事件 | ✅ | `@on_command`, `@on_message` |
| astrbot_loaded | ❌ | Core 启动完成 |
| platform_loaded | ❌ | 平台连接成功 |
| waiting_llm_request | ❌ | 准备调用 LLM（获取锁之前通知） |
| llm_request | ❌ | LLM 请求开始 |
| llm_response | ❌ | LLM 响应完成 |
| decorating_result | ❌ | 发送前装饰 |
| calling_func_tool | ❌ | 函数工具调用 |
| using_llm_tool | ❌ | LLM 工具使用 |
| llm_tool_respond | ❌ | LLM 工具响应 |
| after_message_sent | ❌ | 消息发送后 |
| plugin_error | ❌ | 插件错误 |
| plugin_loaded | ❌ | 插件加载 |
| plugin_unloaded | ❌ | 插件卸载 |

---

## 消息组件

| 组件 | 状态 | 说明 |
| --- | --- | --- |
| Plain (文本) | ✅ | 已支持 |
| Image (图片) | ✅ | 已支持 |
| **At (@某人)** | ❌ | @提及 |
| **AtAll (@全体)** | ❌ | @全体成员 |
| **Reply (引用)** | ❌ | 引用回复 |
| **Record (语音)** | ❌ | 语音消息 |
| **Video (视频)** | ❌ | 视频消息 |
| **File (文件)** | ❌ | 文件附件 |
| **Face (表情)** | ❌ | QQ 表情 |
| **Forward (转发)** | ❌ | 合并转发 |
| **Poke (戳一戳)** | ❌ | 戳一戳动作 |
| **Node (转发节点)** | ❌ | 合并转发节点 |
| **Nodes (多节点)** | ❌ | 多个转发节点 |
| **Json (JSON)** | ❌ | JSON 消息 |
| **RPS (猜拳)** | ❌ | 石头剪刀布 |
| **Dice (骰子)** | ❌ | 骰子消息 |
| **Shake (窗口抖动)** | ❌ | 窗口抖动 |
| **Share (分享)** | ❌ | 链接分享卡片 |
| **Contact (联系人)** | ❌ | 联系人推荐 |
| **Location (位置)** | ❌ | 地理位置 |
| **Music (音乐)** | ❌ | 音乐分享 |
| **WechatEmoji (微信表情)** | ❌ | 微信表情包 |

### 消息组件方法对比

| 方法/功能 | 旧系统状态 | 说明 |
| --- | --- | --- |
| `Image.fromURL()` | ✅ | 从URL创建图片 |
| `Image.fromFileSystem()` | ✅ | 从本地文件创建图片 |
| `Image.fromBase64()` | ✅ | 从Base64创建图片 |
| `Image.fromBytes()` | ✅ | 从字节创建图片 |
| `Image.convert_to_file_path()` | ❌ | 转换为本地文件路径 |
| `Image.convert_to_base64()` | ❌ | 转换为Base64编码 |
| `Image.register_to_file_service()` | ❌ | 注册到文件服务 |
| `Record.fromFileSystem()` | ❌ | 从文件系统创建语音 |
| `Record.fromURL()` | ❌ | 从URL创建语音 |
| `Record.convert_to_file_path()` | ❌ | 转换为本地文件路径 |
| `Record.register_to_file_service()` | ❌ | 注册到文件服务 |
| `Video.fromFileSystem()` | ❌ | 从文件系统创建视频 |
| `Video.fromURL()` | ❌ | 从URL创建视频 |
| `Video.convert_to_file_path()` | ❌ | 转换为本地文件路径 |
| `File.get_file()` | ❌ | 异步获取文件 |
| `File.register_to_file_service()` | ❌ | 注册到文件服务 |
| `Node` / `Nodes` | ❌ | 合并转发消息构造 |
| `toDict()` | ✅ | 同步转换为字典 |
| `to_dict()` | ✅ | 异步转换为字典 |

---

## Legacy Context 兼容

| Legacy 方法 | SDK 等价 | 状态 | 说明 |
| --- | --- | --- | --- |
| `llm_generate()` | `ctx.llm.chat()` | ✅ | 基本对话 |
| `get_registered_star()` | `ctx.metadata.get_plugin()` | ✅ | 获取插件 |
| `get_all_stars()` | `ctx.metadata.list_plugins()` | ✅ | 列出插件 |
| `get_config()` | `ctx.metadata.get_plugin_config()` | ✅ | 获取配置 |
| `send_message()` | `ctx.platform.send()` | ✅ | 发送消息 |
| `get_db()` | `ctx.db` | ✅ | 数据库 |
| `llm_generate(image_urls=...)` | `ctx.llm.chat(image_urls=...)` | 🔄 | 图片输入 |
| `llm_generate(tools=...)` | `ctx.llm.chat(tools=...)` | 🔄 | 工具调用 |
| `tool_loop_agent()` | 无 | ❌ | Agent 循环 |
| `get_llm_tool_manager()` | 无 | ❌ | 工具管理器 |
| `activate_llm_tool()` | 无 | ❌ | 激活工具 |
| `deactivate_llm_tool()` | 无 | ❌ | 停用工具 |
| `add_llm_tools()` | 无 | ❌ | 添加工具 |
| `get_using_provider()` | 无 | ❌ | 获取 Provider |
| `get_current_chat_provider_id()` | 无 | ❌ | 获取当前会话正在使用的聊天 Provider ID |
| `get_all_providers()` | 无 | ❌ | 列出 Provider |
| `get_all_tts_providers()` | 无 | ❌ | 列出 TTS Provider |
| `get_all_stt_providers()` | 无 | ❌ | 列出 STT Provider |
| `get_all_embedding_providers()` | 无 | ❌ | 列出 Embedding Provider |
| `get_using_tts_provider()` | 无 | ❌ | TTS Provider |
| `get_using_stt_provider()` | 无 | ❌ | STT Provider |
| `register_web_api()` | `ctx.http.register_api()` | ⚠️ | 注册 API（Core端不支持） |
| `register_commands()` | 无 | ❌ | 注册命令描述/帮助信息 |
| `register_task()` | 无 | ❌ | 注册后台任务 |
| `get_platform()` | 无 | ❌ | 获取平台 |
| `get_platform_inst()` | 无 | ❌ | 获取平台实例 |
| `get_event_queue()` | 无 | ❌ | 事件队列 |

---

## 工具方法

| 方法 | 状态 | 说明 |
| --- | --- | --- |
| `Star.text_to_image(text)` | ❌ | 文本转图片 |
| `Star.html_render(html)` | ❌ | HTML 渲染 |
| `get_data_dir()` | ❌ | 获取插件数据目录 |
| `create_message()` | ❌ | 创建消息对象 |
| `create_event()` | ❌ | 创建并提交事件 |
| `MessageChain.get_plain_text()` | ❌ | 获取消息链纯文本 |

---

## 会话控制（SessionWaiter）

| 类/方法 | 状态 | 说明 |
| --- | --- | --- |
| `SessionWaiter` | ❌ | 会话等待类 |
| `SessionController` | ❌ | 会话控制器 |
| `SessionController.stop()` | ❌ | 立即结束会话 |
| `SessionController.keep(timeout)` | ❌ | 保持会话 |
| `SessionController.get_history_chains()` | ❌ | 获取历史消息链 |
| `@session_waiter(timeout=30)` | ❌ | 会话等待装饰器 |

---

## 过滤器（Filter）

| 过滤器 | 状态 | 说明 |
| --- | --- | --- |
| `CustomFilter` | ❌ | 自定义过滤器基类 |
| `CustomFilter.__and__()` | ❌ | 过滤器与运算 |
| `CustomFilter.__or__()` | ❌ | 过滤器或运算 |
| `EventMessageTypeFilter` | ❌ | 消息类型过滤器（GROUP/PRIVATE/OTHER） |
| `PlatformAdapterTypeFilter` | ❌ | 平台适配器过滤器（支持15种平台） |

---

## 高级管理器

| 管理器/方法 | 状态 | 说明 |
| --- | --- | --- |
| **PersonaManager** | ❌ | 人格管理器 |
| `get_persona(persona_id)` | ❌ | 获取人格 |
| `get_all_personas()` | ❌ | 获取所有人格 |
| `create_persona(...)` | ❌ | 创建人格 |
| `update_persona(...)` | ❌ | 更新人格 |
| `delete_persona(persona_id)` | ❌ | 删除人格 |
| **ConversationManager** | ❌ | 对话管理器 |
| `new_conversation(umo)` | ❌ | 新建对话 |
| `switch_conversation(umo, cid)` | ❌ | 切换对话 |
| `delete_conversation(umo, cid)` | ❌ | 删除对话 |
| `get_conversation(umo, cid)` | ❌ | 获取对话 |
| `get_conversations(umo)` | ❌ | 获取对话列表 |
| `update_conversation(...)` | ❌ | 更新对话 |
| **KnowledgeBaseManager** | ❌ | 知识库管理器 |
| `get_kb(kb_id)` | ❌ | 获取知识库 |
| `create_kb(...)` | ❌ | 创建知识库 |
| `delete_kb(kb_id)` | ❌ | 删除知识库 |

---

## Provider 管理

| 方法 | 状态 | 说明 |
| --- | --- | --- |
| `set_provider(provider_id, type, umo)` | ❌ | 设置提供商 |
| `get_provider_by_id(provider_id)` | ❌ | 根据ID获取提供商实例 |
| `get_using_provider(type, umo)` | ❌ | 获取当前使用的提供商 |
| `load_provider(config)` | ❌ | 加载提供商 |
| `terminate_provider(provider_id)` | ❌ | 终止提供商 |
| `create_provider(config)` | ❌ | 创建提供商 |
| `update_provider(origin_id, config)` | ❌ | 更新提供商 |
| `delete_provider(provider_id)` | ❌ | 删除提供商 |
| `register_provider_change_hook(hook)` | ❌ | 注册提供商变更钩子 |
| `get_insts()` | ❌ | 获取所有提供商实例列表 |
| `get_merged_provider_config(config)` | ❌ | 获取合并后的提供商配置 |

### Provider 类型枚举

| 类型 | 状态 | 说明 |
| --- | --- | --- |
| `ProviderType.CHAT_COMPLETION` | ❌ | 聊天完成 |
| `ProviderType.SPEECH_TO_TEXT` | ❌ | 语音转文字 |
| `ProviderType.TEXT_TO_SPEECH` | ❌ | 文字转语音 |
| `ProviderType.EMBEDDING` | ❌ | 嵌入向量 |
| `ProviderType.RERANK` | ❌ | 重排序 |

---

## Provider 实体类

| 类 | 状态 | 说明 |
| --- | --- | --- |
| `ProviderMeta` | ❌ | 提供商元数据（id, model, type, provider_type） |
| `ProviderRequest` | ❌ | 提供商请求对象 |
| `TokenUsage` | ❌ | Token 使用统计 |
| `LLMResponse` (完整版) | ❌ | LLM 完整响应（含 result_chain, reasoning_content 等） |
| `ToolCallsResult` | ❌ | 工具调用结果 |
| `RerankResult` | ❌ | 重排序结果 |
| `MessageSession` | ❌ | 消息会话对象（platform_name, message_type, session_id） |
| `MessageSession.from_str()` | ❌ | 从字符串解析会话 |
| `Providers` 类型别名 | ❌ | Provider/STT/TTS/Embedding/Rerank 联合类型 |

---

## TTS/STT/Embedding Provider

| 方法 | 状态 | 说明 |
| --- | --- | --- |
| **STTProvider** | ❌ | 语音转文字提供商 |
| `get_text(audio_url)` | ❌ | 获取音频的文本 |
| **TTSProvider** | ❌ | 文字转语音提供商 |
| `get_audio(text)` | ❌ | 获取文本的音频（返回文件路径） |
| `get_audio_stream(text_q, audio_q)` | ❌ | 流式 TTS 处理 |
| `support_stream()` | ❌ | 是否支持流式 TTS |
| **EmbeddingProvider** | ❌ | 嵌入向量提供商 |
| **RerankProvider** | ❌ | 重排序提供商 |

---

## Platform 实体

| 类/方法 | 状态 | 说明 |
| --- | --- | --- |
| `PlatformStatus` 枚举 | ❌ | 平台状态（PENDING/RUNNING/ERROR/STOPPED） |
| `PlatformError` | ❌ | 平台错误信息 |
| `Platform.record_error()` | ❌ | 记录平台错误 |
| `Platform.last_error` | ❌ | 最近一次平台错误 |
| `Platform.errors` | ❌ | 平台错误历史 |
| `Platform.clear_errors()` | ❌ | 清空平台错误历史 |
| `Platform.send_by_session()` | ❌ | 通过会话发送消息 |
| `Platform.commit_event()` | ❌ | 提交事件到队列 |
| `Platform.get_client()` | ❌ | 获取平台客户端对象 |
| `Platform.get_stats()` | ❌ | 获取平台统计信息 |
| `Platform.unified_webhook()` | ❌ | 统一 Webhook 模式 |
| `Platform.webhook_callback()` | ❌ | Webhook 回调 |

---

## Agent 运行器

| 类/方法 | 状态 | 说明 |
| --- | --- | --- |
| `BaseAgentRunner` | ❌ | Agent 运行器基类 |
| `AgentState` 枚举 | ❌ | Agent 状态（IDLE/RUNNING/DONE/ERROR） |
| `reset(context, hooks)` | ❌ | 重置 Agent 状态 |
| `step()` | ❌ | 执行单步 |
| `step_until_done(max_step)` | ❌ | 执行直到完成 |
| `done()` | ❌ | 检查是否完成 |
| `get_final_llm_resp()` | ❌ | 获取最终 LLM 响应 |

---

## Handler 注册表

| 类/方法 | 状态 | 说明 |
| --- | --- | --- |
| `StarHandlerRegistry` | ❌ | Handler 注册表 |
| `get_handlers_by_event_type(type)` | ❌ | 按事件类型获取 Handler |
| `get_handler_by_full_name(name)` | ❌ | 按全名获取 Handler |
| `get_handlers_by_module_name(name)` | ❌ | 按模块名获取 Handler |
| `StarHandlerMetadata` | ❌ | Handler 元数据 |

---

## 优先级

### P0 - 阻塞迁移
1. **Memory Client** - AI 插件核心能力
2. **HTTP Client** - Web API 注册
3. **MessageEvent**: `is_private_chat()`, `is_admin()`, `self_id`, `message_type`, `unified_msg_origin`
4. **事件控制**: `stop_event()`, `continue_event()`
5. **基础事件**: `astrbot_loaded`, `platform_loaded`, `after_message_sent`
6. **工具方法**: `get_data_dir()` - 数据存储必需
7. **会话等待**: `SessionWaiter` - 交互式插件必需
8. **Provider实体**: `MessageSession` - 跨会话发送必需

### P1 - 影响体验
1. **消息组件**: `At`, `AtAll`, `Reply`
2. **Agent**: `tool_loop_agent()`, `BaseAgentRunner`
3. **触发器过滤**: `message_types=[...]`, `CustomFilter`
4. **LLM**: `image_urls`, `tools` 参数
5. **触发器实现**: `@on_event`, `@on_schedule` Core端实现
6. **工具方法**: `text_to_image()`, `html_render()`
7. **命令组**: 子命令路由
8. **TTS/STT Provider**: 语音输入输出

### P2 - 增强功能
1. Provider 查询和管理
2. TTS/STT/Embedding Provider
3. 更多事件类型
4. 命令组路由
5. LLM 工具注册装饰器
6. 更多消息组件: `Poke`, `Node`, `Json`
7. 人格管理 API
8. 对话管理 API
9. 知识库管理 API
10. Platform 统计和状态

### P2.5 - Star基类扩展方法（旧系统Star类特有）

| 方法 | 状态 | 说明 | 建议实现 |
| --- | --- | --- | --- |
| `Star.text_to_image(text)` | ❌ | 文本转图片渲染 | 通过Capability暴露给SDK |
| `Star.html_render(tmpl, data)` | ❌ | HTML模板渲染 | 通过Capability暴露给SDK |
| `Star.initialize()` | 🔄 | 插件激活时调用（旧系统生命周期） | SDK使用`on_start()`替代 |
| `Star.terminate()` | 🔄 | 插件禁用时调用（旧系统生命周期） | SDK使用`on_stop()`替代 |
| `Star.__init_subclass__()` | ✅ | 自动注册插件到star_map | SDK已实现类似的`__init_subclass__` |
| `Star.context` | ❌ | 插件上下文引用 | SDK通过handler参数传递ctx |
| `Star._get_context_config()` | ❌ | 获取上下文配置 | SDK通过`ctx.metadata.get_plugin_config()` |

### P2.6 - 命令参数类型系统（旧系统CommandFilter特有）

| 参数类型 | 状态 | 说明 | 旧系统实现位置 |
| --- | --- | --- | --- |
| `str` 自动解析 | ✅ | 字符串参数 | `CommandFilter.validate_and_convert_params()` |
| `int` 自动转换 | ❌ | 整数参数自动转换 | `CommandFilter.validate_and_convert_params()` |
| `float` 自动转换 | ❌ | 浮点数参数自动转换 | `CommandFilter.validate_and_convert_params()` |
| `bool` 自动转换 | ❌ | 布尔参数自动转换（支持true/false/yes/no/1/0） | `CommandFilter.validate_and_convert_params()` |
| `Optional[T]` 支持 | ❌ | 可选类型参数 | `CommandFilter.validate_and_convert_params()` |
| `GreedyStr` 贪婪匹配 | ❌ | 捕获剩余所有文本作为单个参数 | `CommandFilter.GreedyStr` |
| `unwrap_optional()` | ❌ | 解析Optional类型注解的工具函数 | `command.py`中的工具函数 |
| `print_types()` | ❌ | 打印命令参数类型信息用于帮助 | `CommandFilter.print_types()` |

### P2.7 - 过滤器组合与自定义（旧系统Filter系统）

| 功能 | 状态 | 说明 | 旧系统实现 |
| --- | --- | --- | --- |
| `CustomFilter` 基类 | ❌ | 自定义过滤器抽象基类 | `custom_filter.py` |
| `CustomFilter.__and__()` | ❌ | 过滤器与运算（&） | `CustomFilterMeta.__and__()` |
| `CustomFilter.__or__()` | ❌ | 过滤器或运算（\|） | `CustomFilterMeta.__or__()` |
| `CustomFilterAnd` | ❌ | 与运算过滤器组合 | `custom_filter.py` |
| `CustomFilterOr` | ❌ | 或运算过滤器组合 | `custom_filter.py` |
| `raise_error` 参数 | ❌ | 权限不足时是否抛出错误 | `CustomFilter.__init__()` |

### P2.8 - 事件系统细节对比

| 旧系统特性 | 新SDK状态 | 说明 |
| --- | --- | --- |
| `EventType` 枚举（14种事件） | 🔄 | SDK有事件触发器但Core端未实现完整事件系统 |
| `OnWaitingLLMRequestEvent` | ❌ | 等待调用LLM前的通知事件 |
| `OnCallingFuncToolEvent` | ❌ | 调用函数工具时的事件 |
| `OnUsingLLMToolEvent` | ❌ | 使用LLM工具时的事件 |
| `OnLLMToolRespondEvent` | ❌ | LLM工具响应后的事件 |
| `StarHandlerRegistry` | ❌ | Handler注册表（全局单例） |
| Handler优先级排序 | ❌ | 按`priority`字段排序执行 |
| Handler白名单过滤 | ❌ | 按插件名称过滤Handler |

### P2.9 - 平台适配器类型系统

| 平台类型 | 状态 | 说明 |
| --- | --- | --- |
| `PlatformAdapterType` 枚举 | ❌ | 支持15+种平台类型 |
| `AIOCQHTTP` | ❌ | QQ机器人协议 |
| `QQOFFICIAL` | ❌ | QQ官方API |
| `TELEGRAM` | ❌ | Telegram |
| `WECOM`/`WECOM_AI_BOT` | ❌ | 企业微信 |
| `LARK` | ❌ | 飞书 |
| `DINGTALK` | ❌ | 钉钉 |
| `DISCORD` | ❌ | Discord |
| `SLACK` | ❌ | Slack |
| `KOOK` | ❌ | KOOK |
| `VOCECHAT` | ❌ | VoceChat |
| `WEIXIN_OFFICIAL_ACCOUNT` | ❌ | 微信公众号 |
| `SATORI` | ❌ | Satori协议 |
| `MISSKEY` | ❌ | Misskey |
| `LINE` | ❌ | LINE |
| `ADAPTER_NAME_2_TYPE` 映射 | ❌ | 平台名称到类型的映射 |

### P2.10 - StarTools 工具集（旧系统特有，新SDK未实现）

| 方法 | 状态 | 说明 | 使用场景 |
| --- | --- | --- | --- |
| `StarTools.send_message(session, chain)` | ❌ | 根据session主动发送消息 | 定时任务、后台通知 |
| `StarTools.send_message_by_id(type, id, chain, platform)` | ❌ | 根据ID直接发送消息 | 跨会话发送 |
| `StarTools.create_message(...)` | ❌ | 创建AstrBotMessage对象 | 构造人工消息事件 |
| `StarTools.create_event(abm, platform)` | ❌ | 创建并提交事件到平台 | 触发处理流程 |
| `StarTools.activate_llm_tool(name)` | ❌ | 激活LLM工具 | 动态控制工具 |
| `StarTools.deactivate_llm_tool(name)` | ❌ | 停用LLM工具 | 动态控制工具 |
| `StarTools.register_llm_tool(...)` | ❌ | 注册LLM工具 | 动态注册 |
| `StarTools.unregister_llm_tool(name)` | ❌ | 注销LLM工具 | 动态注销 |
| `StarTools.get_data_dir(plugin_name?)` | ❌ | 获取插件数据目录 | 文件存储 |
| `StarTools._context` | ❌ | 类级别的Context引用 | 工具方法访问Core |

### P2.11 - 会话级插件管理（SessionPluginManager）

| 功能 | 状态 | 说明 |
| --- | --- | --- |
| `SessionPluginManager` 类 | ❌ | 会话级插件管理器 |
| `is_plugin_enabled_for_session(session_id, plugin_name)` | ❌ | 检查插件在会话中是否启用 |
| `filter_handlers_by_session(event, handlers)` | ❌ | 根据会话配置过滤处理器 |
| `session_plugin_config` 配置 | ❌ | 会话插件配置存储 |
| `enabled_plugins` 列表 | ❌ | 会话启用的插件列表 |
| `disabled_plugins` 列表 | ❌ | 会话禁用的插件列表 |

### P2.11.1 - 会话级 LLM/TTS 开关（SessionServiceManager）

| 功能 | 状态 | 说明 |
| --- | --- | --- |
| `SessionServiceManager` 类 | ❌ | 会话级服务开关管理器 |
| `is_llm_enabled_for_session(session_id)` | ❌ | 检查会话是否启用 LLM |
| `set_llm_status_for_session(session_id, enabled)` | ❌ | 设置会话 LLM 开关 |
| `should_process_llm_request(session_id)` | ❌ | 判断是否处理默认 LLM 请求 |
| `is_tts_enabled_for_session(session_id)` | ❌ | 检查会话是否启用 TTS |
| `set_tts_status_for_session(session_id, enabled)` | ❌ | 设置会话 TTS 开关 |
| `should_process_tts_request(session_id)` | ❌ | 判断是否处理 TTS 请求 |
| `is_session_enabled(session_id)` | ❌ | 汇总判断会话服务是否可用 |

### P2.12 - 命令组系统（CommandGroupFilter）

| 功能 | 状态 | 说明 | 示例 |
| --- | --- | --- | --- |
| `CommandGroupFilter` 类 | ❌ | 命令组过滤器 | `!group subcmd` |
| `group_name` 属性 | ❌ | 命令组名称 | - |
| `sub_command_filters` 列表 | ❌ | 子命令过滤器列表 | - |
| `parent_group` 引用 | ❌ | 父命令组引用 | 支持嵌套 |
| `add_sub_command_filter()` | ❌ | 添加子命令 | - |
| `get_complete_command_names()` | ❌ | 获取完整命令名 | `group subcmd` |
| `print_cmd_tree()` | ❌ | 打印命令树 | 帮助文档 |
| `startswith()` | ❌ | 消息是否以命令组开头 | - |
| `equals()` | ❌ | 消息是否完全匹配命令组 | - |

### P2.13 - 消息类型过滤（EventMessageType）

| 类型 | 状态 | 说明 |
| --- | --- | --- |
| `EventMessageType` 枚举 | ❌ | 消息类型枚举 |
| `GROUP_MESSAGE` | ❌ | 群聊消息 |
| `PRIVATE_MESSAGE` | ❌ | 私聊消息 |
| `OTHER_MESSAGE` | ❌ | 其他消息 |
| `ALL` | ❌ | 所有消息类型 |
| `EventMessageTypeFilter` | ❌ | 消息类型过滤器 |
| `MESSAGE_TYPE_2_EVENT_MESSAGE_TYPE` 映射 | ❌ | 类型转换映射 |

### P2.14 - PluginKVStoreMixin（插件KV存储Mixin）

| 方法 | 状态 | 说明 | 替代方案 |
| --- | --- | --- | --- |
| `PluginKVStoreMixin` 类 | ❌ | 为插件提供KV存储的Mixin | SDK的`ctx.db` |
| `put_kv_data(key, value)` | ❌ | 存储键值对 | `ctx.db.set()` |
| `get_kv_data(key, default)` | ❌ | 获取键值对 | `ctx.db.get()` |
| `delete_kv_data(key)` | ❌ | 删除键值对 | `ctx.db.delete()` |
| `plugin_id` 属性 | ❌ | 插件ID标识 | SDK自动处理 |

### P2.15 - StarMetadata 完整字段对比

| 字段 | 状态 | 说明 |
| --- | --- | --- |
| `name` | ✅ | 插件名称 |
| `author` | ✅ | 插件作者 |
| `desc` | ✅ | 插件描述 |
| `version` | ✅ | 插件版本 |
| `repo` | ✅ | 仓库地址 |
| `star_cls_type` | ✅ | 插件类类型 |
| `module_path` | ✅ | 模块路径 |
| `star_cls` | ✅ | 插件类实例 |
| `module` | ✅ | 模块对象 |
| `root_dir_name` | ✅ | 根目录名称 |
| `reserved` | ✅ | 是否保留插件 |
| `activated` | ✅ | 是否激活 |
| `config` | ✅ | 插件配置 |
| `star_handler_full_names` | ✅ | Handler全名列表 |
| `display_name` | ✅ | 显示名称 |
| `logo_path` | ✅ | Logo路径 |
| `support_platforms` | ❌ | 支持的平台列表 |
| `astrbot_version` | ❌ | 要求的AstrBot版本范围 |

### P3 - SDK 架构扩展（可选增强）
1. **CancelToken 扩展** - 取消原因、回调注册、组合取消
2. **provide_capability 扩展** - 版本控制、依赖声明、中间件、速率限制
3. **Handler kind 实现** - `hook`/`tool`/`session` 类型运行时支持
4. **Permissions 扩展** - 角色系统、权限范围、用户白/黑名单
5. **插件间 Capability** - 发现机制、流式调用、版本协商
6. **事件类型标准化** - EventType 枚举、payload schema
7. **依赖注入扩展** - 自定义类型注入器、配置注入

---

## 架构说明

### Core端 MVP 不支持的功能
以下功能 SDK 已定义接口，但 Core 端 `capability_bridge.py` 标记为 MVP 不支持：

1. **HTTP Client** 全部方法
2. **db.watch()** 流式订阅
3. **@on_event** 事件触发器
4. **@on_schedule** 定时触发器
5. **Memory Client** 全部方法（实际返回空/错误）

### Core端简化实现的功能
以下功能 Core 端有简化实现，但非完整功能：

1. **memory.search** - 简单字符串匹配，非语义搜索
2. **llm.stream_chat** - 等待完整响应后逐字符返回，非真正流式
3. **memory.save_with_ttl** - TTL 仅记录但不实际过期

### 新 SDK 新增能力
以下能力是新 SDK 独有，旧系统没有的：

1. `@provide_capability` - 声明对外暴露的能力
2. `CancelToken` - 取消令牌机制
3. `DBClient.watch()` - 数据库变更订阅
4. `ctx.logger` - 绑定插件 ID 的日志器
5. `AstrBotError` - 完善的错误模型（含错误码、重试标记、序列化）

### 旧系统独有能力
以下能力是旧系统独有，新 SDK 未实现的：

1. `SessionWaiter` - 会话等待机制（交互式对话必需）
2. `CustomFilter` - 自定义过滤器（支持与/或组合）
3. `CommandGroupFilter` - 命令组（子命令路由）
4. 命令参数自动类型解析（int/float/bool/GreedyStr）
5. `PlatformAdapterTypeFilter` - 平台适配器类型过滤（15+平台）
6. `EventMessageTypeFilter` - 消息类型过滤（GROUP/PRIVATE/OTHER）
7. `PersonaManager` - 人格管理 API
8. `ConversationManager` - 对话管理 API
9. `KnowledgeBaseManager` - 知识库管理 API
10. `FunctionToolManager` - LLM 工具管理器
11. `ProviderManager` - 提供商管理器
12. `BaseAgentRunner` - Agent 运行器基类
13. `StarHandlerRegistry` - Handler 注册表
14. `Platform` 实体类（状态、统计、Webhook）
15. `MessageSession` - 消息会话对象
16. TTS/STT/Embedding/Rerank Provider 支持
17. `StarTools` - 插件开发工具集（send_message_by_id, create_event等）
18. `SessionPluginManager` - 会话级插件管理
19. `PluginKVStoreMixin` - 插件KV存储Mixin
20. `CommandFilter.print_types()` - 命令参数类型打印
21. `Star.text_to_image()` / `Star.html_render()` - 渲染工具方法

---

## SDK 扩展能力（新 SDK 可进一步扩展）

以下是基于当前 SDK 架构设计，可以进一步扩展的能力。

### CancelToken 取消机制扩展

| 扩展 | 状态 | 说明 |
| --- | --- | --- |
| `cancel(reason: str)` | ❌ | 取消时传递原因 |
| `on_cancel(callback)` | ❌ | 注册取消回调，支持清理逻辑 |
| `with_timeout(seconds)` | ❌ | 辅助方法：超时自动取消 |
| `CancelToken.any(*tokens)` | ❌ | 组合取消：任一取消即触发 |
| `CancelToken.all(*tokens)` | ❌ | 组合取消：全部取消才触发 |

### provide_capability 能力导出扩展

| 扩展 | 状态 | 说明 |
| --- | --- | --- |
| `version: str` | ❌ | 能力版本控制 |
| `requires: list[str]` | ❌ | 声明依赖的其他 capability |
| `middleware: list[Middleware]` | ❌ | 能力拦截器/中间件支持 |
| `rate_limit: RateLimit` | ❌ | 速率限制声明 |
| `cache_policy: CachePolicy` | ❌ | 缓存策略声明 |

### Handler kind 类型实现

| 类型 | 状态 | 说明 |
| --- | --- | --- |
| `handler` | ✅ | 已实现，标准消息处理器 |
| `hook` | ❌ | 钩子类型（定义但未在运行时实现） |
| `tool` | ❌ | LLM Function Calling 工具类型 |
| `session` | ❌ | 会话级处理器类型 |

### Permissions 权限系统扩展

| 扩展 | 状态 | 说明 |
| --- | --- | --- |
| `roles: list[str]` | ❌ | 角色系统支持 |
| `scopes: list[str]` | ❌ | 细粒度权限范围 |
| `platforms: list[str]` | ❌ | 平台级权限限制 |
| `allow_users: list[str]` | ❌ | 用户白名单 |
| `deny_users: list[str]` | ❌ | 用户黑名单 |

### 插件间 Capability 调用

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| `ctx.capability.discover()` | ❌ | 发现其他插件导出的 capability |
| `ctx.capability.invoke(name, payload)` | ❌ | 调用其他插件的 capability（当前只支持同步） |
| `ctx.capability.invoke_stream(name, payload)` | ❌ | 流式调用其他插件的 capability |
| 版本协商 | ❌ | capability 版本兼容性检查 |

### 事件类型标准化

| 扩展 | 状态 | 说明 |
| --- | --- | --- |
| `EventType` 枚举 | ❌ | 标准化事件类型常量，避免拼写不一致 |
| 事件 payload schema | ❌ | 每种事件的标准化 payload 结构定义 |

### 依赖注入扩展

| 扩展 | 状态 | 说明 |
| --- | --- | --- |
| 自定义类型注入器 | ❌ | 允许插件注册自定义类型的依赖注入 |
| 配置注入 | ❌ | 自动注入插件配置项到 handler 参数 |
| 依赖注入容器 | ❌ | 支持更复杂的依赖关系 |

### 调度器验证

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| `@on_schedule` Core 端调度器 | ❓ | 需验证 Core 端是否有完整调度器实现 |
| 持久化任务 | ❓ | 验证定时任务是否支持持久化 |

---

## 其他系统能力

### 错误处理和异常类型

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| `AstrBotError` 基类 | ✅ | SDK 已定义，含 code/message/hint/retryable |
| `ErrorCodes` 常量 | ✅ | SDK 已定义错误码枚举 |
| `to_payload()` / `from_payload()` | ✅ | 错误序列化/反序列化（跨进程传递） |
| `ProviderNotFoundError` | ❌ | Core 端特有异常类型 |

### 日志系统

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| `ctx.logger` | ✅ | 绑定插件 ID 的日志器 |
| `LogBroker` 日志代理 | ❌ | 日志缓存和订阅分发 |
| `LogManager.GetLogger()` | ❌ | Core 端日志管理器 |
| 日志订阅机制 | ❌ | 外部订阅日志消息队列 |

### 文件服务

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| `FileTokenService` | ❌ | 临时文件令牌服务 |
| `register_file(path, timeout) -> token` | ❌ | 注册文件获取下载令牌 |
| `handle_file(token) -> path` | ❌ | 通过令牌获取文件路径 |
| `File.register_to_file_service()` | ❌ | 消息组件注册到文件服务 |
| `File.get_file()` | ❌ | 异步获取文件（支持 URL 下载） |

### Webhook 处理

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| `Platform.unified_webhook()` | ❌ | 统一 Webhook 模式检查 |
| `Platform.webhook_callback(request)` | ❌ | Webhook 回调处理 |
| `/api/platform/webhook/{uuid}` 路由 | ❌ | Dashboard Webhook 路由 |

### MCP (Model Context Protocol)

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| `MCPClient.connect_to_server()` | ❌ | 连接 MCP 服务器 |
| `MCPClient.list_tools_and_save()` | ❌ | 列出并保存工具 |
| `MCPClient.call_tool_with_reconnect()` | ❌ | 调用工具（带自动重连） |
| `MCPTool` 包装器 | ❌ | MCP 工具转 Function Tool |

### 事件总线

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| `EventBus` | ❌ | 事件分发和处理 |
| `event_queue` | ❌ | 异步事件队列访问 |

### 热重载

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| `ASTRBOT_RELOAD=1` 环境变量 | ❌ | 启用热重载 |
| `_watch_plugins_changes()` | ❌ | 监视插件文件变化 |

### 国际化 (i18n)

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| `ConfigMetadataI18n` | ❌ | 配置元数据国际化 |
| `convert_to_i18n_keys()` | ❌ | 转换为 i18n 键 |

### 插件依赖管理

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| `requirements.txt` 自动安装 | ❓ | Core 端已支持，SDK 需验证 |
| `PluginVersionIncompatibleError` | ❌ | 版本不兼容异常 |
| `PluginDependencyInstallError` | ❌ | 依赖安装失败异常 |
| `_import_plugin_with_dependency_recovery()` | ❌ | 带依赖恢复的导入 |

### 消息撤回

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| 消息撤回 API | ❌ | 撤回已发送消息（平台特定） |

### 群组管理

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| `get_group(group_id?)` | ❌ | 获取群聊数据 |
| 群成员列表获取 | ❌ | 依赖 `get_group()` |

### 插件间通信

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| `get_registered_star(name)` | ✅ | 通过 `ctx.metadata.get_plugin()` 支持 |
| `get_all_stars()` | ✅ | 通过 `ctx.metadata.list_plugins()` 支持 |
| `StarHandlerRegistry` 访问 | ❌ | 直接访问 Handler 注册表 |
| `get_handlers_by_event_type()` | ❌ | 按事件类型获取 Handler |
| `get_handler_by_full_name()` | ❌ | 按全名获取 Handler |

### 命令参数类型解析

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| `str` 参数 | ✅ | 字符串参数 |
| `int` 参数 | ❌ | 整数参数自动转换 |
| `float` 参数 | ❌ | 浮点数参数自动转换 |
| `bool` 参数 | ❌ | 布尔参数自动转换 |
| `Optional[T]` 参数 | ❌ | 可选类型参数 |
| `GreedyStr` 参数 | ❌ | 贪婪字符串（剩余所有文本） |

### Cron 定时任务管理

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| `CronJobManager.add_basic_job()` | ⚠️ | SDK 定义 `@on_schedule`，Core 端 MVP 不支持 |
| `CronJobManager.add_active_job()` | ⚠️ | 主动 Agent 定时任务 |
| `CronJobManager.update_job()` | ❌ | 更新任务 |
| `CronJobManager.delete_job()` | ❌ | 删除任务 |
| `CronJobManager.list_jobs()` | ❌ | 列出任务 |
| 任务持久化 | ❌ | 定时任务持久化存储 |

### Reply 消息组件属性

| 属性 | 状态 | 说明 |
| --- | --- | --- |
| `Reply.id` | ❌ | 被引用消息 ID |
| `Reply.chain` | ❌ | 被引用的消息段列表 |
| `Reply.sender_id` | ❌ | 发送者 ID |
| `Reply.sender_nickname` | ❌ | 发送者昵称 |
| `Reply.message_str` | ❌ | 被引用消息的纯文本 |
