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
| **总计** | **200** | **33** | **9** | **146** | **17** | **19%** |

> 注：覆盖率 = `(已实现 + 部分实现 × 0.5) / 总计`，⚠️ 表示SDK已定义但Core端未实现

---

## SDK Client 方法

### LLMClient

| 方法 | 状态 | 说明 |
| --- | --- | --- |
| `chat(prompt, system?, history?, model?, temperature?)` | ✅ | 发送聊天，返回文本 |
| `chat_raw(prompt, ...)` | ✅ | 返回完整响应（含 usage、tool_calls） |
| `stream_chat(prompt, ...)` | ⚠️ | 流式聊天（Core端是假流式：等待完整响应后逐字符返回） |
| `chat(image_urls=[...])` | 🔄 | 多模态：图片输入 |
| `chat(tools=[...])` | 🔄 | 工具调用 |
| `chat(contexts=[...])` | 🔄 | 自定义上下文 |
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
| At (@某人) | ❌ | @提及 |
| AtAll (@全体) | ❌ | @全体成员 |
| Reply (引用) | ❌ | 引用回复 |
| Record (语音) | ❌ | 语音消息 |
| Video (视频) | ❌ | 视频消息 |
| File (文件) | ❌ | 文件附件 |
| Face (表情) | ❌ | QQ 表情 |
| Forward (转发) | ❌ | 合并转发 |
| Poke (戳一戳) | ❌ | 戳一戳动作 |
| Node (转发节点) | ❌ | 合并转发节点 |
| Json (JSON) | ❌ | JSON 消息 |

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
| `get_all_providers()` | 无 | ❌ | 列出 Provider |
| `get_all_tts_providers()` | 无 | ❌ | 列出 TTS Provider |
| `get_all_stt_providers()` | 无 | ❌ | 列出 STT Provider |
| `get_using_tts_provider()` | 无 | ❌ | TTS Provider |
| `get_using_stt_provider()` | 无 | ❌ | STT Provider |
| `register_web_api()` | `ctx.http.register_api()` | ⚠️ | 注册 API（Core端不支持） |
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
5. `PlatformAdapterTypeFilter` - 平台适配器类型过滤
6. `EventMessageTypeFilter` - 消息类型过滤
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
