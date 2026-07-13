# ERP 数据源路由实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-subagent-driven-development (recommended) or superpowers-executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 LLM 根据当前 ERP 启用状态自动选择正确的数据源取数，不擅自猜测。

**Architecture:** 两层加固。Layer 1 在 system prompt 末尾动态注入当前 ERP 启用状态和规则，Layer 2 在 MCP 工具 description 中标注数据源归属。两个改动点互不依赖。

**Tech Stack:** Python 3.11+, pytest, MCP JSON-RPC

---

### Task 1: Layer 1 — message_builder 新增 `erp_context` 参数

**Files:**
- Modify: `agent/core/message_builder.py:33-92`
- Test: `tests/test_message_builder.py`

- [ ] **Step 1: Write the failing test**

```python
def test_erp_context_appended_when_provided():
    result = build_system_prompt(base="你是助手", erp_context="YonSuite ✅")
    assert result is not None
    assert "可用数据源" in result
    assert "YonSuite" in result


def test_erp_context_empty_when_not_provided():
    result = build_system_prompt(base="你是助手")
    # Should not contain the section when no erp_context given
    assert "可用数据源" not in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_message_builder.py -v`
Expected: `FAILED — `build_system_prompt()` got unexpected keyword argument 'erp_context'`

- [ ] **Step 3: Add `erp_context` parameter to `build_system_prompt`**

In `agent/core/message_builder.py`:

```python
def build_system_prompt(
    base: str,
    memory_store: object | None = None,
    memory_context: str = "",
    skill_index: str = "",
    skill_detail: str = "",
    erp_context: str = "",         # ← 新增
) -> str | None:
```

After the # 6 sub-agent delegation section (before `if len(parts) == 1: return None`), add:

```python
    # 7. ERP 数据源上下文（动态注入）
    if erp_context:
        parts.append(erp_context)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_message_builder.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add agent/core/message_builder.py tests/test_message_builder.py
git commit -m "feat(message_builder): add erp_context param for dynamic ERP status injection"
```

---

### Task 2: Layer 1 — agent.py 读取 ERP 配置并格式化

**Files:**
- Modify: `agent/core/agent.py:367-371`
- Test: `tests/test_agent_loop.py`

- [ ] **Step 1: Write the failing test**

```python
from agent.config_model import AppConfig


def test_build_system_prompt_includes_erp_context_when_enabled(monkeypatch):
    """当 erp_clients 中有启用项时，system prompt 应包含可用数据源信息"""
    cfg = AppConfig(approval_mode="allow_all")
    cfg.erp_clients = {
        "yonsuite": {"enabled": True, "tenant_id": "t1", "app_key": "k1", "app_secret": "s1"},
        "nc": {"enabled": False},
    }
    monkeypatch.setattr("agent.config_manager.load", lambda: cfg)

    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    from agent.core.llm_client import LLMClient
    from tests.conftest import MockLLMProvider
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=MockLLMProvider())

    sys_prompt = agent._build_system_prompt()
    assert sys_prompt is not None
    assert "可用数据源" in sys_prompt
    assert "YonSuite" in sys_prompt
    assert "NC" in sys_prompt
    # YonSuite 已启用应有 ✅
    assert "YonSuite" in sys_prompt  # name
    # NC 未启用应有 ❌
    assert "未启用" in sys_prompt


def test_build_system_prompt_no_erp_context_when_none_enabled(monkeypatch):
    """当所有 ERP 都未启用时，不注入可用数据源 section"""
    cfg = AppConfig(approval_mode="allow_all")
    cfg.erp_clients = {}
    monkeypatch.setattr("agent.config_manager.load", lambda: cfg)

    agent = AIAgent(api_key="sk-fake", base_url="x", model="gpt-4o", max_iterations=3)
    from agent.core.llm_client import LLMClient
    from tests.conftest import MockLLMProvider
    agent._llm = LLMClient(api_key="sk-fake", base_url="x", provider=MockLLMProvider())

    sys_prompt = agent._build_system_prompt()
    assert sys_prompt is None or "可用数据源" not in sys_prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_agent_loop.py::test_build_system_prompt_includes_erp_context_when_enabled -v`
Expected: FAIL — new test not found yet

- [ ] **Step 3: Implement `_build_system_prompt` ERP logic**

In `agent/core/agent.py`, modify `_build_system_prompt()`:

```python
def _build_system_prompt(self) -> str | None:
    # 读取 ERP 配置，生成可用数据源上下文
    erp_context = self._build_erp_context()
    return build_system_prompt(
        base=self.system_prompt,
        memory_store=self._memory_store,
        erp_context=erp_context,
    )

def _build_erp_context(self) -> str:
    """生成可用数据源列表文本，供 system prompt 注入。"""
    try:
        from agent import config_manager
        cfg = config_manager.load()
    except Exception:
        return ""

    erp_clients = cfg.erp_clients or {}
    if not erp_clients:
        return ""

    # ERP 显示名称映射
    ERP_LABELS = {"yonsuite": "YonSuite", "nc": "NC"}

    lines = ["## 可用数据源", "当前已启用的 ERP 系统："]
    enabled_count = 0
    for name, ecfg in erp_clients.items():
        enabled = bool(ecfg.get("enabled", False)) if isinstance(ecfg, dict) else False
        label = ERP_LABELS.get(name, name)
        if enabled:
            lines.append(f"  • {label} ✅ — 可查询销售订单、客户等数据")
            enabled_count += 1
        else:
            lines.append(f"  • {label} ❌ — 未启用")

    if enabled_count > 1:
        lines.append("")
        lines.append("规则：")
        lines.append('- 如果用户未指明系统 → 必须先询问"查哪个系统的数据"')
        lines.append('- 如果用户已指定系统名称（如"查 NC 的销售订单"）→ 直接执行')
    elif enabled_count == 1:
        lines.append("")
        lines.append("规则：")
        lines.append("- 使用已启用 ✅ 系统的对应工具取数")

    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_agent_loop.py::test_build_system_prompt_includes_erp_context_when_enabled tests/test_agent_loop.py::test_build_system_prompt_no_erp_context_when_none_enabled -v`
