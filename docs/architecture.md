# YS-Agent 架构（M1-M5 重构后）

最后更新：2026-06-02
适用版本：M1+M2+M3+M4 完成后（即 `agent/agent.py` 缩到 re-export 之后的所有版本）

## 一句话

> YS-Agent 的 agent loop 在 2026-06 经过一次 Pi 风格架构升级：拆分层、引入事件总线、引入 LLM Provider 抽象、引入压缩前的文件追踪钩子。**前端、YonSuite 业务工具、MCP server、skill 系统零改动**。

## 模块图

```
backend/                FastAPI 入口（web 层）— 没动
  api/chat.py           唯一调用 AIAgent 的地方
  api/...               其他 24 个路由
  llm_providers.py      LLM_PROVIDERS 元数据（加了 protocol 字段）

agent/                  业务核心
  agent.py              12 行 re-export —— 历史兼容层
  core/                 M1+M2+M4 新增
    agent.py            主循环 ~440 行（事件发布 + 工具调度 + 压缩）
    message_builder.py  纯函数：build_system_prompt / build_turn_messages
    llm_client.py       M3 薄壳（向后兼容）—— 委托给 provider
    llm_providers/      M3 新增
      base.py           LLMProvider 抽象基类 + 统一 LLMResponse
      openai_compat.py  OpenAI 协议 provider（覆盖 9 个兼容 host）
      anthropic.py      Anthropic 原生 provider
      factory.py        get_provider(name) / get_provider_for_config()
    tool_dispatcher.py  纯函数：dispatch_tool(name, args) -> (result, preview)
    iteration_budget.py 纯类：IterationBudget
  context_compactor.py  M4 增强：summary_caller + 文件追踪 + 事件钩子
  events/               M1+M2 新增
    bus.py              Event 基类 + EventBus + 全局 event_bus 单例
    types.py            8 个事件类
    extensions.py       Extension 基类 + ExtensionRunner
  tools/                没动 —— registry 已有 before/after hook
  security_hooks.py     没动（registry 老钩子）—— 仍注册
  session_manager.py    没动
  skill_manager.py      没动
  erp_clients/yonsuite/      没动

frontend/               React/Vite —— 没动
mcp_server/             YonSuite MCP server —— 没动
```

## 数据流

```
WebSocket 消息
   ↓
backend/api/chat.py:_run_agent
   ↓
AIAgent.run_conversation (re-export → core/agent.py)
   ↓
事件总线发布顺序（每次对话）:
   session_start → user_message → (每轮:)
      before_llm_call → LLM call → after_llm_call
      (如果有 tool_calls:) before_tool_call × N → after_tool_call × N
   session_end
   ↓
结果流回 WebSocket
```

## 关键设计决策

### 1. M1：拆 `agent/agent.py`（481 → 12 行）

`agent.py` 拆成 5 个模块。**老 import 路径不断**（`from agent.agent import AIAgent` 继续工作），所以 `backend/api/chat.py` 零改动。

每个新模块的职责：

| 模块 | 职责 | 大小 |
|---|---|---|
| `message_builder.py` | 纯函数构造 system prompt / turn list | ~95 行 |
| `llm_client.py` | OpenAI SDK 包装（M1）/ 薄壳（M3） | ~155 行 |
| `tool_dispatcher.py` | registry dispatch + truncation | ~50 行 |
| `iteration_budget.py` | 迭代计数器 | ~30 行 |
| `agent.py` | 主循环（事件 + 循环 + 工具调度） | ~445 行 |

### 2. M2：事件总线

- 同步、线程安全、单例（`agent.events.event_bus`）
- 9 个事件发布点（见数据流）
- `BeforeToolCallEvent` 可 cancel —— extension 阻断危险操作
- `BeforeLLMCallEvent` 可 cancel —— 短路 LLM 调用
- `AfterToolCallEvent.result` 可被 extension 改写
- `SessionBeforeCompactEvent` 可写 `event.extra: list[str]` 追加到 summary

### 3. M3：LLM Provider 抽象

`LLMClient` 变成薄壳，持有 `LLMProvider`。新增 provider 只要在 `backend/llm_providers.py` 加一行：

```python
"MyNewProvider": {
    "base_url": "https://...",
    "models": [...],
    "api_key_label": "...",
    "api_key_placeholder": "...",
    "protocol": "openai_compat",  # 或 "anthropic" 或新加的
},
```

