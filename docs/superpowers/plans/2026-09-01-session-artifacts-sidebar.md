# 会话产物侧边栏（Session Artifacts Sidebar）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 zlink-agent 加一个可手动展开/收起的右侧「会话产物」栏，并把一次会话产出的所有文件收敛到唯一的物理归属 —— 会话目录 `data/sessions/<sid>/artifacts/`。

**Architecture:** 后端三件套：`session_manager` 从扁平 `<sid>.json` 改为 `<sid>/session.json` 目录布局（幂等迁移）；一个 `ContextVar` 把当前会话 id 送进工具层；一处 before-hook 把文件/终端工具的相对路径归一到会话产物目录，一处 after-hook 把写到目录外的路径登记进 `external.jsonl`。前端一个 `ArtifactsPanel`（列表 + 尽力而为的 iframe/markdown/图片预览 + 浏览器打开/下载/Finder 三操作），数据来自 4 个只读端点，刷新靠复用现有 WS 帧，不新增事件类型。

**Tech Stack:** Python 3.11 / FastAPI / pytest（零网络零 LLM）· React 19 + Vite + TypeScript（**不新增任何依赖**）· `@tabler/icons-react`（已装）

**Spec:** `docs/superpowers/specs/2026-09-01-session-artifacts-sidebar-design.md` —— 本计划逐节实现它，执行时两份一起读。

## Global Constraints

以下为项目级硬约束，每个任务都隐含遵守（值抄自 spec 与 `AGENTS.md`）：

- 测试命令 `.venv/bin/python -m pytest tests/ -q`；lint `ruff check . && ruff format --check .`；**任何任务不得引入网络或真实 LLM 调用**，一律用 `MockLLMProvider` / `make_tool_call_response` / FastAPI `TestClient` / `tmp_path`。
- 前端零新依赖：不引 vitest、echarts、codemirror、mermaid。类型检查 `cd web && npx tsc -b`，构建 `cd web && npm run build`。
- ❌ 不改区：`agent/tools/registry.py` 内部（只用 `add_before_hook`/`add_after_hook` 公开 API）、`agent/tools/security_hooks.py`、`backend/schemas/session.py` 既有字段名。
- 冻结契约：`AIAgent.__init__` 签名、`run_conversation(...)` 的 6 个返回键 `{final_response, messages, api_calls, token_usage, completed, error}`。本计划只**传**已有参数 `session_id`，不加参数。
- 后端无鉴权（保护靠文件权限 + 绑 `127.0.0.1`）：任何读文件的端点必须把作用域收紧到 `<sid>/artifacts/` 子树，永不吐 `session.json` / `external.jsonl`。
- 会话 id 一律经 `^[A-Za-z0-9_-]{1,64}$` 校验（挡路径穿越；`create_session` 生成的是 `uuid4().hex[:8]`）。
- 运行时数据只写 `DATA_DIR`（`~/.zlink-agent/data/`），**绝不写源码仓库**。
- 每个任务结尾提交一次，commit message 用 `feat:` / `fix:` / `docs:` / `chore:` 前缀。
- 版本号本次收口到 `1.13.0`（`pyproject.toml` 为单一来源 + 根 `package.json` 同步）。

---

## 文件结构

| 文件 | 责任 | 任务 |
| --- | --- | --- |
| `agent/session_manager.py` | 会话布局唯一权威：目录访问器、CRUD、`sid` 校验、一次性迁移 | T1 |
| `agent/session_context.py` | 把"当前会话"送进工具层（ContextVar + 产物目录解析） | T2 |
| `agent/core/agent_adapter.py` | 回合入口 set ContextVar；产物目录注入 system prompt | T2 |
| `agent/core/message_builder.py` | 新增 `artifact_dir` 片段（与 `erp_context` 同机制） | T2 |
| `agent/tools/cronjob_tools.py` | 把已创建的 sid 传给 `run_conversation`（+ `tests/test_cronjob_artifact_session.py` 守护） | T2 |
| `agent/tools/session_artifact_hook.py` | 路径归一（before）+ 会话外写出登记（after）+ external 读取 | T3 T4 |
| `backend/schemas/session_artifact.py` | 产物 API 的 Pydantic 模型 | T5 |
| `backend/api/session_artifacts.py` | 列表 / 文件 / zip / reveal 四端点 + 路径校验 | T5 T6 T7 |
| `backend/main.py` | lifespan 调迁移 + hook 安装；挂 router | T1 T4 T5 |
| `agent/skills/{u8,nc,yonsuite}/SKILL.md` | 产物落点文案（各 1 行） | T8 |
| `web/src/api/http.ts` | 导出 `apiUrl()`（iframe/下载要绝对 URL） | T9 |
| `web/src/hooks/useChat.ts` | 新增 `onToolActivity` 回调 | T9 |
| `web/src/hooks/useSessionArtifacts.ts` | 产物列表拉取 + 防抖刷新 | T9 |
| `web/src/components/ArtifactsPanel.tsx` | 面板 UI：列表 / 预览 / 操作 | T10 |
| `web/src/components/Layout.tsx` | 第三列布局 + 顶栏开关 + `⌘B` + Outlet context | T10 |
| `web/src/pages/ChatPage.tsx` | 接收 `bumpArtifacts`，在工具/回合结束时递增 | T10 |
| `web/src/styles/global.css` | 面板样式 | T10 |
| `web/src/types/index.ts` | `ArtifactItem` / `ArtifactListResponse` 类型 | T9 |
| `.gitignore`、`pyproject.toml`、`package.json`、`CHANGELOG.md`、`README.md`、`AGENTS.md` | 收口 | T11 |

---

## Task 1: 会话目录化 + sid 校验 + 幂等迁移

**Files:**

- Modify: `agent/session_manager.py`（全文 125 行，路径逻辑集中在 `SESSIONS_DIR`/`INDEX_FILE` 与 4 个函数）
- Test: `tests/test_session_layout.py`（新建）

**Interfaces:**

- Consumes: 无（第一个任务）
- Produces: `session_manager.session_dir(sid) -> Path`、`session_manager.session_file(sid) -> Path`、`session_manager.artifacts_dir(sid) -> Path`、`session_manager.ensure_artifacts_dir(sid) -> Path`、`session_manager.migrate_session_layout() -> int`、`session_manager.is_valid_session_id(sid) -> bool`、常量 `SESSIONS_DIR`、`_SAFE_ID_RE`

- [ ] **Step 1: 写失败测试（目录化 CRUD + 迁移 + 穿越防护）**

创建 `tests/test_session_layout.py`：

```python
"""会话目录化：CRUD 走 <sid>/session.json，迁移幂等，非法 sid 不落盘。"""

import json

import pytest

from agent import search_index
from agent import session_manager as sm


@pytest.fixture
def sessions_root(tmp_path, monkeypatch):
    """把 sessions 目录与 FTS 库都指向 tmp，测试不碰真实 ~/.zlink-agent。"""
    root = tmp_path / "sessions"
    root.mkdir()
    monkeypatch.setattr(sm, "SESSIONS_DIR", root)
    monkeypatch.setattr(sm, "INDEX_FILE", root / "index.json")
    monkeypatch.setattr(search_index, "DB_PATH", tmp_path / "search.db")
    return root


def test_create_session_makes_dir_and_artifacts(sessions_root):
    sid = sm.create_session("报表")
    assert (sessions_root / sid / "session.json").is_file()
    assert (sessions_root / sid / "artifacts").is_dir()
    assert not (sessions_root / f"{sid}.json").exists()


def test_save_and_load_roundtrip_uses_session_json(sessions_root):
    sid = sm.create_session()
    msgs = [{"role": "user", "content": "查一下销售订单"}]
    sm.save_session(sid, msgs, title="销售订单查询")
    assert (sessions_root / sid / "session.json").is_file()
    assert sm.load_session(sid) == msgs
    entry = next(e for e in sm.list_sessions() if e["id"] == sid)
    assert entry["title"] == "销售订单查询"


def test_delete_session_removes_dir_with_artifacts(sessions_root):
    sid = sm.create_session()
    art = sm.ensure_artifacts_dir(sid)
    (art / "report.html").write_text("<h1>x</h1>", encoding="utf-8")
    (sm.session_dir(sid) / "external.jsonl").write_text("{}", encoding="utf-8")
    sm.delete_session(sid)
    assert not (sessions_root / sid).exists()
    assert all(e["id"] != sid for e in sm.list_sessions())


def test_load_falls_back_to_legacy_flat_file(sessions_root):
    legacy = sessions_root / "abcd1234.json"
    legacy.write_text(
        json.dumps({"id": "abcd1234", "title": "旧", "messages": [{"role": "user", "content": "hi"}]}), encoding="utf-8"
    )
    assert sm.load_session("abcd1234") == [{"role": "user", "content": "hi"}]


def test_migrate_moves_flat_files_once(sessions_root):
    for sid in ("aaaa1111", "bbbb2222"):
        (sessions_root / f"{sid}.json").write_text(
            json.dumps({"id": sid, "title": sid, "messages": []}), encoding="utf-8"
        )
    (sessions_root / "index.json").write_text("[]", encoding="utf-8")

    assert sm.migrate_session_layout() == 2
    for sid in ("aaaa1111", "bbbb2222"):
        assert (sessions_root / sid / "session.json").is_file()
        assert (sessions_root / sid / "artifacts").is_dir()
        assert not (sessions_root / f"{sid}.json").exists()
    # 幂等：再跑一次不报错、不搬东西
    assert sm.migrate_session_layout() == 0


def test_migrate_skips_illegal_names_but_keeps_sibling(sessions_root):
    (sessions_root / "evil.json").write_text("{}", encoding="utf-8")  # 非 8 位 hex 风格名 → 跳过
    (sessions_root / "cccc3333.json").write_text(
        json.dumps({"id": "cccc3333", "title": "", "messages": []}), encoding="utf-8"
    )
    sm.migrate_session_layout()
    assert (sessions_root / "evil.json").is_file()
    assert (sessions_root / "cccc3333" / "session.json").is_file()


def test_illegal_session_id_never_writes_outside(sessions_root, tmp_path):
    evil = "../../../../../" + tmp_path.parent.name + "/pwn"
    sm.save_session(evil, [{"role": "user", "content": "x"}], title="t")
    assert not (tmp_path.parent / "pwn.json").exists()
    assert list(sessions_root.glob("*pwn*")) == []
    assert sm.load_session(evil) == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_session_layout.py -q`
Expected: FAIL —— `AttributeError: module 'agent.session_manager' has no attribute 'session_dir'` / `ensure_artifacts_dir` / `migrate_session_layout`

- [ ] **Step 3: 改写 `agent/session_manager.py`**

顶部 import 与常量段（替换现有 `import` 块与 `SESSIONS_DIR`/`INDEX_FILE` 两行）改为：

```python
import json
import logging
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from agent import search_index
from agent.utils import DATA_DIR, atomic_json_write

logger = logging.getLogger(__name__)

SESSIONS_DIR = DATA_DIR / "sessions"
INDEX_FILE = SESSIONS_DIR / "index.json"

# 会话 id 来自客户端（WS URL），必须挡住 ../ 之类的路径穿越。
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def is_valid_session_id(session_id: str) -> bool:
    return bool(session_id) and _SAFE_ID_RE.match(session_id) is not None


def session_dir(session_id: str) -> Path:
    """`data/sessions/<sid>/`（未校验，调用方负责或用下面的安全版）。"""
    return SESSIONS_DIR / session_id


def session_file(session_id: str) -> Path:
    return session_dir(session_id) / "session.json"


def artifacts_dir(session_id: str) -> Path:
    return session_dir(session_id) / "artifacts"


def ensure_artifacts_dir(session_id: str) -> Path:
    d = artifacts_dir(session_id)
    d.mkdir(parents=True, exist_ok=True)
    return d
```

四个 CRUD 函数改成目录版（`_load_index` / `_save_index` / `_ensure_dirs` / `auto_title` **保持不动**）：

