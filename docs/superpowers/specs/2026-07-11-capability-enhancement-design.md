# ZLink Agent 能力增强设计文档

> 2026-07-11 — 四个方向：LLM 提供商扩展 / 子代理委托 / 命令审批安全层 / 浏览器自动化工具

> Spec 自检: ✅ 无占位符 ✅ 内部一致 ✅ 范围聚焦 ✅ 无歧义

---

## 目录

1. [LLM 提供商扩展 — DeepSeek](#1-llm-提供商扩展--deepseek)
2. [子代理委托](#2-子代理委托)
3. [命令审批模式](#3-命令审批模式)
4. [浏览器自动化工具](#4-浏览器自动化工具)
5. [集成与兼容性分析](#5-集成与兼容性分析)
6. [实施顺序建议](#6-实施顺序建议)

---

## 1. LLM 提供商扩展 — DeepSeek

### 1.1 背景

当前 ZLink Agent 只支持两个 LLM 提供商：OpenAI-compat（`openai_compat.py`）和 Anthropic（`anthropic.py`）。DeepSeek 是中文生态中最主流的 LLM 提供商之一，使用与 OpenAI 完全兼容的 API 格式，可以直接用现有的 `OpenAICompatProvider`。

### 1.2 改动范围

**仅改一个文件**: `backend/llm_providers.py`

在 `PROVIDERS` 表中添加 DeepSeek 条目：

```python
ProviderInfo(
    name="DeepSeek",
    base_url="https://api.deepseek.com",
    models=["deepseek-chat", "deepseek-reasoner"],
    api_key_label="DeepSeek API Key",
    api_key_placeholder="sk-...",
)
```

`deepseek-chat` 是标准对话模型，`deepseek-reasoner` 是推理模型（会返回 `reasoning_content` 字段）。`OpenAICompatProvider` 已有对 `reasoning_content` 的处理逻辑，可直接使用。

### 1.3 前端改动

当前 `SettingsLLMPage.tsx` 已从 `llm_providers.py` 动态读取提供商列表，添加新条目后自动出现，无需额外前端改动。

### 1.4 测试

- 添加一个配置加载测试，验证 DeepSeek 可以从 `PROVIDERS` 正确读取
- 不需要集成测试（底层复用 `OpenAICompatProvider`，已有覆盖）

### 1.5 不涉及

- 不需要新的 Provider 类
- 不需要新的依赖
- 不需要数据库迁移

---

## 2. 子代理委托

### 2.1 背景

Agent 在工具循环中可能遇到可以并行执行的任务。例如用户问"对比 YonSuite 和 NC 上个月的销售数据"，Agent 可以 spawn 两个子代理分别查两个系统，然后合并结果。当前 Agent 只能串行执行，效率低。

### 2.2 设计方案

#### 2.2.1 新文件: `agent/tools/delegate_tool.py`

提供一个 `delegate_task` 工具，供 Agent 在工具循环中调用。

**工具签名**:

```python
registry.register(
    name="delegate_task",
    toolset="agent",
    schema={
        "type": "function",
        "function": {
            "name": "delegate_task",
            "description": "将任务委托给子代理并行执行。当你遇到可以独立并行的子任务时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "子代理需要完成的任务描述"
                    },
                    "context": {
                        "type": "string",
                        "description": "子代理需要的上下文（相关对话历史、数据等）"
                    }
                },
                "required": ["task"]
            }
        }
    },
    handler=handle_delegate_task,
)
```

#### 2.2.2 实现方式: ThreadPoolExecutor + 子 AIAgent

```python
def handle_delegate_task(args: dict) -> str:
    task = args["task"]
    context = args.get("context", "")

    # 在 ThreadPoolExecutor 中运行子 AIAgent
    with ThreadPoolExecutor(max_workers=3) as executor:
        future = executor.submit(_run_sub_agent, task, context)
        result = future.result(timeout=120)

    return result
```

**子 AIAgent 的配置**:
- 使用与主 Agent 相同的 LLM 配置（模型、API Key、temperature）
- 使用独立的空对话历史
- 使用主 Agent 的完整工具集（包括 ERP MCP 工具）
- 设置 `max_iterations=15`（有限循环，防止子代理失控）
- 不发布 EventBus 事件（避免主 Agent 扩展重复执行）

#### 2.2.3 并行检测策略

子代理委托由主 Agent **自主决定**何时调用。通过系统提示词中加入指导：
- 当用户问题涉及多个独立数据源时，考虑使用 `delegate_task`
- 每个子代理负责一个独立的数据查询
- 主代理在收到所有子代理结果后合并呈现

不需要 LLM 自动检测框架——让模型自己通过系统提示词策略决定。这是一种务实的"emergent parallelism"模式。

#### 2.2.4 安全和资源控制

- **最大并行数**: 3（可配置）
- **子代理超时**: 120 秒
- **最大迭代数**: 15 轮/子代理
- **错误隔离**: 一个子代理失败不影响其他子代理
- **结果截断**: 单个子代理返回结果最大 10000 字符

### 2.3 涉及文件

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `agent/tools/delegate_tool.py` | **新增** | 委托工具实现 |
| `agent/tools/registry.py` | 无（自动发现） | `discover_tools()` 自动导入新模块 |
| `agent/core/message_builder.py` | 小改 | 添加 `delegate_task` 工具使用指导到系统提示词 |
| `agent/core/agent.py` | 无 | `AIAgent` 类复用为子代理构造器 |

### 2.4 测试

- `tests/test_delegate_tool.py` — 测试子代理任务分发、结果返回、超时处理、错误隔离
- 使用 `MockLLMProvider` 模拟子代理行为

### 2.5 不涉及

- 不需要子进程管理
- 不需要跨进程通信
- 不需要新的依赖

---

## 3. 命令审批模式

### 3.1 背景

当前 ZLink Agent 的安全层包括三层：系统提示词阻止 + BeforeHook 链 + SecurityEventExtension。但没有"需要用户确认后再执行"的能力。对于高风险操作（文件删除、终端命令执行、数据修改等），应当能够暂停执行、询问用户、获得批准/拒绝后再继续。

### 3.2 设计方案

#### 3.2.1 审批模式配置

在 `AppConfig`/`AgentConfigPayload` 中增加：

```python
class ApprovalMode(str, Enum):
    ALLOW_ALL = "allow_all"          # 不审批，直接执行（默认，当前行为）
    APPROVE_HIGH_RISK = "approve"    # 高风险操作需审批
    REJECT_ALL = "reject_all"        # 拒绝所有高风险操作
```

#### 3.2.2 高风险标记机制

在工具注册时通过 `risk_level` 标记风险等级：

```python
registry.register(
    name="terminal",
    toolset="system",
    schema=TERMINAL_SCHEMA,
    handler=handle_terminal,
    risk_level="high",         # 新增参数
)
```

风险等级定义：

| 等级 | 示例工具 | 审批行为 |
|------|---------|---------|
| `low` | web_search, file_read, todo, clarify | 不需要审批 |
| `medium` | web_extract, file_write, skills_tool | 可配置是否需要审批 |
| `high` | terminal, file_delete | 严格审批 |

#### 3.2.3 Approval Hook

在 `agent/tools/security_hooks.py` 中添加一个 BeforeHook 函数：

```python
from agent.config_manager import load as load_config

def approval_hook(tool_name: str, args: dict) -> dict | None:
    """命令审批 BeforeHook。如果工具需要审批，暂停并询问用户。"""
    config = load_config()
    mode = config.approval_mode

    if mode == "allow_all":
        return None  # 放行

    risk_level = _get_tool_risk_level(tool_name)
    if mode == "reject_all" and risk_level in ("medium", "high"):
        return {"__block__": True, "__reason__": f"工具 {tool_name} 已被管理员禁用（审批模式: 全部拒绝）"}

    if mode == "approve" and risk_level == "high":
        # 触发审批流程：向用户发送审批请求
        # 通过 clarify_tool 机制询问用户
        approved = _ask_user_approval(tool_name, args)
        if not approved:
            return {"__block__": True, "__reason__": f"用户拒绝了工具 {tool_name} 的执行"}
        # 放行
        return None

    return None
```

#### 3.2.4 审批交互流程

```
用户: "删除 /tmp/test.sql 文件"
  → Agent 调用 file_delete(path="/tmp/test.sql")
  → BeforeHook 链:
      → system_prompt_block_hook (检查危险路径 → 通过)
      → approval_hook (high risk → 触发审批)
          → 向用户推送审批请求:
              "⚠️ 需要你的确认才能执行以下操作：
               工具: file_delete
               参数: path=/tmp/test.sql
               请选择：批准 / 拒绝"
          → 用户选择 "批准"
      → SecurityEventExtension (记录事件)
  → 执行工具
  → 用户看到结果
```

审批交互复用现有的 WebSocket 消息格式，通过 `clarify_tool.py` 风格的 Y/N 选择实现。

#### 3.2.5 审批记录

所有审批事件通过 EventBus 发布，可被 `log_everything` 和 `monitoring` 扩展记录。额外在 `agent/extensions/` 中新增 `audit_log.py` 扩展，专门记录审批日志到文件。

### 3.3 涉及文件

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `agent/tools/security_hooks.py` | **改** | 添加 `approval_hook` 函数，集成到 hook 链 |
| `agent/tools/registry.py` | **小改** | 注册时支持 `risk_level` 参数 |
| `agent/config_model.py` | **小改** | 添加 `approval_mode` 字段到 `AppConfig` |
| `agent/config_manager.py` | 无 | 配置自动序列化 |
| `backend/api/config_api.py` | **小改** | 前端可读写 `approval_mode` |
| `backend/schemas/config.py` | **小改** | 添加 `approval_mode` 到 schema |
| `web/src/pages/SettingsAgentPage.tsx` | **小改** | UI 添加审批模式选择 |
| `web/src/types/index.ts` | **小改** | 添加 `approval_mode` 到类型 |
| `agent/extensions/audit_log.py` | **新增** | 审批日志扩展 |

### 3.4 测试

- `tests/test_approval.py` — 测试三种审批模式的行为
- 测试 `approval_hook` 的阻断/放行逻辑
- 测试高风险工具被正确标记

### 3.5 不涉及

- 不需要修改已有工具的 handler 逻辑
- 不需要修改前端聊天界面核心
- 向后兼容：`allow_all` 是默认值，现有行为不变

---

## 4. 浏览器自动化工具

### 4.1 背景

当前 ZLink Agent 有 `web_tools.py`（网页搜索）和 `web_extract_tool.py`（网页内容提取），但都是通过 HTTP 请求获取内容，无法处理：
- JavaScript 渲染的页面（单页应用、动态内容）
- 需要登录后的页面（ERP 系统仪表盘）
- 表单交互（填写查询条件、点击导出按钮）
- 页面截图

### 4.2 技术选型

**Playwright**（MIT 协议，Microsoft 维护）：

| 要求 | Playwright |
|------|-----------|
| JS 渲染 | ✅ 完整 Chromium/Firefox/WebKit |
| 截图 | ✅ 全页截图、元素截图 |
| 表单交互 | ✅ fill/click/select/check |
| 等待策略 | ✅ wait_for_selector/wait_for_navigation |
| Cookie/会话管理 | ✅ context.cookies() / context.add_cookies() |
| 无头模式 | ✅ headless=True（默认） |
| 网络拦截 | ✅ route() |
| 安装 | `pip install playwright && playwright install chromium` |
| Python 版本 | 3.11+ 完美兼容 |

### 4.3 新文件: `agent/tools/browser_tool.py`

提供一个「浏览器」工具集，包含多个子工具：

```python
# 工具清单
BROWSER_TOOLS = [
    {
        "name": "browser_navigate",
        "description": "导航到指定 URL",
        "parameters": {"url": "string"}
    },
    {
        "name": "browser_screenshot",
        "description": "截取当前页面截图（全页）",
        "parameters": {}
    },
    {
        "name": "browser_click",
        "description": "点击页面上的元素",
        "parameters": {"selector": "string", "wait_after": "number (可选, ms)"}
    },
    {
        "name": "browser_fill",
        "description": "在输入框中填写文本",
        "parameters": {"selector": "string", "value": "string"}
    },
    {
        "name": "browser_get_text",
        "description": "获取页面元素的文本内容",
        "parameters": {"selector": "string"}
    },
    {
        "name": "browser_get_html",
        "description": "获取当前页面的 HTML 内容",
        "parameters": {}
    },
    {
        "name": "browser_evaluate",
        "description": "在浏览器中执行 JavaScript",
        "parameters": {"code": "string"}
    },
    {
        "name": "browser_close",
        "description": "关闭浏览器实例",
        "parameters": {}
    },
]
```

### 4.4 架构设计

```
agent/tools/browser_tool.py
├── _BrowserSession (单例，管理 Playwright browser + context)
│   ├── lazy 初始化（首次调用时启动 Chromium）
│   ├── 超时管理（闲置 5 分钟自动关闭）
│   └── Cookie 持久化（可选）
├── handle_browser_navigate(url)
├── handle_browser_screenshot()
├── handle_browser_click(selector, wait_after)
├── handle_browser_fill(selector, value)
├── handle_browser_get_text(selector)
├── handle_browser_get_html()
├── handle_browser_evaluate(code)
└── handle_browser_close()
```

#### 4.4.1 生命周期管理

- **Lazy 初始化**: 首次调用任浏览器工具时启动 Playwright Chromium 进程
- **会话复用**: 同一个对话轮次中多次调用复用同一个浏览器上下文（保持 cookie/登录状态）
- **自动关闭**: 闲置 5 分钟后自动关闭浏览器进程释放资源
- **每个会话独立**: 不同对话使用不同的 browser context 隔离状态

```python
class _BrowserSession:
    """浏览器会话单例管理"""
    _instance = None
    _browser = None
    _context = None
    _page = None
    _last_used = 0
    _lock = threading.Lock()

    @classmethod
    def get_page(cls):
        """获取当前页面，lazy 初始化"""
        with cls._lock:
            if cls._page is None:
                cls._start_browser()
            cls._last_used = time.time()
            return cls._page

    @classmethod
    def _start_browser(cls):
        """启动 Playwright Chromium"""
        import playwright.sync_api
        cls._playwright = playwright.sync_api.sync_playwright().start()
        cls._browser = cls._playwright.chromium.launch(headless=True)
        cls._context = cls._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
        )
        cls._page = cls._context.new_page()

    @classmethod
    def close(cls):
        """关闭浏览器实例"""
        with cls._lock:
            if cls._page:
                cls._page.close()
                cls._page = None
            if cls._context:
                cls._context.close()
                cls._context = None
            if cls._browser:
                cls._browser.close()
                cls._browser = None
            if cls._playwright:
                cls._playwright.stop()
                cls._playwright = None

    @classmethod
    def is_idle(cls):
        """检查是否闲置超时"""
        return cls._page is not None and (time.time() - cls._last_used) > 300
```

#### 4.4.2 安全约束

- **URL 过滤**: 默认阻止访问内网地址（127.0.0.1, 10.*, 172.16-31.*, 192.168.*）和文件协议（file://）
- **导航超时**: 30 秒
- **资源限制**: 单个页面最大 50MB 资源加载
- **弹窗自动关闭**: `page.on("dialog", lambda d: d.dismiss())`

### 4.5 涉及文件

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `agent/tools/browser_tool.py` | **新增** | 浏览器自动化工具模块 |
| `pyproject.toml` | **小改** | 添加 `playwright` 作为可选依赖 |
| `agent/tools/security_hooks.py` | **小改** | 将 `browser_navigate` 的 URL 纳入安全过滤 |

### 4.6 测试

- `tests/test_browser_tool.py` — 使用 Playwright 的 `chromium.launch(headless=True)` 在 CI 中运行
- 测试 navigate/screenshot/click/fill 核心流程
- 测试安全过滤（内网地址阻断）
- 测试闲置超时自动关闭

### 4.7 不涉及

- 不需要 CDP 直接管理
- 不需要分布式浏览器集群
- 不需要持久化 cookie 到磁盘（对 ERP 场景暂无需求）

---

## 5. 集成与兼容性分析

### 5.1 四个方向的相互影响

| 方向 | 影响其他 | 被其他影响 |
|------|---------|-----------|
| DeepSeek 提供商 | 无 | 无 |
| 子代理委托 | 消耗 LLM API 配额翻倍 | 需要安全层约束子代理行为 |
| 命令审批 | 影响所有高风险工具的执行流程 | 子代理调用工具时同样受审批约束 |
| 浏览器工具 | 增加新的工具类型 | 受安全层审批约束 |

### 5.2 向后兼容性

- DeepSeek 添加：无破坏性变更
- 子代理委托：新增工具，不影响现有工具行为
- 命令审批：默认 `allow_all` 模式，现有行为不变
- 浏览器工具：新增工具集，不影响现有 `web_tools.py`

### 5.3 依赖新增

| 方向 | 新增依赖 |
|------|---------|
| DeepSeek | 无 |
| 子代理委托 | 无 |
| 命令审批 | 无 |
| 浏览器工具 | `playwright` + `playwright install chromium` |

---

## 6. 实施顺序建议

考虑到"不着急，做扎实"的时间预期，建议按以下顺序实施：

```
Phase 1 — 立竿见影（半天）
├── DeepSeek 提供商添加（改 1 个文件，加 8 行配置）
├── 命令审批模式（核心安全能力）
│   ├── config_model.py 添加字段
│   ├── registry.py 添加 risk_level 支持
│   ├── security_hooks.py 添加 approval_hook
│   └── 前端 SettingsAgentPage 添加审批模式选择

Phase 2 — 核心新能力（1-2 天）
├── 浏览器自动化工具
│   ├── browser_tool.py 实现
│   ├── 安全层集成
│   └── 测试覆盖
├── 子代理委托
│   ├── delegate_tool.py 实现
│   ├── message_builder.py 添加系统提示
│   └── 测试覆盖

Phase 3 — 打磨和测试（1 天）
├── 集成测试
├── 边界情况处理
├── 文档更新（AGENTS.md / README.md）
└── CHANGELOG.md 更新
```