Expected: Both PASS

- [ ] **Step 5: Run full test suite to verify no regressions**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add agent/core/agent.py tests/test_agent_loop.py
git commit -m "feat(agent): inject ERP enable status and routing rules into system prompt"
```

---

### Task 3: Layer 2 — MCP 工具 description 标注数据源归属

**Files:**
- Modify: `agent/tools/mcp_manager.py:335-353`
- No test file changes needed (no existing mcp_manager tests; adding minimal test)

- [ ] **Step 1: Write the failing test**

In `tests/test_mcp_manager.py` (new file):

```python
"""Tests for agent/tools/mcp_manager — MCP tool description labeling."""


def test_mcp_tool_description_tagged_with_source_label():
    """已知 ERP 的 MCP 服务器注册工具时，description 应包含数据源标签。"""
    from agent.tools.mcp_manager import MCPServerConnection

    # 模拟一个 yonsuite MCP 服务器的 tool 列表
    conn = MCPServerConnection(
        "yonsuite",
        {"transport": "stdio", "command": "python", "args": [], "timeout": 120},
    )
    conn._tools = [
        {
            "name": "ys_api",
            "description": "调用 YonSuite 开放 API",
            "inputSchema": {"type": "object", "properties": {}},
        }
    ]

    # 直接调用 _register_tools 会触发 asyncio + registry — 改用内部逻辑手工验证
    # 检查 _convert_mcp_tool_schema 是否会追加标签
    from agent.tools.mcp_manager import _convert_mcp_tool_schema

    schema = _convert_mcp_tool_schema("yonsuite", conn._tools[0])
    assert "【数据源：YonSuite】" in schema.get("description", "")


def test_non_erp_mcp_tool_not_tagged():
    """非 ERP 的 MCP 服务器（如 chart server）不应被打上数据源标签。"""
    from agent.tools.mcp_manager import _convert_mcp_tool_schema

    schema = _convert_mcp_tool_schema(
        "mcp-server-chart",
        {
            "name": "render_chart",
            "description": "渲染图表",
            "inputSchema": {"type": "object", "properties": {}},
        },
    )
    assert "【数据源" not in schema.get("description", "")


def test_erp_label_added_in_register_tools(monkeypatch):
    """验证 _register_tools 实际调用注册时 description 被正确追加。"""
    from agent.tools.mcp_manager import MCPServerConnection
    from agent.tools.registry import registry

    conn = MCPServerConnection(
        "mcp-nc",
        {"transport": "stdio", "command": "python", "args": [], "timeout": 120},
    )
    conn._tools = [
        {
            "name": "query_sales_orders",
            "description": "查询 NC 销售订单",
            "inputSchema": {"type": "object", "properties": {}},
        }
    ]

    # 手动运行注册逻辑，验证 description 被追加了标签
    conn._register_tools()

    entry = registry.get_entry("mcp_mcp-nc_query_sales_orders")
    assert entry is not None
    assert "【数据源：NC】" in entry.description
    assert "查询 NC 销售订单" in entry.description

    # 清理
    registry.deregister("mcp_mcp-nc_query_sales_orders")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_mcp_manager.py -v`
Expected: FAIL — `_convert_mcp_tool_schema` 还不加标签

- [ ] **Step 3: Read `_convert_mcp_tool_schema` function to confirm code**

Read `agent/tools/mcp_manager.py` lines 88-110 to see the exact return block.

- [ ] **Step 4: Add ERP label code to `_convert_mcp_tool_schema`**

In `agent/tools/mcp_manager.py:88-110`, modify the function to add ERP source label before the return:

```python
def _convert_mcp_tool_schema(server_name: str, tool: dict) -> dict:
    """Convert an MCP tool definition to OpenAI function-calling schema."""
    safe_server = _sanitize_name(server_name)
    safe_tool = _sanitize_name(tool["name"])
    prefixed = f"mcp_{safe_server}_{safe_tool}"

    input_schema = tool.get("inputSchema", {})
    params = {"type": "object", "properties": {}, "required": []}

    if input_schema:
        params["properties"] = input_schema.get("properties", {})
        params["required"] = input_schema.get("required", [])

    description = tool.get("description", f"MCP tool: {tool['name']}")
    # Redact potential credential leakage in descriptions
    if len(description) > 2000:
        description = description[:2000] + "..."

    # ERP 数据源标签：在 description 末尾标注数据来源
    ERP_SOURCE_LABELS = {"yonsuite": "YonSuite", "mcp-nc": "NC"}
    source_label = ERP_SOURCE_LABELS.get(server_name)
    if source_label:
        description = f"{description.rstrip()} 【数据源：{source_label}】"

    return {
        "name": prefixed,
        "description": description,
        "parameters": params,
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_mcp_manager.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All existing tests still pass

- [ ] **Step 7: Commit**

```bash
git add agent/tools/mcp_manager.py tests/test_mcp_manager.py
git commit -m "feat(mcp_manager): tag MCP tool descriptions with ERP source label"
```