`factory.get_provider("MyNewProvider", api_key=...)` 自动选对类。

**支持的 protocol：**
- `openai_compat`（9 个 host）—— OpenAI / DeepSeek / 智谱 / 硅基流动 / 阿里 / Kimi / OpenRouter / MiniMax
- `anthropic`（1 个）—— Anthropic，需要 `pip install anthropic`
- `baidu_qianfan`（1 个）—— **M5 还未实现**，需要新增 `BaiduQianfanProvider` 类

**异常统一**：`LLMProviderError` 包装所有 provider 错误，`transient=True` 触发重试。

### 4. M4：压缩增强

3 个改进：

1. **`compact_messages` 不再吃 OpenAI client**，改成 `summary_caller: (str) -> str`。agent 层构造一个调用 `provider.chat()` 的闭包。这让 Anthropic 也能跑压缩（M3 留下的兼容问题）。
2. **文件追踪**：扫描 `tool_calls` args + 消息内容抽文件路径，**限 5 个文件 / 8KB 总大小 / 2KB 每文件**，**拒绝 `/etc /sys /proc /dev /boot /System /usr/lib /usr/bin /usr/sbin /Library /var/run`**。读到的内容作为 `tracked_files: {path: contents}` 挂在 `SessionBeforeCompactEvent` 上，**并嵌入 LLM 的 summary prompt**。
3. **`SessionBeforeCompactEvent` 钩子**：在 LLM 生成 draft summary 之后、构造 final summary_msg 之前发。extension 写 `event.extra`，追加到 final summary。

**保守正则** —— `/Users/`、`/home/`、`/root/`、`/tmp/`、`/var/`、`~/...`、`./...`、`../...`。**不**误抓 `https://`。

## 向后兼容

**保留不动的：**
- `from agent.agent import AIAgent`（re-export）
- `from agent.core.llm_client import LLMClient, LLMResponse, ToolCallPayload`（shim）
- `ToolRegistry.add_before_hook / add_after_hook`（M2 没替换，只新增事件层）
- 26 个内置工具的 schema、handler 全部不变
- `context_compactor.CompactionSettings` 字段不变
- 30 个 FastAPI 路由全保留
- 前端 API 调用全保留

**改动的：**
- `compact_messages(messages, settings, summary_caller, model, ...)` —— 第 3 个参数从 `openai_client` 变成 callable
- `_maybe_compact` 在 `agent/core/agent.py` 内部（外部不可见）
- `LLM_PROVIDERS` 字典加了 `protocol` 字段（前端 `/api/providers` 仍然只返回 5 个字段，不暴露 `protocol`）

## 手测冒烟记录（2026-06-02）

| # | 流程 | 结果 |
|---|---|---|
| 1 | 简单问答 | ✓ |
| 2 | 长对话压缩（8306 tokens 节省） | ✓ |
| 3 | 9 个 provider 切换 + 2 个错误路径 | ✓ |
| 4 | security hook 真实阻断 `rm -rf` + 放行 `echo` | ✓ |
| 5 | session_manager 真实读写 | ✓ |
| 6 | 流式回调 4 个 sentinel 齐全 | ✓ |
| 7 | 工具调用真实执行 + token/api_calls 累加 | ✓ |
| 8 | skill 真实加载（6 个 active） | ✓ |
| 9 | MCP server 状态可读 | ✓ |
| 10 | FastAPI 30 个路由全保留 | ✓ |

**未在 mock 环境测、需要在真实 API key 下手测的：**
- 真实 LLM 调用的 SSE 流式断点恢复（需要真 API key + 断网模拟）
- MCP server 实际连接到 YonSuite / chart-server
- 真实 YonSuite 业务工具调用

## 不在范围

下列是 M5 明确**不做**的（见 M1 提案）：
- ❌ 树形会话 / fork（产品形态不需要）
- ❌ TUI（有 Web）
- ❌ 完整 Pydantic 化所有工具
- ❌ pytest 套件（手测够用）
- ❌ 性能 profiling（M1-M4 自然会变快）
- ❌ 任意时刻 session 快照（降级为"compaction 后存一次"，已经在做）
- ❌ `BaiduQianfanProvider` 实现（baidu_qianfan protocol 报清晰错误）