```python
def create_session(title: str = "") -> str:
    """Create a new session and return its ID."""
    session_id = uuid.uuid4().hex[:8]
    now = datetime.now().isoformat()
    entry = {
        "id": session_id,
        "title": title or "新对话",
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
    }
    index = _load_index()
    index.append(entry)
    _save_index(index)

    session_dir(session_id).mkdir(parents=True, exist_ok=True)
    ensure_artifacts_dir(session_id)
    atomic_json_write(
        session_file(session_id),
        {"id": session_id, "title": entry["title"], "messages": []},
    )
    return session_id


def _writable_session_file(session_id: str) -> Path | None:
    """会话消息文件路径。非法 id 返回 None（拒绝写盘）。"""
    if not is_valid_session_id(session_id):
        logger.warning("忽略非法 session_id，未写盘: %r", session_id)
        return None
    d = session_dir(session_id)
    if not d.exists():
        d.mkdir(parents=True, exist_ok=True)
        ensure_artifacts_dir(session_id)
    return session_file(session_id)


def save_session(session_id: str, messages: list[dict], title: str = ""):
    """Persist session messages and update index."""
    _ensure_dirs()
    if not session_id:
        return
    target = _writable_session_file(session_id)
    if target is None:
        return
    atomic_json_write(target, {"id": session_id, "title": title, "messages": messages})

    index = _load_index()
    for entry in index:
        if entry["id"] == session_id:
            entry["updated_at"] = datetime.now().isoformat()
            entry["message_count"] = len(messages)
            if title:
                entry["title"] = title
            break
    _save_index(index)

    search_index.index_session(session_id, messages, title)


def load_session(session_id: str) -> list[dict]:
    """Load messages for a session. Returns empty list if not found."""
    if not is_valid_session_id(session_id):
        return []
    for candidate in (session_file(session_id), SESSIONS_DIR / f"{session_id}.json"):
        if candidate.is_file():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                return data.get("messages", [])
            except (json.JSONDecodeError, OSError):
                return []
    return []


def delete_session(session_id: str):
    """Remove session from index and wipe its directory (artifacts included)."""
    index = _load_index()
    index = [e for e in index if e["id"] == session_id]
    _save_index(index)

    if is_valid_session_id(session_id):
        shutil.rmtree(session_dir(session_id), ignore_errors=True)
        legacy = SESSIONS_DIR / f"{session_id}.json"
        if legacy.exists():
            legacy.unlink()

    search_index.delete_session(session_id)
```

文件末尾追加迁移函数：

```python
def migrate_session_layout() -> int:
    """一次性把扁平 ``<sid>.json`` 搬进 ``<sid>/session.json``。幂等。

    在 ``backend/main.py`` lifespan 里调用。单个会话失败只记日志，绝不
    抛出 —— 后端必须能在半成品布局下正常启动。返回实际处理条数。
    """
    _ensure_dirs()
    moved = 0
    for legacy in sorted(SESSIONS_DIR.glob("*.json")):
        sid = legacy.stem
        if sid == "index" or not is_valid_session_id(sid):
            if sid != "index":
                logger.warning("跳过非法会话文件名: %s", legacy.name)
            continue
        target_dir = session_dir(sid)
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            ensure_artifacts_dir(sid)
            if not legacy.exists():
                continue
            target = target_dir / "session.json"
            if target.exists():
                # 目录版已有数据 → 扁平文件是陈旧副本
                legacy.unlink()
            else:
                legacy.rename(target)
            moved += 1
        except OSError as e:
            logger.warning("会话布局迁移失败 %s: %s", sid, e)
    return moved
```

- [ ] **Step 4: 在 lifespan 里调用迁移 + 加 `.gitignore` 白名单**

`backend/main.py` 的 `lifespan` 内，`search_index.init_db()` 那段之后、`_lap("search_index")` 之前插入：

```python
    from agent import session_manager

    n_moved = session_manager.migrate_session_layout()
    if n_moved:
        _logger.info("会话布局迁移完成: %d 个会话 → 目录布局", n_moved)
    _lap("session_layout")
```

`.gitignore` 第 13 行 `docs/` 之后追加两行，让设计文档不再需要 `git add -f`：

```
!docs/
!docs/superpowers/
```

- [ ] **Step 5: 跑测试确认通过（含存量全绿）**

Run: `.venv/bin/python -m pytest tests/test_session_layout.py -q && .venv/bin/python -m pytest tests/ -q`
Expected: 新测试 8 passed；全量 ≥526 passed 且 0 failed（`test_chat_async.py` 已整体 monkeypatch `save/load_session`，不受影响）

- [ ] **Step 6: Commit**

```bash
git add agent/session_manager.py backend/main.py .gitignore tests/test_session_layout.py
git commit -m "feat: store sessions as per-session directories with artifacts dir"
```

---

## Task 2: 会话上下文 + system prompt 注入 + cronjob 归属

**Files:**

- Create: `agent/session_context.py`
- Modify: `agent/core/agent_adapter.py`（`run_conversation_async` 开头 `effective_session_id` 处、`_build_system_prompt()`）
- Modify: `agent/core/message_builder.py`（`build_system_prompt` 新增 `artifact_dir` 形参）
- Modify: `agent/tools/cronjob_tools.py:400`（补 `session_id=session_id`）
- Test: `tests/test_session_context.py`（新建）

**Interfaces:**

- Consumes: `session_manager.artifacts_dir(sid)`、`ensure_artifacts_dir(sid)`（T1）
- Produces: `session_context.current_session_id: ContextVar[str | None]`、`set_current_session(sid)`、`get_current_session() -> str | None`、`current_artifacts_dir() -> Path | None`、`ensure_current_artifacts_dir() -> Path | None`；`build_system_prompt(..., artifact_dir: str = "")`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_session_context.py`：

```python
"""ContextVar 会话上下文：产物目录解析 + 未设会话时返回 None。"""

from pathlib import Path

import pytest

from agent import session_manager as sm
from agent import session_context as ctx


@pytest.fixture
def sessions_root(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    root.mkdir()
    monkeypatch.setattr(sm, "SESSIONS_DIR", root)
    monkeypatch.setattr(sm, "INDEX_FILE", root / "index.json")
    return root


def test_none_by_default():
    assert ctx.get_current_session() is None
    assert ctx.current_artifacts_dir() is None
    assert ctx.ensure_current_artifacts_dir() is None


def test_resolves_to_session_artifacts(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    try:
        assert ctx.get_current_session() == sid
        assert ctx.current_artifacts_dir() == sessions_root / sid / "artifacts"
        made = ctx.ensure_current_artifacts_dir()
        assert isinstance(made, Path) and made.is_dir()
    finally:
        ctx.set_current_session(None)


def test_empty_string_session_means_no_session(sessions_root):
    ctx.set_current_session("")
    assert ctx.get_current_session() is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_session_context.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'agent.session_context'`

- [ ] **Step 3: 新建 `agent/session_context.py`**

```python
"""当前会话上下文 —— 把 session_id 送进工具层，不污染工具签名。

设置点在 :meth:`agent.core.agent_adapter.AIAgent.run_conversation_async`。
工具执行走 ``asyncio.to_thread(registry.dispatch, ...)``，而 ``to_thread``
会 ``copy_context()``，因此 handler / hook 线程内能读到本值；
``FileMutationQueue.enqueue`` 在调用线程内带锁执行，同样可见。

未设置（单测、直接调用工具、未来 CLI）时一切返回 ``None``，调用方必须
回退到改动前的行为（进程 cwd），这是本模块最重要的兼容性约定。
"""

from __future__ import annotations

import contextvars
from pathlib import Path

current_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "zlink_current_session_id", default=None
)


def set_current_session(session_id: str | None) -> None:
    """Normalize empty strings to None so downstream checks stay simple."""
    current_session_id.set(session_id or None)


def get_current_session() -> str | None:
    return current_session_id.get()


def current_artifacts_dir() -> Path | None:
    """本次会话的产物目录（不创建）。无会话上下文时返回 None。"""
    sid = current_session_id.get()
    if not sid:
        return None
    from agent import session_manager

    return session_manager.artifacts_dir(sid)


def ensure_current_artifacts_dir() -> Path | None:
    """本次会话的产物目录，不存在则创建。无会话上下文时返回 None。"""
    sid = current_session_id.get()
    if not sid:
        return None
    from agent import session_manager

    return session_manager.ensure_artifacts_dir(sid)


__all__ = [
    "current_session_id",
    "set_current_session",
    "get_current_session",
    "current_artifacts_dir",
    "ensure_current_artifacts_dir",
]
```

- [ ] **Step 4: 最小实现（ContextVar 生效 + prompt 片段 + cronjob 传 sid）**

`agent/core/agent_adapter.py`：import 段加一行（放在 `from agent.core.message_builder import ...` 之后）：

```python
from agent.session_context import set_current_session
```

`run_conversation_async` 内，把

```python
        effective_session_id = session_id or ""
        self._session_id = effective_session_id
```

改成：

```python
        effective_session_id = session_id or ""
        self._session_id = effective_session_id
        set_current_session(effective_session_id)
```

`_build_system_prompt()` 改成：

```python
def _build_system_prompt(self) -> str | None:
    erp_context = self._build_erp_context()
    return build_system_prompt(
        base=self.system_prompt,
        memory_store=self._memory_store,
        erp_context=erp_context,
        artifact_dir=self._build_artifact_dir_text(),
    )


@staticmethod
def _build_artifact_dir_text() -> str:
    """会话产物目录说明。无会话上下文时返回空串（不注入）。"""
    from agent.session_context import ensure_current_artifacts_dir

    d = ensure_current_artifacts_dir()
    if d is None:
        return ""
    return (
        f"本次会话的产物目录：`{d}`\n"
        "- 写文件工具（write_file / patch）与终端的**相对路径默认落在此目录**，"
        "生成的报告、图表、导出文件都用相对路径，例如 `write_file('report_2026-09-01.html')`；"
        "用户界面会在侧边栏直接列出这些产物。\n"
        "- **不要**把产物写到 `~/Desktop`、仓库目录或 `/tmp`，除非用户明确要求绝对路径。\n"
        "- 只有用户给了绝对路径时才用绝对路径；技能自带脚本请用技能的绝对路径。"
    )
```

`agent/core/message_builder.py`：`build_system_prompt` 形参表在 `erp_context: str = "",` 后加一行 `artifact_dir: str = "",`；在 `# 6. ERP 数据源上下文` 段之后、`if len(parts) == 1:` 之前插入：

```python
    # 7. 会话产物目录（动态注入）
    if artifact_dir:
        parts.append("## 会话产物\n" + artifact_dir)
```

`agent/tools/cronjob_tools.py:400`：

```python
        result = agent.run_conversation(
            user_message=prompt,
            system_message=system_with_memory,
            session_id=session_id,
        )
```

- [ ] **Step 5: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_session_context.py tests/test_message_builder.py tests/test_contract_freeze.py -q`
Expected: PASS（`test_contract_freeze.py` 必须仍然全绿 —— 我们没有动构造签名和返回键）

- [ ] **Step 6: 加 system prompt 注入与冻结契约的守护测试**

`tests/test_session_context.py` 末尾追加：

```python
def test_system_prompt_contains_artifact_dir(sessions_root):
    from agent.core.message_builder import build_system_prompt

    sid = sm.create_session()
    ctx.set_current_session(sid)
    try:
        text = build_system_prompt(base="B", artifact_dir=f"本次会话的产物目录：`{sm.artifacts_dir(sid)}`")
    finally:
        ctx.set_current_session(None)
    assert "## 会话产物" in text
    assert str(sid) in text


def test_system_prompt_unchanged_without_artifact_dir():
    from agent.core.message_builder import build_system_prompt

    assert build_system_prompt(base="B") != "B"  # 仍会注入"当前信息"
    assert "## 会话产物" not in (build_system_prompt(base="B") or "")


def test_run_conversation_signature_frozen():
    """只允许**传**已有的 session_id 参数，不得增删形参。"""
    import inspect

    from agent.core.agent_adapter import AIAgent

    params = list(inspect.signature(AIAgent.run_conversation).parameters)
    assert params == [
        "self",
        "user_message",
        "system_message",
        "conversation_history",
        "stream_callback",
        "reasoning_callback",
        "stop_event",
        "session_id",
    ]
```

- [ ] **Step 7: 定时任务产物归属的回归测试**

创建 `tests/test_cronjob_artifact_session.py`：

```python
"""cronjob 必须把自己创建的 sid 透传给冻结入口 run_conversation（否则产物无归属）。"""

from agent import config_manager, fact_memory, memory_manager, search_index
from agent import session_manager as sm
from agent import skill_manager
from agent.config_model import AppConfig
from agent.tools import cronjob_tools as cj


def test_job_prompt_passes_session_id(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    root.mkdir()
    monkeypatch.setattr(sm, "SESSIONS_DIR", root)
    monkeypatch.setattr(sm, "INDEX_FILE", root / "index.json")
    monkeypatch.setattr(search_index, "DB_PATH", tmp_path / "search.db")

    cfg = AppConfig(llm_api_key="sk-test", llm_base_url="http://x", llm_model="m")
    monkeypatch.setattr(config_manager, "load", lambda: cfg)
    monkeypatch.setattr(fact_memory, "init_store", lambda *a, **k: None)
    monkeypatch.setattr(memory_manager, "get_context", lambda *a, **k: "")
    monkeypatch.setattr(skill_manager, "get_active_instructions", lambda *a, **k: "")
    monkeypatch.setattr(skill_manager, "get_active_skills", lambda *a, **k: [])

    seen: dict = {}

    class FakeAgent:
        system_prompt = "P"

        def run_conversation(self, **kw):
            seen.update(kw)
            return {
                "final_response": "ok",
                "messages": [],
                "api_calls": 1,
                "token_usage": None,
                "completed": True,
                "error": None,
            }

    import agent.agent as agent_mod

    monkeypatch.setattr(agent_mod, "AIAgent", FakeAgent)

    sid = cj._execute_job_prompt("日报", "生成日报")
    assert sid is not None, "_execute_job_prompt 内部吞异常会返回 None —— 检查桩件是否缺失"
    assert seen.get("session_id") == sid
    assert (root / sid / "artifacts").is_dir()
```

上面代码块已遵守 ruff：`import` 只列用到的（无 `pytest` / `inspect` 这类未用 import）。

Run: `.venv/bin/python -m pytest tests/test_cronjob_artifact_session.py -q`
Expected: 实现到位后 PASS；若把 `agent/tools/cronjob_tools.py:400` 的 `session_id=session_id` 删掉，该用例必须变红（先验一次这个反向断言，确认测试真的在守东西）。

- [ ] **Step 8: 跑测试确认通过并 Commit**

Run: `.venv/bin/python -m pytest tests/test_session_context.py tests/test_cronjob_artifact_session.py -q`
Expected: PASS

```bash
git add agent/session_context.py agent/core/agent_adapter.py agent/core/message_builder.py agent/tools/cronjob_tools.py tests/test_session_context.py tests/test_cronjob_artifact_session.py
git commit -m "feat: bind tool execution to the current session via ContextVar"
```

---

## Task 3: 相对路径归一到会话产物目录（before-hook）

**Files:**

- Create: `agent/tools/session_artifact_hook.py`
- Modify: `backend/main.py`（lifespan 内安装 hook，紧接 T1 的迁移调用之后）
- Test: `tests/test_session_artifact_hook.py`（新建）

**Interfaces:**

- Consumes: `session_context.current_artifacts_dir()` / `ensure_current_artifacts_dir()`（T2）
- Produces: `session_artifact_hook.PATH_ARGS`、`MUTATING_TOOLS`、`artifact_before_hook(name, args) -> dict`、`install_session_artifact_hooks() -> None`、`is_within(path, root) -> bool`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_session_artifact_hook.py`：

```python
"""路径归一：有会话上下文时相对路径落产物目录；没有时行为不变。"""

import json
import os
from pathlib import Path

import pytest

from agent import session_manager as sm
from agent import session_context as ctx
from agent.tools import session_artifact_hook as sah


@pytest.fixture
def sessions_root(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    root.mkdir()
    monkeypatch.setattr(sm, "SESSIONS_DIR", root)
    monkeypatch.setattr(sm, "INDEX_FILE", root / "index.json")
    yield root
    ctx.set_current_session(None)


@pytest.fixture
def cwd_isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _call(tool, **args):
    return sah.artifact_before_hook(tool, dict(args))


def test_relative_write_path_goes_to_artifacts(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    out = _call("write_file", path="report.html", content="x")
    assert out["path"] == str(sessions_root / sid / "artifacts" / "report.html")


def test_nested_relative_path_carries_subdir(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    out = _call("write_file", path="charts/bar.js", content="x")
    assert out["path"].endswith("artifacts/charts/bar.js")


def test_absolute_and_tilde_paths_untouched(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    assert _call("write_file", path="/tmp/a.html")["path"] == "/tmp/a.html"
    assert _call("write_file", path="~/Desktop/a.html")["path"] == "~/Desktop/a.html"


def test_no_session_context_leaves_path_as_is(cwd_isolated):
    assert _call("write_file", path="a.html")["path"] == "a.html"
    assert _call("ls")["path"] == "."


def test_missing_path_arg_gets_artifacts_dir(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    assert _call("ls")["path"] == str(sessions_root / sid / "artifacts")
    assert _call("terminal", command="pwd")["workdir"] == str(sessions_root / sid / "artifacts")


def test_terminal_relative_workdir_resolves_to_artifacts(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    out = _call("terminal", command="ls", workdir="sub")
    assert out["workdir"] == str(sessions_root / sid / "artifacts" / "sub")


def test_unknown_tool_and_non_string_path_pass_through(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    assert _call("erp_ys_api", path="a.html")["path"] == "a.html"
    assert _call("write_file", path=123)["path"] == 123


def test_hook_never_blocks(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    assert "__block__" not in _call("write_file", path="a.html")


def test_real_write_lands_in_session_artifacts(sessions_root, cwd_isolated):
    """端到端：真调 write_file handler（含 FileMutationQueue 路径）。"""
    from agent.tools.file_tools import _handle_write_file

    sid = sm.create_session()
    ctx.set_current_session(sid)
    args = sah.artifact_before_hook("write_file", {"path": "r.html", "content": "<h1>hi</h1>"})
    res = json.loads(_handle_write_file(args))
    assert res["success"] is True
    assert (sessions_root / sid / "artifacts" / "r.html").read_text(encoding="utf-8") == "<h1>hi</h1>"
    assert list(cwd_isolated.glob("*.html")) == []  # 仓库/cwd 不再被污染


def test_is_within_helper(tmp_path):
    root = tmp_path / "artifacts"
    root.mkdir()
    assert sah.is_within(root / "a" / "b.html", root)
    assert not sah.is_within(tmp_path / "elsewhere.html", root)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_session_artifact_hook.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'agent.tools.session_artifact_hook'`

- [ ] **Step 3: 新建 `agent/tools/session_artifact_hook.py`（本任务只写归一部分）**

```python
"""会话工作目录 —— 把文件/终端工具的相对路径归到本次会话的产物目录。

动机（见 spec §4.2）：写产物的相对路径今天落在后端进程 cwd（即源码仓库
根目录），是 ``/*.html`` 污染 gitignore 的根因；且产物没有会话归属，侧边
栏无从列起。

规则：
* 只改**相对**路径；绝对路径与 ``~`` 开头一律尊重用户/模型意图；
* 无会话上下文（单测、直接调工具、CLI）时完全不改 args —— 行为与改动前
  逐字一致；
* before-hook 只改写 args，**永不**返回 ``__block__``，不参与三层安全模型
  （注册顺序在 ``security_hooks`` 之后，先过安全再归一）。
"""

from __future__ import annotations

import os
from pathlib import Path

from agent.session_context import ensure_current_artifacts_dir
from agent.tools.registry import registry

#: 工具名 → 承载路径的参数名。terminal 用 workdir，其余用 path。
PATH_ARGS: dict[str, str] = {
    "write_file": "path",
    "patch": "path",
    "read_file": "path",
    "ls": "path",
    "glob": "path",
    "search_files": "path",
    "terminal": "workdir",
}

#: 会写盘的工具（after-hook 登记 external.jsonl 时用）
MUTATING_TOOLS: frozenset[str] = frozenset({"write_file", "patch"})

#: 缺省即"当前目录"、需要替换成产物目录的工具
_DEFAULT_IS_CWD: frozenset[str] = frozenset({"ls", "glob", "search_files", "terminal"})


def is_within(path: Path | str, root: Path | str) -> bool:
    """*path* 解析后是否落在 *root* 子树内（含软链接解析后的真实路径）。"""
    try:
        return Path(path).resolve().is_relative_to(Path(root).resolve())
    except (OSError, ValueError):
        return False


def _should_skip(raw: object) -> bool:
    if not isinstance(raw, str):
        return True  # 非字符串 → 交给 handler 报错
    expanded = os.path.expanduser(raw)
    if raw.startswith("~") or os.path.isabs(expanded):
        return True  # 绝对 / 家目录展开：尊重
    return False


def artifact_before_hook(name: str, args: dict) -> dict:
    """registry before-hook：把相对路径改写成会话产物目录下的绝对路径。"""
    key = PATH_ARGS.get(name)
    if key is None:
        return args
    base = ensure_current_artifacts_dir()
    if base is None:
        return args  # 无会话上下文 → 行为不变

    raw = args.get(key)
    if raw is None or (isinstance(raw, str) and raw.strip() in ("", ".")):
        if name in _DEFAULT_IS_CWD:
            new = dict(args)
            new[key] = str(base)
            return new
        return args  # write_file/patch 空 path：让 handler 报错
    if _should_skip(raw):
        return args

    new = dict(args)
    new[key] = str(base / os.path.expanduser(raw))
    return new


_installed = False


def install_session_artifact_hooks() -> None:
    """幂等安装 before-hook（T4 会补上 after-hook）。不读 registry 私有字段。"""
    global _installed
    if _installed:
        return
    registry.add_before_hook(artifact_before_hook)
    _installed = True


__all__ = [
    "PATH_ARGS",
    "MUTATING_TOOLS",
    "artifact_before_hook",
    "install_session_artifact_hooks",
    "is_within",
]
```

- [ ] **Step 4: 在 lifespan 安装 hook**

`backend/main.py` lifespan 内，紧接 T1 的会话迁移调用之后：

```python
    from agent.tools.session_artifact_hook import install_session_artifact_hooks

    install_session_artifact_hooks()
    _lap("artifact_hooks")
```

- [ ] **Step 5: 跑测试确认通过（含 file tools 回归）**

Run: `.venv/bin/python -m pytest tests/test_session_artifact_hook.py tests/test_file_tools.py tests/test_glob_guard.py -q`
Expected: PASS —— 全部既有 `test_file_tools.py` 用例无需修改（无会话上下文 → 走老分支）

- [ ] **Step 6: Commit**

```bash
git add agent/tools/session_artifact_hook.py backend/main.py tests/test_session_artifact_hook.py
git commit -m "feat: resolve relative tool paths against the session artifacts dir"
```

---

## Task 4: 会话外写出登记（after-hook + external.jsonl）

**Files:**

- Modify: `agent/tools/session_artifact_hook.py`（追加 after-hook 与读取函数）
- Modify: `backend/main.py`（安装函数已含 after-hook，无需再改）
- Test: `tests/test_session_artifact_hook.py`（追加）

**Interfaces:**

- Consumes: T3 的 `MUTATING_TOOLS` / `is_within`、`session_context` / `session_manager.session_dir`
- Produces: `session_artifact_hook.EXTERNAL_FILENAME = "external.jsonl"`、`artifact_after_hook(name, args, result) -> str`、`read_external_entries(sid) -> list[dict]`、`record_external_write(abs_path, tool) -> None`

- [ ] **Step 1: 写失败测试**

`tests/test_session_artifact_hook.py` 末尾追加（顶部 import 补 `datetime` 不需要）：

```python
def _ok_result(path: str) -> str:
    return json.dumps({"success": True, "data": f"Written 3 chars to {path}"})


def test_outside_write_is_registered(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    outside = str(sessions_root.parent / "Desktop" / "U8_2026-09-01_销售订单.html")
    sah.artifact_after_hook("write_file", {"path": outside}, _ok_result(outside))
    entries = sah.read_external_entries(sid)
    assert len(entries) == 1
    assert entries[0]["path"] == outside
    assert entries[0]["tool"] == "write_file"
    assert "ts" in entries[0]


def test_inside_write_is_not_registered(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    inside = str(sm.artifacts_dir(sid) / "r.html")
    sah.artifact_after_hook("write_file", {"path": inside}, _ok_result(inside))
    assert sah.read_external_entries(sid) == []


def test_failed_write_is_not_registered(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    outside = str(sessions_root.parent / "x.html")
    res = json.dumps({"success": False, "error": "boom"})
    sah.artifact_after_hook("write_file", {"path": outside}, res)
    assert sah.read_external_entries(sid) == []


def test_read_tools_never_register(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    sah.artifact_after_hook("read_file", {"path": "/etc/hosts"}, json.dumps({"success": True}))
    assert sah.read_external_entries(sid) == []


def test_no_session_registers_nothing(sessions_root, tmp_path):
    ctx.set_current_session(None)
    sah.artifact_after_hook("write_file", {"path": str(tmp_path / "x.html")}, _ok_result("x"))
    assert list(sessions_root.glob("*/external.jsonl")) == []


def test_malformed_jsonl_lines_are_skipped(sessions_root):
    sid = sm.create_session()
    f = sm.session_dir(sid) / "external.jsonl"
    f.write_text('{"path": "/a.html"}\nNOT JSON\n\n{"path": "/b.html", "tool": "patch"}\n', encoding="utf-8")
    entries = sah.read_external_entries(sid)
    assert [e["path"] for e in entries] == ["/a.html", "/b.html"]


def test_duplicates_deduped_latest_wins(sessions_root):
    sid = sm.create_session()
    ctx.set_current_session(sid)
    p = str(sessions_root.parent / "same.html")
    sah.artifact_after_hook("write_file", {"path": p}, _ok_result(p))
    sah.artifact_after_hook("patch", {"path": p}, _ok_result(p))
    entries = sah.read_external_entries(sid)
    assert len(entries) == 1 and entries[0]["tool"] == "patch"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_session_artifact_hook.py -q -k "registered or jsonl or dedup or registers"`
Expected: FAIL —— `AttributeError: module ... has no attribute 'artifact_after_hook'`

- [ ] **Step 3: 在 `session_artifact_hook.py` 追加实现**

模块顶部 import 补：

```python
import json
import logging
from datetime import datetime

from agent.session_context import get_current_session
```

在 `install_session_artifact_hooks` 之前插入：

```python
logger = logging.getLogger(__name__)

EXTERNAL_FILENAME = "external.jsonl"


def record_external_write(session_id: str, abs_path: str, tool: str) -> None:
    """向 ``<sid>/external.jsonl`` 追加一行。

    单行 ``open("a")`` 写（POSIX 短写原子），不引入锁 —— 读侧只做展示。
    """
    from agent import session_manager

    target = session_manager.session_dir(session_id) / EXTERNAL_FILENAME
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {"path": abs_path, "tool": tool, "ts": datetime.now().isoformat()},
            ensure_ascii=False,
        )
        with open(target, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:  # pragma: no cover - 磁盘异常只记日志
        logger.warning("external.jsonl 写入失败 %s: %s", target, e)


def read_external_entries(session_id: str) -> list[dict]:
    """读 ``external.jsonl``，同 path 去重取最后一条，坏行跳过。"""
    from agent import session_manager

    f = session_manager.session_dir(session_id) / EXTERNAL_FILENAME
    if not f.is_file():
        return []
    by_path: dict[str, dict] = {}
    try:
        raw_lines = f.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        path = obj.get("path")
        if isinstance(path, str) and path:
            by_path[path] = {
                "path": path,
                "tool": str(obj.get("tool", "")),
                "ts": str(obj.get("ts", "")),
            }
    return sorted(by_path.values(), key=lambda e: e["ts"], reverse=True)


def artifact_after_hook(name: str, args: dict, result: str) -> str:
    """registry after-hook：写出落在会话目录外时登记一笔（只观察，不改 result）。"""
    if name not in MUTATING_TOOLS:
        return result
    sid = get_current_session()
    if not sid:
        return result
    try:
        payload = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return result
    if not isinstance(payload, dict) or not payload.get("success"):
        return result

    raw = args.get(PATH_ARGS[name])
    if not isinstance(raw, str) or not raw:
        return result
    base = ensure_current_artifacts_dir()
    if base is None:
        return result
    expanded = os.path.expanduser(raw)
    if is_within(expanded, base):
        return result

    record_external_write(sid, str(Path(expanded).resolve()), name)
    return result
```

`install_session_artifact_hooks()` 里改成 before + after 都装：

```python
def install_session_artifact_hooks() -> None:
    """幂等安装 before + after hook。"""
    global _installed
    if _installed:
        return
    registry.add_before_hook(artifact_before_hook)
    registry.add_after_hook(artifact_after_hook)
    _installed = True
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_session_artifact_hook.py -q`
Expected: PASS（含 T3 全部用例）

- [ ] **Step 5: 全量回归 + Commit**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 全绿（after-hook 链多一环，`test_approval.py` / `test_execution_mode_audit.py` 若因 hook 计数断言失败，按实际注册数修正断言值，不要降低断言强度）

```bash
git add agent/tools/session_artifact_hook.py tests/test_session_artifact_hook.py
git commit -m "feat: register out-of-session writes in per-session external.jsonl"
```

---

## Task 5: 产物列表端点 + Pydantic 模型

**Files:**

- Create: `backend/schemas/session_artifact.py`
- Create: `backend/api/session_artifacts.py`
- Modify: `backend/main.py`（import + `app.include_router(...)`，紧跟 `sessions_router` 之后）
- Test: `tests/test_session_artifacts_api.py`（新建）

**Interfaces:**

- Consumes: `session_manager.session_dir/artifacts_dir/is_valid_session_id`（T1）、`session_artifact_hook.read_external_entries`（T4）
- Produces: `session_artifacts.router`、`session_artifacts._resolve_in_artifacts(sid, rel) -> Path | None`（T6 复用）、`session_artifacts._scan_artifacts(sid) -> tuple[list[ArtifactItem], bool]` 与 `_iter_artifact_files(root)`（T6/T7 复用）、`KIND_BY_EXT`、`MAX_LIST_ITEMS = 300`、`MAX_INLINE_BYTES = 5_000_000`、`MAX_ZIP_BYTES = 200_000_000`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_session_artifacts_api.py`：

```python
"""产物 API：列表分类/截断，文件端点的路径穿越防护，zip，reveal。"""

import shutil
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.api.session_artifacts as sa_mod
from agent import search_index
from agent import session_manager as sm


@pytest.fixture
def client(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    root.mkdir()
    monkeypatch.setattr(sm, "SESSIONS_DIR", root)
    monkeypatch.setattr(sm, "INDEX_FILE", root / "index.json")
    monkeypatch.setattr(search_index, "DB_PATH", tmp_path / "search.db")

    app = FastAPI()
    app.include_router(sa_mod.router)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sid_with_artifacts(client):
    sid = sm.create_session("报表")
    art = sm.ensure_artifacts_dir(sid)
    (art / "report.html").write_text("<h1>r</h1>", encoding="utf-8")
    (art / "notes.md").write_text("# t", encoding="utf-8")
    (art / "chart.js").write_text("console.log(1)", encoding="utf-8")
    (art / "pic.png").write_bytes(b"\x89PNG\r\n")
    sub = art / "sub"
    sub.mkdir()
    (sub / "deep.pdf").write_bytes(b"%PDF-1.4")
    (sub / "blob.bin").write_bytes(b"\x00\x01")
    return sid


def test_list_artifacts_classifies_kinds(client, sid_with_artifacts):
    sid = sid_with_artifacts
    r = client.get(f"/api/sessions/{sid}/artifacts")
    assert r.status_code == 200
    body = r.json()
    kinds = {i["name"]: i["kind"] for i in body["items"]}
    assert kinds["report.html"] == "html"
    assert kinds["notes.md"] == "md"
    assert kinds["pic.png"] == "image"
    assert kinds["deep.pdf"] == "pdf"
    assert kinds["chart.js"] == "text"
    assert kinds["blob.bin"] == "other"
    assert body["truncated"] is False
    assert body["count"] == len(body["items"]) == 6
    # rel 是相对 artifacts/ 的 POSIX 路径
    assert "sub/deep.pdf" in {i["rel"] for i in body["items"]}


def test_list_artifacts_unknown_sid_404(client):
    assert client.get("/api/sessions/deadbeef/artifacts").status_code == 404


def test_list_artifacts_truncation_flag(client, sid_with_artifacts):
    sid = sid_with_artifacts
    art = sm.ensure_artifacts_dir(sid)
    for i in range(300):
        (art / f"f{i:03d}.txt").write_text("x", encoding="utf-8")
    body = client.get(f"/api/sessions/{sid}/artifacts").json()
    assert body["truncated"] is True
    assert len(body["items"]) == sa_mod.MAX_LIST_ITEMS


def test_list_includes_external_with_exists(client, sid_with_artifacts, tmp_path):
    from agent.tools import session_artifact_hook as sah

    sid = sid_with_artifacts
    gone = str(tmp_path / "gone.html")
    here = str(tmp_path / "here.html")
    Path(here).write_text("x", encoding="utf-8")
    sah.record_external_write(sid, here, "write_file")
    sah.record_external_write(sid, gone, "write_file")
    body = client.get(f"/api/sessions/{sid}/artifacts").json()
    by_path = {e["abs_path"]: e for e in body["external"]}
    assert by_path[here]["exists"] is True
    assert by_path[gone]["exists"] is False


def test_empty_session_dir_gets_recreated(client, sid_with_artifacts):
    sid = sid_with_artifacts
    shutil.rmtree(sm.artifacts_dir(sid))
    assert client.get(f"/api/sessions/{sid}/artifacts").status_code == 200
    assert sm.artifacts_dir(sid).is_dir()


def test_illegal_sid_in_url_is_404(client):
    assert client.get("/api/sessions/..%2F..%2Fetc/artifacts").status_code == 404
```

上面已把 `shutil` / `Path` 放在顶部 import；T7 会再往里补 `zipfile` 与 `BytesIO`。

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_session_artifacts_api.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'backend.api.session_artifacts'`

- [ ] **Step 3: 新建 `backend/schemas/session_artifact.py`**

```python
from pydantic import BaseModel


class ArtifactItem(BaseModel):
    name: str
    rel: str
    size: int
    mtime: str
    kind: str


class ExternalArtifact(BaseModel):
    abs_path: str
    tool: str
    ts: str = ""
    exists: bool


class ArtifactListResponse(BaseModel):
    items: list[ArtifactItem]
    external: list[ExternalArtifact]
    count: int
    truncated: bool
    root: str


class RevealRequest(BaseModel):
    rel: str | None = None
    abs_path: str | None = None
```

- [ ] **Step 4: 新建 `backend/api/session_artifacts.py`（本任务只做列表 + 共用校验）**

> import 只先列本任务用到的（ruff 选 `F`+`I`，多余 import 会直接挂）。T6 补 `mimetypes` / `Query` / `FileResponse`，T7 补 `subprocess` / `sys` / `zipfile` / `BytesIO` / `Response` / `RevealRequest`，两处都按标准库分组顺序插入。

```python
"""会话产物只读 API —— 列表 / 文件 / zip / 在 Finder 显示。

安全模型（spec §4.5）：不用 StaticFiles 挂载（那会把含 ERP 数据的
``session.json`` 暴露给本机任意页面），改为显式路由 + 单一校验入口
``_resolve_in_artifacts``，作用域严格限定在 ``<sessions>/<sid>/artifacts/``。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from agent import session_manager
from agent.tools.session_artifact_hook import read_external_entries
from backend.schemas.session_artifact import (
    ArtifactItem,
    ArtifactListResponse,
    ExternalArtifact,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["session-artifacts"])

MAX_LIST_ITEMS = 300
MAX_SCAN_DEPTH = 6
MAX_INLINE_BYTES = 5_000_000
MAX_ZIP_BYTES = 200_000_000

#: 永不可通过文件端点读出的名字（双保险，它们本就不在 artifacts/ 下）
_DENY_NAMES = frozenset({"session.json", "external.jsonl"})

KIND_BY_EXT: dict[str, str] = {
    ".html": "html",
    ".htm": "html",
    ".md": "md",
    ".markdown": "md",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
    ".bmp": "image",
    ".svg": "image",
    ".pdf": "pdf",
    ".txt": "text",
    ".log": "text",
    ".json": "text",
    ".csv": "text",
    ".js": "text",
    ".ts": "text",
    ".py": "text",
    ".css": "text",
    ".xml": "text",
    ".yml": "text",
    ".yaml": "text",
    ".sql": "text",
}


def _kind_of(name: str) -> str:
    return KIND_BY_EXT.get(Path(name).suffix.lower(), "other")


def _safe_sid(sid: str) -> str:
    if not session_manager.is_valid_session_id(sid):
        raise HTTPException(status_code=404, detail="session not found")
    return sid


def _require_session(sid: str) -> str:
    _safe_sid(sid)
    if not session_manager.session_dir(sid).is_dir():
        raise HTTPException(status_code=404, detail="session not found")
    return sid


def _norm_rel(rel: str) -> list[str]:
    """反斜杠归一 + 分段，绝不接受 `..`。返回空列表表示非法。"""
    unified = (rel or "").replace("\\", "/")
    if Path(unified).is_absolute() or unified.startswith("/"):
        return []
    parts = [p for p in unified.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return []
    if parts[-1].lower() in _DENY_NAMES:
        return []
    return parts


def _resolve_in_artifacts(sid: str, rel: str) -> Path | None:
    """把 ``rel`` 解析成 ``<sid>/artifacts/`` 内的真实文件；非法/越界返回 None。"""
    if not session_manager.is_valid_session_id(sid):
        return None
    parts = _norm_rel(rel)
    if not parts:
        return None
    root = session_manager.artifacts_dir(sid)
    candidate = root.joinpath(*parts)
    try:
        resolved = candidate.resolve()
    except (OSError, ValueError):
        return None
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None  # 软链接逃逸
    if not resolved.is_file():
        return None
    return resolved


def _iter_artifact_files(root: Path):
    """深度受限的产物文件遍历（跳过软链接与不可读目录）。"""
    root_r = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        base = Path(dirpath)
        try:
            depth = len(base.resolve().relative_to(root_r).parts)
        except ValueError:
            dirnames[:] = []
            continue
        if depth >= MAX_SCAN_DEPTH:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if not (base / d).is_symlink()]
        for fn in filenames:
            p = base / fn
            if p.is_symlink():
                continue
            yield p


def _scan_artifacts(sid: str) -> tuple[list[ArtifactItem], bool]:
    root = session_manager.ensure_artifacts_dir(sid)
    items: list[ArtifactItem] = []
    truncated = False
    for p in _iter_artifact_files(root):
        try:
            st = p.stat()
        except OSError:
            continue
        items.append(
            ArtifactItem(
                name=p.name,
                rel=p.relative_to(root).as_posix(),
                size=st.st_size,
                mtime=datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                kind=_kind_of(p.name),
            )
        )
        if len(items) >= MAX_LIST_ITEMS:
            truncated = True
            break
    items.sort(key=lambda i: i.mtime, reverse=True)
    return items, truncated


@router.get("/api/sessions/{sid}/artifacts", response_model=ArtifactListResponse)
def list_artifacts(sid: str) -> ArtifactListResponse:
    _require_session(sid)
    items, truncated = _scan_artifacts(sid)
    external = [
        ExternalArtifact(
            abs_path=e["path"],
            tool=e["tool"],
            ts=e["ts"],
            exists=os.path.isfile(e["path"]),
        )
        for e in read_external_entries(sid)
    ]
    return ArtifactListResponse(
        items=items,
        external=external,
        count=len(items),
        truncated=truncated,
        root=f"/api/session-files/{sid}/",
    )
```

- [ ] **Step 5: 挂到 `backend/main.py`**

```python
from backend.api.session_artifacts import router as session_artifacts_router

app.include_router(session_artifacts_router)
```

放在 `app.include_router(sessions_router)` 之后。

- [ ] **Step 6: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_session_artifacts_api.py -q`
Expected: PASS（6 passed）

> `test_illegal_sid_in_url_is_404`：Starlette 会解码 `%2F`，`..%2F..%2Fetc` 落到 `{sid}` 后被 `is_valid_session_id` 拒 → 404。若该用例因路由匹配返回 405，把它改成 `client.get("/api/sessions/no-such-sess-id-longer-than-64-chars-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/artifacts")` 并在测试内加注释说明校验意图。

- [ ] **Step 7: Commit**

```bash
git add backend/schemas/session_artifact.py backend/api/session_artifacts.py backend/main.py tests/test_session_artifacts_api.py
git commit -m "feat: add session artifacts listing endpoint"
```

---

## Task 6: 文件端点（内容出口 + CSP + 下载）

**Files:**

- Modify: `backend/api/session_artifacts.py`（追加 `get_artifact_file`）
- Modify: `tests/test_session_artifacts_api.py`（追加攻击集与响应头断言）

**Interfaces:**

- Consumes: T5 的 `_resolve_in_artifacts`、`MAX_INLINE_BYTES`
- Produces: `GET /api/session-files/{sid}/{rel:path}`（T7 的 zip/reveal 与前端 iframe/下载都依赖它）

- [ ] **Step 1: 写失败测试**

`tests/test_session_artifacts_api.py` 追加（文件顶部已 `import json`，此处新用例不依赖软链接权限之外的夹具；软链接用例需要 `import os`）：

```python
def _get_file(client, sid, rel, **params):
    return client.get(f"/api/session-files/{sid}/{rel}", params=params)


def test_file_endpoint_serves_html_with_csp(client, sid_with_artifacts):
    sid = sid_with_artifacts
    r = _get_file(client, sid, "report.html")
    assert r.status_code == 200
    assert "sandbox allow-scripts" in r.headers.get("content-security-policy", "")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert "inline" in r.headers.get("content-disposition", "")


def test_file_endpoint_text_body(client, sid_with_artifacts):
    r = _get_file(client, sid_with_artifacts, "notes.md")
    assert r.status_code == 200
    assert r.text == "# t"


def test_file_endpoint_nested_rel(client, sid_with_artifacts):
    r = _get_file(client, sid_with_artifacts, "sub/deep.pdf")
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")


def test_file_endpoint_download_disposition(client, sid_with_artifacts):
    r = _get_file(client, sid_with_artifacts, "report.html", download=1)
    cd = r.headers.get("content-disposition", "")
    assert cd.startswith("attachment")
    assert "report.html" in cd


ATTACKS = [
    "../session.json",
    "..%2Fsession.json",
    "sub/../../session.json",
    "./../session.json",
    "/etc/hosts",
    "C:\\Windows\\win.ini",
    "Session.json",
    "nope.html",
]


@pytest.mark.parametrize("target", ATTACKS)
def test_path_traversal_is_404(client, sid_with_artifacts, target):
    sid = sid_with_artifacts
    assert _get_file(client, sid, target).status_code == 404


def test_symlink_escape_is_404(client, sid_with_artifacts, tmp_path):
    sid = sid_with_artifacts
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    link = sm.artifacts_dir(sid) / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError:  # pragma: no cover - Windows 无符号链接权限
        pytest.skip("文件系统不支持软链接")
    assert _get_file(client, sid, "link.txt").status_code == 404


def test_empty_rel_is_rejected():
    # 直接测单元：空 rel 不走 HTTP（Starlette 对末尾斜杠会 307，不适合做 404 断言）
    assert sa_mod._resolve_in_artifacts("aaaa1111", "") is None


def test_illegal_sid_is_404(client, sid_with_artifacts):
    # 百分号编码的 .. 才能原样抵达路由参数（字面 /../ 会被 httpx 在客户端归一）
    assert client.get("/api/session-files/%2e%2e%2fdeadbeef/report.html").status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

先确认路由真的没注册（否则"路由不存在的 404"会被误当成"防护已生效"）：

Run: `.venv/bin/python -c "import backend.api.session_artifacts as sa; print(sorted(r.path for r in sa.router.routes))"`
Expected: `['/api/sessions/{sid}/artifacts']`（只有列表路由）

Run: `.venv/bin/python -m pytest tests/test_session_artifacts_api.py -q -k "file_endpoint or traversal or symlink or illegal_sid"`
Expected: `test_file_endpoint_*` 3 个用例 FAIL（404 != 200）；`test_path_traversal_is_404` / `test_symlink_escape_is_404` / `test_illegal_sid_is_404` 此阶段会因"路由不存在"而意外通过 —— 属预期，Step 4 它们才真正检验校验逻辑。

- [ ] **Step 3: 实现文件端点**

先把 import 补成（加 `mimetypes`、`Query`、`FileResponse`）：

```python
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
```

然后追加端点：

```python
@router.get("/api/session-files/{sid}/{rel:path}")
def get_artifact_file(sid: str, rel: str, download: bool = Query(False)):
    """产物内容的唯一出口：iframe 预览与前端 fetch 文本共用。

    同源是这套设计成立的前提 —— 报告里的 ``src="chart.js"`` 顺同一前缀
    命中本端点。
    """
    _safe_sid(sid)
    target = _resolve_in_artifacts(sid, rel)
    if target is None:
        raise HTTPException(status_code=404, detail="artifact not found")

    media_type, _ = mimetypes.guess_type(target.name)
    media_type = media_type or "application/octet-stream"
    quoted = _quote_filename(target.name)
    disposition = "attachment" if download else "inline"
    headers = {
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{quoted}",
        "X-Content-Type-Options": "nosniff",
    }
    if media_type == "text/html":
        # 「在浏览器打开」时产物 JS 必须以独立源运行，否则它能 fetch /api/sessions
        # 拖走全部会话内容（后端无鉴权）。iframe 侧再叠一个 sandbox 属性。
        headers["Content-Security-Policy"] = "sandbox allow-scripts;"
    return FileResponse(path=str(target), media_type=media_type, headers=headers, filename=None)


def _quote_filename(name: str) -> str:
    return quote(name, safe="")
```

> `FileResponse(..., filename=None)` 是有意为之：传 filename 会让 Starlette 自行生成 `Content-Disposition`，覆盖我们要控制的 `inline`/`attachment` 语义。`_quote_filename` 定义须放在 `get_artifact_file` 之前或之后均可（模块级函数在调用时已解析）。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/test_session_artifacts_api.py -q`
Expected: 全部 PASS（含 parametrize 9 个攻击用例）

- [ ] **Step 5: 手工验一次真实报告（可选但推荐）**

```bash
./start.sh --dev   # 后端 8089 + Vite 8088
# 对话里让模型生成一个 ECharts 报告 → 浏览器打开
curl -sI "http://127.0.0.1:8089/api/session-files/<sid>/report.html" | head
```

Expected: 响应头里出现 `content-security-policy: sandbox allow-scripts;`

- [ ] **Step 6: Commit**

```bash
git add backend/api/session_artifacts.py tests/test_session_artifacts_api.py
git commit -m "feat: serve session artifacts through a scoped file endpoint"
```

---

## Task 7: zip 打包 + 在 Finder 显示

**Files:**

- Modify: `backend/api/session_artifacts.py`（追加 2 个端点）
- Modify: `tests/test_session_artifacts_api.py`（追加用例）

**Interfaces:**

- Consumes: T5 的 `_iter_artifact_files`、`_require_session`、`_safe_sid`、`MAX_ZIP_BYTES`；`session_manager.artifacts_dir`
- Produces: `GET /api/sessions/{sid}/artifacts/zip`、`POST /api/sessions/{sid}/artifacts/reveal`

- [ ] **Step 1: 写失败测试**

```python
def test_zip_contains_relative_entries(client, sid_with_artifacts):
    sid = sid_with_artifacts
    r = client.get(f"/api/sessions/{sid}/artifacts/zip")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/zip")
    assert sid in r.headers["content-disposition"]
    zf = zipfile.ZipFile(BytesIO(r.content))
    names = set(zf.namelist())
    assert {"report.html", "notes.md", "sub/deep.pdf"} <= names
    assert zf.read("report.html").decode() == "<h1>r</h1>"


def test_zip_empty_dir_ok(client, sid_with_artifacts):
    sid = sid_with_artifacts
    for p in sm.artifacts_dir(sid).rglob("*"):
        if p.is_file():
            p.unlink()
    assert client.get(f"/api/sessions/{sid}/artifacts/zip").status_code == 200


def test_zip_oversized_returns_413(client, sid_with_artifacts, monkeypatch):
    sid = sid_with_artifacts
    monkeypatch.setattr(sa_mod, "MAX_ZIP_BYTES", 10)
    r = client.get(f"/api/sessions/{sid}/artifacts/zip")
    assert r.status_code == 413


def test_reveal_rejects_unlisted_abs_path(client, sid_with_artifacts, tmp_path):
    sid = sid_with_artifacts
    r = client.post(f"/api/sessions/{sid}/artifacts/reveal", json={"abs_path": "/etc/hosts"})
    assert r.status_code == 403


def test_reveal_accepts_internal_rel(client, sid_with_artifacts, monkeypatch):
    sid = sid_with_artifacts
    seen: list[str] = []
    monkeypatch.setattr(sa_mod, "_reveal_in_file_manager", lambda p: seen.append(str(p)))
    r = client.post(f"/api/sessions/{sid}/artifacts/reveal", json={"rel": "report.html"})
    assert r.status_code == 200
    assert seen and seen[0].endswith("report.html")


def test_reveal_accepts_registered_abs_path(client, sid_with_artifacts, tmp_path, monkeypatch):
    from agent.tools import session_artifact_hook as sah

    sid = sid_with_artifacts
    p = tmp_path / "out.html"
    p.write_text("x", encoding="utf-8")
    sah.record_external_write(sid, str(p), "write_file")
    monkeypatch.setattr(sa_mod, "_reveal_in_file_manager", lambda target: None)
    assert client.post(f"/api/sessions/{sid}/artifacts/reveal", json={"abs_path": str(p)}).status_code == 200
```

本任务的测试文件顶部 import 补两行（标准库组内按字母序）：`import zipfile` 与 `from io import BytesIO`。

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/test_session_artifacts_api.py -q -k "zip or reveal"`
Expected: FAIL —— 405/404（端点不存在）

- [ ] **Step 3: 实现两个端点**

先把 import 补齐（加 `subprocess`/`sys`/`zipfile`/`BytesIO`/`Response`/`RevealRequest`）：

```python
import subprocess
import sys
import zipfile
from io import BytesIO

from fastapi.responses import FileResponse, Response

from backend.schemas.session_artifact import (
    ArtifactItem,
    ArtifactListResponse,
    ExternalArtifact,
    RevealRequest,
)
```

```python
@router.get("/api/sessions/{sid}/artifacts/zip")
def download_artifacts_zip(sid: str) -> Response:
    """把整个 artifacts/ 打包（保留相对目录结构、跳过软链接）。"""
    _require_session(sid)
    root = session_manager.ensure_artifacts_dir(sid)
    files = list(_iter_artifact_files(root))
    total = 0
    for p in files:
        try:
            total += p.stat().st_size
        except OSError:
            continue
    if total > MAX_ZIP_BYTES:
        raise HTTPException(status_code=413, detail="产物总体积超过打包上限")

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            try:
                zf.write(p, arcname=p.relative_to(root).as_posix())
            except OSError:
                logger.warning("zip 跳过不可读产物: %s", p)
    buf.seek(0)
    name = f"session-{sid}-artifacts.zip"
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/api/sessions/{sid}/artifacts/reveal")
def reveal_artifact(sid: str, body: RevealRequest) -> dict:
    """在系统文件管理器里定位产物。入参只能是会话内 rel 或已登记的 abs_path。"""
    _require_session(sid)
    target: Path | None = None
    if body.rel:
        target = _resolve_in_artifacts(sid, body.rel)
        if target is None:
            raise HTTPException(status_code=404, detail="artifact not found")
    elif body.abs_path:
        registered = {e["path"] for e in read_external_entries(sid)}
        candidate = os.path.realpath(os.path.expanduser(body.abs_path))
        if candidate not in {os.path.realpath(p) for p in registered}:
            raise HTTPException(status_code=403, detail="未登记的绝对路径不允许 reveal")
        if not os.path.isfile(candidate):
            raise HTTPException(status_code=404, detail="文件已不存在")
        target = Path(candidate)
    else:
        raise HTTPException(status_code=422, detail="需要 rel 或 abs_path")

    _reveal_in_file_manager(target)
    return {"success": True}


def _reveal_in_file_manager(target: Path) -> None:
    """跨平台在文件管理器中定位（不 wait，失败只记日志）。"""
    if sys.platform == "darwin":
        cmd: list[str] = ["open", "-R", str(target)]
    elif os.name == "nt":  # pragma: no cover - 非 macOS/Linux CI
        cmd = ["explorer", f"/select,{target}"]
    else:  # pragma: no cover
        cmd = ["xdg-open", str(target.parent)]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        logger.warning("reveal 失败 %s: %s", target, e)
```

- [ ] **Step 4: 跑测试确认通过 + 全量回归**

Run: `.venv/bin/python -m pytest tests/test_session_artifacts_api.py -q && .venv/bin/python -m pytest tests/ -q`
Expected: 全绿

- [ ] **Step 5: Commit**

```bash
git add backend/api/session_artifacts.py tests/test_session_artifacts_api.py
git commit -m "feat: add artifact zip export and reveal-in-finder endpoints"
```

---

## Task 8: ERP skill 产物落点文案（3 处）

**Files:**

- Modify: `agent/skills/u8/SKILL.md:136`
- Modify: `agent/skills/nc/SKILL.md:128`
- Modify: `agent/skills/yonsuite/SKILL.md:104`

**Interfaces:**

- Consumes: T2 注入的 `## 会话产物` system prompt 片段
- Produces: 无代码接口（纯文案，与 prompt 指令一致化）

> `AGENTS.md` 里的 ❌ 区指"内置技能不可经 API 删除/编辑"，源码内的文案修订是本仓库正常改动；只改这 3 行，不动其余技能内容。

- [ ] **Step 1: 确认三行现文**

Run: `grep -n "默认保存到桌面" agent/skills/u8/SKILL.md agent/skills/nc/SKILL.md agent/skills/yonsuite/SKILL.md`
Expected: 各命中 1 行（`u8:136`、`nc:128`、`yonsuite:104`）

- [ ] **Step 2: 逐行改写（保留各自前缀风格）**

`agent/skills/u8/SKILL.md:136`：

```markdown
- 默认写入会话产物目录：`U8_YYYY-MM-DD_类型.html`（相对路径即可，工具会自动落到本次会话的 `artifacts/`，侧边栏直接可预览/下载；用户明确要"放到桌面/下载"时才写绝对路径）
```

`agent/skills/nc/SKILL.md:128`：同结构，前缀换 `NC_`。

`agent/skills/yonsuite/SKILL.md:104`：同结构，前缀换 `YS_`，保留原有 `**` 粗体包裹。

- [ ] **Step 3: 确认旧约定已消失、新约定已就位**

Run: `grep -rn "默认保存到桌面" agent/skills/ ; grep -rn "默认写入会话产物目录" agent/skills/`
Expected: 第一条无输出；第二条命中 3 行

- [ ] **Step 4: 确认技能加载不受影响**

Run: `.venv/bin/python -m pytest tests/test_skill_manager.py tests/test_skills_api.py -q`
Expected: PASS（技能文件只是内容变更，激活/解析逻辑不感知）

- [ ] **Step 5: Commit**

```bash
git add agent/skills/u8/SKILL.md agent/skills/nc/SKILL.md agent/skills/yonsuite/SKILL.md
git commit -m "docs: point ERP report skills at the session artifacts dir"
```

---

## Task 9: 前端数据层（apiUrl / onToolActivity / useSessionArtifacts / 类型）

**Files:**

- Modify: `web/src/api/http.ts`（导出 `apiUrl`）
- Modify: `web/src/types/index.ts`（`ArtifactItem` / `ExternalArtifact` / `ArtifactListResponse`）
- Modify: `web/src/hooks/useChat.ts:6-9`（`UseChatOptions` 加 `onToolActivity`）、`:89-100`（`tool_result` 分支）、`:101`（`done` 分支）
- Create: `web/src/hooks/useSessionArtifacts.ts`

**Interfaces:**

- Consumes: `GET /api/sessions/{sid}/artifacts`（T5）
- Produces: `apiUrl(path): string`；`UseChatOptions.onToolActivity?: (name: string) => void`（`done` 帧回调名固定为 `"__turn_end__"`）；`useSessionArtifacts(sid: string | null, version: number): { data, loading, error, refresh }`

- [ ] **Step 1: `http.ts` 导出绝对 URL helper**

在 `export const api = {...}` 之前插入：

```ts
// 产物预览要用绝对 URL：Electron 下页面可能不是后端源，iframe/下载链接必须自洽。
export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}
```

- [ ] **Step 2: `types/index.ts` 追加产物类型**

文件末尾追加（与后端 `backend/schemas/session_artifact.py` 字段逐字对齐）：

```ts
// ── 会话产物 ──────────────────────────────────────────────
export type ArtifactKind = "html" | "md" | "image" | "pdf" | "text" | "other";

export interface ArtifactItem {
  name: string;
  rel: string;
  size: number;
  mtime: string;
  kind: ArtifactKind;
}

export interface ExternalArtifact {
  abs_path: string;
  tool: string;
  ts: string;
  exists: boolean;
}

export interface ArtifactListResponse {
  items: ArtifactItem[];
  external: ExternalArtifact[];
  count: number;
  truncated: boolean;
  root: string;
}
```

- [ ] **Step 3: `useChat.ts` 加 `onToolActivity`**

`interface UseChatOptions` 改为：

```ts
interface UseChatOptions {
  onApprovalRequest?: (payload: { tool_name: string; reason: string }) => void;
  /** 工具执行完成 / 回合结束（name === "__turn_end__"）—— 供产物面板刷新 */
  onToolActivity?: (name: string) => void;
}
```

紧接 `onApprovalRequestRef` 两行之后加同构的 ref 同步：

```ts
  const onToolActivityRef = useRef(options?.onToolActivity);
  useEffect(() => {
    onToolActivityRef.current = options?.onToolActivity;
  }, [options?.onToolActivity]);
```

`case "tool_result":` 分支末尾（`});` 之后、`break;` 之前）加一行：

```ts
            onToolActivityRef.current?.(msg.name);
```

`case "done":` 分支的 `ws.close(); wsRef.current = null;` 之前加一行：

```ts
            onToolActivityRef.current?.("__turn_end__");
```

- [ ] **Step 4: 新建 `web/src/hooks/useSessionArtifacts.ts`**

```ts
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/http";
import type { ArtifactListResponse } from "../types";

const DEBOUNCE_MS = 300;

/** 会话产物列表。sid 变化立即拉；version 变化防抖重拉。 */
export function useSessionArtifacts(sid: string | null, version: number) {
  const [data, setData] = useState<ArtifactListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);
  const reqIdRef = useRef(0);

  const load = useCallback(async () => {
    if (!sid) {
      setData(null);
      setError(null);
      return;
    }
    const id = ++reqIdRef.current;
    setLoading(true);
    try {
      const next = await api.get<ArtifactListResponse>(`/sessions/${sid}/artifacts`);
      if (id === reqIdRef.current) {
        setData(next);
        setError(null);
      }
    } catch (e) {
      if (id === reqIdRef.current) {
        // 会话未落库 / 已被删除都走 404 → 空态而非报错
        const msg = e instanceof Error ? e.message : String(e);
        setError(/404|not found/i.test(msg) ? null : msg);
        if (/404|not found/i.test(msg)) setData(null);
      }
    } finally {
      if (id === reqIdRef.current) setLoading(false);
    }
  }, [sid]);

  useEffect(() => {
    void load();
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    };
  }, [load]);

  useEffect(() => {
    if (version === 0) return;
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => void load(), DEBOUNCE_MS);
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    };
  }, [version, load]);

  const refresh = useCallback(() => void load(), [load]);
  return { data, loading, error, refresh };
}
```

- [ ] **Step 5: 类型检查通过**

Run: `cd web && npx tsc -b`
Expected: 无输出（0 error）。若报 `useEffect` 返回值不一致，检查两处 cleanup 是否都是 `void` 或都 `return`。

- [ ] **Step 6: Commit**

```bash
git add web/src/api/http.ts web/src/types/index.ts web/src/hooks/useChat.ts web/src/hooks/useSessionArtifacts.ts
git commit -m "feat: add frontend data layer for session artifacts"
```

---

## Task 10: ArtifactsPanel 组件 + 布局接入

**Files:**

- Create: `web/src/components/ArtifactsPanel.tsx`
- Modify: `web/src/components/Layout.tsx`（全文 57 行 → 第三列 + 顶栏开关 + `⌘B` + Outlet context）
- Modify: `web/src/pages/ChatPage.tsx`（取 outlet context、`useChat` 传 `onToolActivity`）
- Modify: `web/src/styles/global.css`（末尾追加 `.artifacts-*` 样式段）

**Interfaces:**

- Consumes: T9 的 `useSessionArtifacts` / `apiUrl` / `ArtifactItem` / `ArtifactListResponse`；T5–T7 的四个端点；`MessageContent.tsx` 的具名导出 `Markdown`（`export const Markdown = memo(function Markdown({ text }: { text: string })`）、`CodeBlock.tsx` 的默认导出 `CodeBlock({ children }: { children?: React.ReactNode })`
- Produces: `Layout` 向子路由暴露 `{ bumpArtifacts: () => void }`（类型 `LayoutOutlet`）；`artifactFileUrl(sid, rel)` / `artifactDownloadUrl(sid, rel)`

已核实的可复用资源（不要新造）：CSS token `--border` `--bg-card` `--text-3` `--primary` `--radius-sm` `--danger`；按钮类 `.btn-secondary`；提示文本类 `.text-hint`。

- [ ] **Step 1: 新建 `web/src/components/ArtifactsPanel.tsx`**

```tsx
import { useEffect, useMemo, useState } from "react";
import {
    IconExternalLink,
    IconFile,
    IconFileText,
    IconFolderOpen,
    IconImage,
    IconPackage,
    IconRefresh,
    IconSidebar,
    IconX,
} from "@tabler/icons-react";
import { api, apiUrl } from "../api/http";
import type { ArtifactItem, ArtifactListResponse } from "../types";
import { Markdown } from "./MessageContent";
import CodeBlock from "./CodeBlock";

const MAX_INLINE_BYTES = 5_000_000;

/** 产物内容 URL —— 与后端 /api/session-files/{sid}/{rel} 一一对应。 */
export function artifactFileUrl(sid: string, rel: string): string {
    const enc = rel.split("/").map(encodeURIComponent).join("/");
    return apiUrl(`/session-files/${sid}/${enc}`);
}

export function artifactDownloadUrl(sid: string, rel: string): string {
    return `${artifactFileUrl(sid, rel)}?download=1`;
}

function KindIcon({ kind }: { kind: ArtifactItem["kind"] }) {
    if (kind === "image") return <IconImage size={14} />;
    if (kind === "md" || kind === "text") return <IconFileText size={14} />;
    return <IconFile size={14} />;
}

function fmtSize(n: number): string {
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function fmtTime(iso: string): string {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? "" : d.toLocaleString("zh-CN", { hour12: false });
}

/** 预览不可用时退化的卡片 —— "文件名 + 在浏览器打开 + 下载"。 */
function FallbackCard({ sid, sel, reason }: { sid: string; sel: ArtifactItem; reason: string }) {
    return (
        <div className="artifacts-fallback">
            <IconFile size={28} />
            <div className="artifacts-fallback-name">{sel.name}</div>
            <div className="text-hint">{reason}</div>
            <a className="btn-secondary" href={artifactFileUrl(sid, sel.rel)} target="_blank" rel="noreferrer">在浏览器打开</a>
            <a className="btn-secondary" href={artifactDownloadUrl(sid, sel.rel)}>下载</a>
        </div>
    );
}

interface Props {
    sid: string | null;
    data: ArtifactListResponse | null;
    loading: boolean;
    error: string | null;
    width: number;
    refresh: () => void;
    onCollapse: () => void;
}

type PreviewState = "idle" | "loading" | "ready" | "missing";

export default function ArtifactsPanel({ sid, data, loading, error, width, refresh, onCollapse }: Props) {
    const [sel, setSel] = useState<ArtifactItem | null>(null);
    const [text, setText] = useState<string | null>(null);
    const [tooBig, setTooBig] = useState(false);
    const [state, setState] = useState<PreviewState>("idle");

    const items = useMemo(() => data?.items ?? [], [data]);
    const external = useMemo(() => data?.external ?? [], [data]);

    // 切会话：清掉选中，避免预览串会话
    useEffect(() => {
        setSel(null);
        setText(null);
    }, [sid]);

    // 选中的文件被外部删除 → 退回列表态
    useEffect(() => {
        if (sel && !items.some((i) => i.rel === sel.rel)) setSel(null);
    }, [items, sel]);

    const isTextKind = sel?.kind === "md" || sel?.kind === "text";
    const isFrameKind = sel?.kind === "html" || sel?.kind === "pdf" || sel?.kind === "image";

    // 文本类：取内容（>5MB 不取）
    useEffect(() => {
        setText(null);
        setTooBig(false);
        if (!sel || !sid || !isTextKind) {
            setState("idle");
            return;
        }
        if (sel.size > MAX_INLINE_BYTES) {
            setTooBig(true);
            setState("ready");
            return;
        }
        setState("loading");
        fetch(artifactFileUrl(sid, sel.rel))
            .then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
            .then((t) => {
                setText(t);
                setState("ready");
            })
            .catch(() => setState("missing"));
    }, [sel, sid, isTextKind]);

    // iframe/img 类：HEAD 探测可用性（探测失败 → 退化卡片）。iframe 内部渲染失败无法探测，靠「在浏览器打开」兜底。
    useEffect(() => {
        if (!sel || !sid || !isFrameKind) {
            setState("idle");
            return;
        }
        setState("loading");
        fetch(artifactFileUrl(sid, sel.rel), { method: "HEAD" })
            .then((r) => setState(r.ok ? "ready" : "missing"))
            .catch(() => setState("missing"));
    }, [sel, sid, isFrameKind]);

    const revealRel = (rel: string) => {
        if (!sid) return;
        void api.post(`/sessions/${sid}/artifacts/reveal`, { rel }).catch(() => undefined);
    };
    const revealAbs = (abs_path: string) => {
        if (!sid) return;
        void api.post(`/sessions/${sid}/artifacts/reveal`, { abs_path }).catch(() => undefined);
    };

    return (
        <aside className="artifacts-panel" style={{ width }}>
            <div className="artifacts-head">
                <IconPackage size={15} />
                <span className="artifacts-title">会话产物</span>
                <span className="text-hint">{data?.count ?? 0}</span>
                <span className="artifacts-head-spacer" />
                <button type="button" className="artifacts-icon-btn" title="刷新" onClick={refresh}>
                    <IconRefresh size={14} className={loading ? "spin" : undefined} />
                </button>
                <button type="button" className="artifacts-icon-btn" title="收起 (⌘B)" onClick={onCollapse}>
                    <IconSidebar size={14} />
                </button>
            </div>

            {error && (
                <div className="artifacts-error">
                    产物读取失败：{error}
                    <button type="button" className="artifacts-link-btn" onClick={refresh}>重试</button>
                </div>
            )}

            <div className="artifacts-list">
                {items.length === 0 && !loading && sid && (
                    <div className="artifacts-empty">开始对话后，这次会话的产物会出现在这里。</div>
                )}
                {!sid && (
                    <div className="artifacts-empty">还没有会话，发出一条消息后产物会归集到这里。</div>
                )}
                {items.map((it) => (
                    <div
                        key={it.rel}
                        className={`artifacts-row${sel?.rel === it.rel ? " active" : ""}`}
                        onClick={() => setSel(it)}
                        title={`${it.rel} · ${fmtSize(it.size)} · ${fmtTime(it.mtime)}`}
                    >
                        <KindIcon kind={it.kind} />
                        <span className="artifacts-row-name">{it.name}</span>
                        <span className="artifacts-row-meta">{fmtSize(it.size)}</span>
                        <span className="artifacts-row-actions">
                            <a
                                className="artifacts-icon-btn"
                                href={sid ? artifactFileUrl(sid, it.rel) : undefined}
                                target="_blank"
                                rel="noreferrer"
                                title="在浏览器打开"
                                onClick={(e) => e.stopPropagation()}
                            >
                                <IconExternalLink size={14} />
                            </a>
                            <a
                                className="artifacts-icon-btn"
                                href={sid ? artifactDownloadUrl(sid, it.rel) : undefined}
                                title="下载"
                                onClick={(e) => e.stopPropagation()}
                            >
                                <IconPackage size={14} />
                            </a>
                            <button
                                type="button"
                                className="artifacts-icon-btn"
                                title="在 Finder 显示"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    revealRel(it.rel);
                                }}
                            >
                                <IconFolderOpen size={14} />
                            </button>
                        </span>
                    </div>
                ))}
                {data?.truncated && (
                    <div className="text-hint artifacts-hint">产物较多，仅显示前 {items.length} 项，其余请到 Finder 查看。</div>
                )}
            </div>

            {external.length > 0 && (
                <details className="artifacts-external">
                    <summary>会话外文件 · {external.length}</summary>
                    {external.map((e) => (
                        <div key={e.abs_path} className={`artifacts-row${e.exists ? "" : " stale"}`} title={e.abs_path}>
                            <IconFile size={14} />
                            <span className="artifacts-row-name">{e.abs_path.split(/[\\/]/).pop()}</span>
                            <span className="artifacts-row-meta">{e.exists ? e.tool : "已失效"}</span>
                            <span className="artifacts-row-actions">
                                <button
                                    type="button"
                                    className="artifacts-icon-btn"
                                    title="在 Finder 显示"
                                    disabled={!e.exists}
                                    onClick={() => revealAbs(e.abs_path)}
                                >
                                    <IconFolderOpen size={14} />
                                </button>
                                <button
                                    type="button"
                                    className="artifacts-icon-btn"
                                    title="复制路径"
                                    onClick={() => void navigator.clipboard.writeText(e.abs_path)}
                                >
                                    <IconFileText size={14} />
                                </button>
                            </span>
                        </div>
                    ))}
                </details>
            )}

            {sel && sid && (
                <div className="artifacts-preview">
                    <div className="artifacts-preview-head">
                        <span className="artifacts-row-name">{sel.name}</span>
                        <span className="text-hint">{fmtSize(sel.size)}</span>
                        <a className="artifacts-link-btn" href={artifactFileUrl(sid, sel.rel)} target="_blank" rel="noreferrer">
                            在浏览器打开
                        </a>
                        <button type="button" className="artifacts-icon-btn" title="关闭预览" onClick={() => setSel(null)}>
                            <IconX size={14} />
                        </button>
                    </div>
                    <div className="artifacts-preview-body">
                        {state === "loading" ? (
                            <div className="artifacts-empty">加载中…</div>
                        ) : state === "ready" && (sel.kind === "html" || sel.kind === "pdf") ? (
                            <iframe className="artifacts-frame" sandbox="allow-scripts" src={artifactFileUrl(sid, sel.rel)} title={sel.name} />
                        ) : state === "ready" && sel.kind === "image" ? (
                            <img className="artifacts-img" src={artifactFileUrl(sid, sel.rel)} alt={sel.name} />
                        ) : state === "ready" && sel.kind === "md" && text != null ? (
                            <div className="artifacts-md"><Markdown text={text} /></div>
                        ) : state === "ready" && sel.kind === "text" && text != null ? (
                            <CodeBlock><code>{text}</code></CodeBlock>
                        ) : (
                            <FallbackCard
                                sid={sid}
                                sel={sel}
                                reason={
                                    state === "missing"
                                        ? "文件已不可读或已被删除。"
                                        : tooBig
                                          ? "文件较大（>5MB），不提供内嵌预览。"
                                          : "该类型不支持内嵌预览。"
                                }
                            />
                        )}
                    </div>
                </div>
            )}

            <div className="artifacts-foot">
                {sid ? (
                    <a className="artifacts-link-btn" href={apiUrl(`/sessions/${sid}/artifacts/zip`)}>打包下载全部产物 (zip)</a>
                ) : (
                    <span className="text-hint">尚无会话</span>
                )}
            </div>
        </aside>
    );
}
```

> 预览是**尽力而为**：`state === "missing"` 覆盖"文件被外部删除/读不到"，`idle` 覆盖 other 类不支持内嵌，两者都退化成卡片（大字文件名 + 在浏览器打开 + 下载）。iframe **内部**渲染失败（如 CDN 不可达导致图表空白）无法从父页面探测，靠「在浏览器打开」兜底 —— 这是 spec §5.4 已接受的边界。

- [ ] **Step 2: `Layout.tsx` 接入第三列与开关**

整个文件替换为（拖拽条是 `.app-layout` 的 flex 子元素、宽度状态由 Layout 持有，面板本身不管拖宽）：

```tsx
import { useCallback, useEffect, useState, type MouseEvent as ReactMouseEvent } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { IconPackage } from "@tabler/icons-react";
import { useAppState } from "../context/AppContext";
import { useSessionArtifacts } from "../hooks/useSessionArtifacts";
import Sidebar from "./Sidebar";
import ArtifactsPanel from "./ArtifactsPanel";

const PAGE_TITLES: Record<string, string> = {
  "/": "对话",
  "/history": "历史对话",
  "/memory": "记忆管理",
  "/skills": "技能管理",
  "/settings/llm": "大模型配置",
  "/settings/erp": "ERP 连接",
  "/settings/agent": "Agent 设置",
  "/cronjobs": "定时任务",
  "/mcp": "MCP 服务器",
};

const PREF_KEY = "zlink.artifactsPanel";
const WIDTH_KEY = `${PREF_KEY}.w`;
const MIN_W = 260;
const MAX_W = 560;
const DEFAULT_W = 320;

export interface LayoutOutlet {
  bumpArtifacts: () => void;
}

export default function Layout() {
  const location = useLocation();
  const { state } = useAppState();
  const title = PAGE_TITLES[location.pathname] || "智链 Agent";
  const isChat = location.pathname === "/";

  const [version, setVersion] = useState(0);
  const bumpArtifacts = useCallback(() => setVersion((v) => v + 1), []);
  const { data, loading, error, refresh } = useSessionArtifacts(isChat ? state.currentSessionId : null, version);

  // pref === null → 用户从未手动开合 → 有产物时自动展开
  const [pref, setPref] = useState<boolean | null>(() => {
    const stored = localStorage.getItem(PREF_KEY);
    return stored === null ? null : stored === "1";
  });
  const count = data?.count ?? 0;
  const open = isChat && (pref ?? count > 0);
  const [width, setWidth] = useState(() => Number(localStorage.getItem(WIDTH_KEY)) || DEFAULT_W);

  const toggle = useCallback(() => {
    const next = !open;
    localStorage.setItem(PREF_KEY, next ? "1" : "0");
    setPref(next);
  }, [open]);

  useEffect(() => {
    if (!isChat) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        toggle();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isChat, toggle]);

  const startResize = useCallback(
    (e: ReactMouseEvent) => {
      e.preventDefault();
      const startX = e.clientX;
      const startW = width;
      const move = (ev: MouseEvent) => {
        const next = Math.min(MAX_W, Math.max(MIN_W, startW + (startX - ev.clientX)));
        setWidth(next);
      };
      const up = () => {
        document.removeEventListener("mousemove", move);
        document.removeEventListener("mouseup", up);
        document.body.style.userSelect = "";
        localStorage.setItem(WIDTH_KEY, String(width));
      };
      document.body.style.userSelect = "none";
      document.addEventListener("mousemove", move);
      document.addEventListener("mouseup", up);
    },
    [width],
  );

  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-area">
        <div className="top-bar">
          <span className="top-bar-title">{title}</span>
          {state.currentSessionId && state.currentSessionTitle && location.pathname === "/" && (
            <span className="text-hint ml-sm">· {state.currentSessionTitle}</span>
          )}
          <span className="top-bar-meta">
            {state.agentRunning ? (
              <span className="flex-row-gap-6">
                <span className="sidebar-footer-dot" style={{ display: "inline-block" }} />
                思考中
              </span>
            ) : state.currentSessionId ? (
              `会话 ${state.currentSessionId.substring(0, 8)}`
            ) : (
              ""
            )}
            {isChat && (
              <button
                type="button"
                className={`top-bar-artifacts-btn${open ? " active" : ""}`}
                onClick={toggle}
                title="会话产物 (⌘B)"
              >
                <IconPackage size={15} />
                {count > 0 && <span className="top-bar-artifacts-badge">{count > 99 ? "99+" : count}</span>}
              </button>
            )}
          </span>
        </div>
        <div className="main-content">
          <Outlet context={{ bumpArtifacts } satisfies LayoutOutlet} />
        </div>
      </div>
      {open && (
        <>
          <div className="artifacts-resizer" onMouseDown={startResize} />
          <ArtifactsPanel
            sid={state.currentSessionId}
            data={data}
            loading={loading}
            error={error}
            width={width}
            refresh={refresh}
            onCollapse={toggle}
          />
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 3: `ChatPage.tsx` 接 outlet context**

import 段加两行（`react-router-dom` 那行已有 `useSearchParams`，合并进去）：

```tsx
import { useSearchParams, useOutletContext } from "react-router-dom";
import type { LayoutOutlet } from "../components/Layout";
```

文件顶层常量段（`export default function ChatPage()` 之前）加：

```tsx
// 会改变会话产物的工具；terminal 里的 shell 也能写文件
const MUTATING_TOOLS = new Set(["write_file", "patch", "terminal", "__turn_end__"]);
```

组件体第一行改为：

```tsx
  const { state, dispatch } = useAppState();
  const { bumpArtifacts } = useOutletContext<LayoutOutlet>();
```

`useChat({ ... })` 的 options 加一个回调（与 `onApprovalRequest` 并列）：

```tsx
    onToolActivity: (name) => {
      if (MUTATING_TOOLS.has(name)) bumpArtifacts();
    },
```

- [ ] **Step 4: `global.css` 追加样式段**

文件末尾追加（只用已存在的 token：`--border` `--bg-card` `--text-3` `--primary` `--radius-sm` `--danger`）：

```css
/* ── 会话产物侧边栏 ─────────────────────────────────── */
.artifacts-panel {
  flex: 0 0 auto;
  height: 100vh;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--border);
  background: var(--bg-card);
  overflow: hidden;
}
.artifacts-head {
  display: flex; align-items: center; gap: 6px;
  height: 40px; flex: 0 0 40px; padding: 0 10px;
  border-bottom: 1px solid var(--border);
}
.artifacts-title { font-size: 13px; font-weight: 600; }
.artifacts-head-spacer { flex: 1 1 auto; }
.artifacts-icon-btn {
  border: none; background: transparent; cursor: pointer; padding: 3px;
  border-radius: var(--radius-sm); color: var(--text-2); display: inline-flex;
  align-items: center; text-decoration: none;
}
.artifacts-icon-btn:hover { background: var(--sidebar-hover); }
.artifacts-icon-btn:disabled { opacity: .35; cursor: default; }
.artifacts-list { flex: 1 1 auto; overflow-y: auto; padding: 6px; }
.artifacts-empty { padding: 24px 12px; font-size: 12px; color: var(--text-3); text-align: center; }
.artifacts-row {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 6px; border-radius: var(--radius-sm); cursor: pointer; font-size: 12px;
}
.artifacts-row:hover { background: var(--bg-hover); }
.artifacts-row.active { background: var(--sidebar-active); }
.artifacts-row.stale { opacity: .5; }
.artifacts-row-name { flex: 1 1 auto; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.artifacts-row-meta { flex: 0 0 auto; color: var(--text-3); font-size: 11px; }
.artifacts-row-actions { display: none; gap: 2px; flex: 0 0 auto; }
.artifacts-row:hover .artifacts-row-actions, .artifacts-row.active .artifacts-row-actions { display: inline-flex; }
.artifacts-hint { padding: 6px; font-size: 11px; }
.artifacts-external { flex: 0 0 auto; border-top: 1px solid var(--border); padding: 4px 8px; }
.artifacts-external summary { font-size: 11px; color: var(--text-3); cursor: pointer; padding: 4px 0; }
.artifacts-preview { flex: 0 0 55%; display: flex; flex-direction: column; border-top: 1px solid var(--border); min-height: 0; }
.artifacts-preview-head {
  display: flex; align-items: center; gap: 8px; padding: 6px 8px; flex: 0 0 auto;
  font-size: 12px; border-bottom: 1px solid var(--border);
}
.artifacts-preview-head .artifacts-row-name { flex: 1 1 auto; }
.artifacts-preview-body { flex: 1 1 auto; overflow: auto; min-height: 0; }
.artifacts-frame { width: 100%; height: 100%; border: 0; background: #fff; }
.artifacts-img { max-width: 100%; height: auto; display: block; margin: 0 auto; }
.artifacts-md { padding: 8px 10px; }
.artifacts-fallback { padding: 28px 16px; text-align: center; display: flex; flex-direction: column; gap: 8px; align-items: center; }
.artifacts-fallback-name { font-size: 14px; font-weight: 600; word-break: break-all; }
.artifacts-foot {
  flex: 0 0 auto; border-top: 1px solid var(--border); padding: 8px;
  display: flex; justify-content: space-between; align-items: center;
}
.artifacts-link-btn {
  font-size: 12px; color: var(--primary); text-decoration: none; cursor: pointer;
  background: none; border: none; padding: 0 0 0 6px;
}
.artifacts-link-btn:hover { text-decoration: underline; }
.artifacts-error { font-size: 12px; color: var(--danger); padding: 6px 8px; border-bottom: 1px solid var(--border); }
.artifacts-resizer { flex: 0 0 5px; height: 100vh; cursor: col-resize; background: transparent; }
.artifacts-resizer:hover { background: var(--primary); opacity: .25; }
.top-bar-artifacts-btn {
  position: relative; margin-left: 10px; border: none; background: transparent;
  cursor: pointer; color: inherit; display: inline-flex; align-items: center;
  padding: 4px 6px; border-radius: var(--radius-sm);
}
.top-bar-artifacts-btn:hover { background: var(--sidebar-hover); }
.top-bar-artifacts-btn.active { background: var(--sidebar-active); }
.top-bar-artifacts-badge {
  position: absolute; top: -2px; right: -4px; min-width: 15px; height: 15px; padding: 0 3px;
  border-radius: 8px; background: var(--primary); color: #fff;
  font-size: 10px; line-height: 15px; text-align: center;
}
.spin { animation: artifacts-spin 1s linear infinite; }
@keyframes artifacts-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .spin { animation: none; } }
```

> `--text-2` 与 `--sidebar-hover` / `--sidebar-active` / `--bg-hover` 已在 `:root` 定义（已核实）。若 `tsc`/样式无报错即可，不必改 token 名。

- [ ] **Step 5: 类型检查 + 构建**
Run: `cd web && npx tsc -b && npm run build`
Expected: tsc 0 error、vite build 成功。若 `Outlet context` 报类型不兼容，确认用了 `satisfies LayoutOutlet`；若 `CodeBlock` 默认导入报错，按 `CodeBlock.tsx:14` 的实际签名（`{ children }`）调整。

- [ ] **Step 6: 后端全量回归**

Run: `.venv/bin/python -m pytest tests/ -q && ruff check . && ruff format --check .`
Expected: 全绿

- [ ] **Step 7: 手工验收（6 条，逐条确认后再提交）**

```bash
./start.sh --dev
```

1. 问一句"生成一个销售订单图表报告" → 回合中出现 `write_file` 后，右侧栏自动展开并列出该 html；
2. 点条目 → 下半区 iframe 里图表可交互（tooltip 有响应）；
3. 点「在浏览器打开」→ 新标签页全屏正常渲染；在该页 DevTools Console 执行 `fetch('/api/sessions').then(r=>r.json()).then(console.log)` 应因 CSP sandbox 独立源而被拒（拿不到会话数据）；
4. 「打包下载全部产物 (zip)」→ 得到 `session-<sid>-artifacts.zip`，解压目录结构与栏内一致；
5. `⌘B` 收起 → 对话区回全宽、顶栏按钮角标数字仍在；再按 `⌘B` 展开；刷新页面后保持上次开合与宽度；
6. 从 `/history` 点进老会话 → 列表变为该会话产物（老会话显示空态文案）。

- [ ] **Step 8: Commit**

```bash
git add web/src/components/ArtifactsPanel.tsx web/src/components/Layout.tsx web/src/pages/ChatPage.tsx web/src/styles/global.css
git commit -m "feat: add collapsible session artifacts sidebar to the chat page"
```

---

## Task 11: 收口 —— 文档、版本号、发布校验

**Files:**

- Modify: `AGENTS.md`（目录结构 §2、会话交接 §12 不动，新增产物约定；§13 补一条）
- Modify: `pyproject.toml`（version → `1.13.0`）、根 `package.json`（同）
- Modify: `CHANGELOG.md`、`README.md`

**Interfaces:**

- Consumes: 前述全部
- Produces: 可发布状态

- [ ] **Step 1: 更新 `AGENTS.md`**

`agent/` 结构段里 `session_manager.py` 那一行改为：

```
├── session_manager.py      # ⚠️ 会话持久化 —— 目录布局 data/sessions/<sid>/{session.json,artifacts/,external.jsonl}
```

并在 `agent/core/` 之后插入两行：

```
├── session_context.py      # ⚠️ 当前会话 ContextVar —— 工具层据此解析产物目录（未设=行为回退进程 cwd）
```

`agent/tools/` 段插入：

```
│   ├── session_artifact_hook.py  # ⚠️ 相对路径归一到 <sid>/artifacts/ + 会话外写出登记 external.jsonl
```

§13 追加一条约定：

```markdown
- **会话产物目录（2026-09-01）**：产物一律写 `~/.zlink-agent/data/sessions/<sid>/artifacts/`。文件/终端工具的相对路径由 `session_artifact_hook` 自动归一（ContextVar 未设时退回进程 cwd）；写到目录外的绝对路径会被登记进同会话的 `external.jsonl` 并在侧边栏「会话外文件」组灰显。禁止再把产物写 `~/Desktop` 或仓库根目录。读端点只允许 `<sid>/artifacts/` 子树（`backend/api/session_artifacts.py`），html 响应带 `Content-Security-Policy: sandbox allow-scripts`。
```

- [ ] **Step 2: 版本号三处同步**

`pyproject.toml` 的 `version = "1.12.0"` → `1.13.0`；根 `package.json` 的 `"version"` 同步。

Run: `grep -n "1\.12\.0" pyproject.toml package.json README.md CHANGELOG.md`
Expected: 除 `CHANGELOG.md` 的历史条目外无残留

- [ ] **Step 3: CHANGELOG + README**

`CHANGELOG.md` 顶部新增 `## [1.13.0] - 2026-09-01`，条目：会话目录化布局（含幂等迁移）、侧边栏产物栏、产物路径归一与 external 登记、4 个产物端点、cronjob 产物归属修复、session_id 路径穿越防护。`README.md` 的功能列表与特性段落同步加"会话产物侧边栏"。

- [ ] **Step 4: 全量验证**

Run: `.venv/bin/python -m pytest tests/ -q && ruff check . && ruff format --check . && cd web && npx tsc -b && npm run build`
Expected: 全绿；`.venv/bin/python -c "from agent.tools.registry import registry, discover_tools; discover_tools(); print(len(registry.get_all_tool_names()), 'tools')"` 仍输出 ~65 tools（本次不增删工具）

- [ ] **Step 5: 真实数据冒烟（迁移不丢会话）**

```bash
.venv/bin/python -c "
from agent import session_manager as sm
print('before:', len(sm.list_sessions()))
print('migrated:', sm.migrate_session_layout())
missing = [e['id'] for e in sm.list_sessions() if not sm.load_session(e['id'])]
print('目录布局:', sorted(p.name for p in sm.SESSIONS_DIR.iterdir())[:3])
print('空会话(可能本来就为空):', missing)
"
```

Expected: `migrated: 33`（或已迁过则为 0）；`list_sessions()` 数量与迁移前一致

- [ ] **Step 6: Commit**

```bash
git add AGENTS.md pyproject.toml package.json CHANGELOG.md README.md
git commit -m "chore: bump version to 1.13.0 and document session artifacts"
```

- [ ] **Step 7: 按 `AGENTS.md` §12 写 `HANDOVER.md`**

包含：分支 `main`、版本 1.13.0、11 个 commit 列表、关键决策（A 档范围 / 会话目录化 / B+B2 / 方案 1「目录为真相」/ 不用 StaticFiles 的原因）、遗留（`sidebar_open` 工具、"本轮文件"分组、skill 相对路径命令改绝对、MCP 工具写出文件不归一）、新会话入口（`Read docs/superpowers/specs/2026-09-01-session-artifacts-sidebar-design.md`）。

---

## 附：与 spec 的差异（已同步进 spec，无需执行时再改）

写计划时核出的 4 处偏差，已直接回写 `docs/superpowers/specs/2026-09-01-session-artifacts-sidebar-design.md`，执行时以本计划为准即可：

1. **sid 正则**从 `^[0-9a-f]{8}$` 放宽为 `^[A-Za-z0-9_-]{1,64}$`（spec §3/§4.5 已改），并因此多一层意义：`session_id` 来自客户端可控的 `/ws/chat/{session_id}`，这层校验顺手堵掉一个**既有路径穿越洞**（T1 Step 1 最后一个用例守着）。
2. **面板拖宽条上移到 Layout**（spec §5.1 已注），面板组件不再持有 `onResize` prop。
3. **预览区固定 55% 比例**，不做可拖分隔条（spec §5.2 已改，理由：YAGNI）。
4. **§8 文件清单补齐**：`web/src/types/index.ts`、`.gitignore`、`web/src/api/http.ts` 的实际职责（导出 `apiUrl`）已写入 spec。

## 执行期修正（TDD 红相不拓获、只有真机/真 lint 才暴露的 4 处）

上面的任务正文是**写计划时的方案**；实际执行中以下 4 处已修正，以代码为准（spec/计划不回改，保留决策轨迹）：

1. **Task 10 的图标名不存在**：`IconImage` / `IconSidebar` 在 `@tabler/icons-react` v3.44 里没有（已用 `grep "declare const X:" node_modules/@tabler/icons-react/dist/tabler-icons-react.d.ts` 逐个核实），改用 `IconPhoto` / `IconLayoutSidebarRight`。
2. **Task 10 的 HEAD 探测必须去掉**：本后端所有路由对 HEAD 一律 404（只有 GET 可用，已对 `/api/health` 等既有路由交叉验证），原探测会把每个产物误判为“已失效”、预览永远退化成卡片。现在 frame 类直接渲染，`missing` 只留给取文本失败。
3. **Task 9/10 的 effect 写法违反 eslint-plugin-react-hooks v7**：`react-hooks/set-state-in-effect` 禁止在 effect 体里同步 setState。`useSessionArtifacts` 改为按 `payload.sid` 派生 `data`/`loading`；`ArtifactsPanel` 的选中项改为 `selRel` + 派生 `active`，切会话由 Layout 的 `key={sid}` 重挂载来清空。
4. **URL helper 不能与组件同文件导出**：`react-refresh/only-export-components` 要求组件文件只导出组件，所以 `artifactFileUrl` / `artifactDownloadUrl` 拆到 `web/src/utils/artifactUrl.ts`。

另外两个属于计划本身的代码缺陷，已在执行时改掉：`Path.lstrip("./")` 会把 `.hidden.html` 吃成 `hidden.html`（改为直接 `base / raw`）；下载链接误用 `&download=1`（无前序 `?`）。
