# 会话产物侧边栏（Session Artifacts Sidebar）设计

> 给 zlink-agent 加一个可手动展开/收起的右侧产物栏，并让"一次会话产出的所有文件"有了唯一归属：会话目录化（`data/sessions/<sid>/`，内含 `session.json` + `artifacts/`）。参考实现是 `dsh-better-sidebar`（DSH 的 VSCode 风格侧边栏插件，本地 `/tmp/dsh-sidebar/DSH-better-sidebar-main`），本次只借鉴其中 3 个点，明确不做其余全部（见 §2.2）。

## 1. 背景与动机

### 1.1 现状（已核实）

- **产物四处散落，无归属**：`agent/skills/u8/SKILL.md:136`、`nc/SKILL.md:128`、`yonsuite/SKILL.md:104` 明写"默认保存到桌面 `~/Desktop/U8_YYYY-MM-DD_类型.html`"（`u9c` 无此约定）；`iuap-data-reporting` / `iuap-data-visualizing` 规定"默认产物为 .html 文件并回传路径"但没有目录约定；`write_file` 的相对路径走 `Path(_expand_path(path))`（`agent/tools/file_tools.py:163`），即落在**后端进程 cwd**——源码仓库根目录，这正是 `/*.html` gitignore（commit `ca4f13b`）要收拾的根因。
- **会话是扁平单文件**：`data/sessions/<sid>.json` + `index.json`（`agent/session_manager.py:11-13`），没有"会话目录"这个概念，产物无处挂靠。
- **工具层不知道自己在为哪个会话干活**：`registry.dispatch(name, args)`（`agent/tools/registry.py:244`）签名里没有会话信息，全项目零 `ContextVar`。
- **前端没有任何文件视图**：左侧 `Sidebar.tsx`（119 行）是导航栏；`Layout.tsx` 的 `.app-layout` 是 `sidebar | main-area` 两列 flex（`web/src/styles/global.css:70,236`）；无文件浏览 API、无预览组件。
- **好消息（决定了改造成本）**：`SESSIONS_DIR` 全项目只有 `agent/session_manager.py` 引用（grep 核实），改布局的爆炸半径仅此一个文件。

### 1.2 参考项目值得借鉴的 3 个点

| 借鉴点 | DSH 做法 | 本次落地形态 |
|---|---|---|
| 会话隔离 | 布局/Tab/面板按 session 持久化 | 产物按 `<sid>/artifacts/` 物理隔离，切会话即换根 |
| "本轮文件"视角 | 实时追踪模型 read/write/edit 并按文件分组 | 只取"写出"这一半：会话内目录扫 + `external.jsonl` 登记 |
| `sidebar_open` 工具 | 模型主动在**当前会话**侧边栏打开 file/folder/url，宿主→浏览器 WS 推送 + 无视图时排队重放 | **本次不做**（见 §2.2）；`external.jsonl` 为它留了接口位 |

### 1.3 明确不借鉴（划界）

DSH 是 28 个源文件目录 + 100+ 测试的独立插件仓库。以下全部排除：`registerTab`/`registerFileViewer` 服务化框架（只有 1 个页面，为它建扩展框架是纯负债）、底部面板与 tab 拖拽拆分、CodeMirror 编辑器、xterm+node-pty 终端、Git diff 视角、侧边对话、自由浮窗、按需 chunk 加载、多语言。

## 2. 范围

### 2.1 v1 包含

1. 会话目录化 + 一次性幂等迁移（§3）
2. `current_session_id` ContextVar + 工具层"会话工作目录"路径归一（§4.1–4.2）
3. 4 个后端只读/无副作用端点：列表、文件、zip 打包、Finder 显示（§4.3）
4. system prompt 注入产物目录 + 3 个 ERP skill 文案改写（§4.4）
5. 前端右侧产物栏：手动展开/收起（含 `⌘B`）、可拖宽、列表 + 尽力而为的内嵌预览 + 浏览器打开/下载/Finder 三个操作（§5）
6. "会话外文件"灰显分组（B2）（§4.2 + §5.4）

### 2.2 v1 不包含

编辑器与任何写操作（删除、重命名同理）、内置浏览器 webview、终端、Mermaid 渲染、按会话持久化面板布局、`sidebar_open` 工具、MCP 工具写出文件的归一（第三方 server 自管子进程 cwd，超出可控范围）、历史 `~/Desktop` 产物的回溯搬移。

## 3. 数据布局与迁移

```
data/sessions/
├── index.json                  # 不动（会话列表唯一来源）
└── <sid>/
    ├── session.json            # 原 <sid>.json 原样搬入（id / title / messages）
    ├── artifacts/              # 产物唯一落点 = 工具的"会话工作目录"
    └── external.jsonl          # 会话外绝对路径写出登记（append-only，一行一条）
```

`agent/session_manager.py` 的改动（唯一碰路径的模块）：

- `create_session`：建 `<sid>/` + `<sid>/artifacts/`，写 `<sid>/session.json`；
- `load_session` / `save_session`：读写 `<sid>/session.json`，`load_session` 保留一次旧 `<sid>.json` 只读回退（应对迁移跳过或用户手工塞回的备份文件），`save_session` 只写新路径；
- `delete_session`：`shutil.rmtree(SESSIONS_DIR / sid)`（产物与 external 连带清理，不留孤儿）；
- 新增 `session_dir(sid)` / `artifacts_dir(sid)` 两个公开访问器 —— ContextVar、后端端点、工具 hook 一律经它取路径，禁止别处手拼 `DATA_DIR / "sessions"`。

**迁移**：`backend/main.py` lifespan 里调用一次 `migrate_session_layout()`，幂等：

1. 遍历 `SESSIONS_DIR/*.json`（排除 `index.json`）；
2. `sid` 不在 `^[A-Za-z0-9_-]{1,64}$` 内 → 跳过并 warn；
3. `<sid>/` 已存在 → 跳过（幂等）；
4. `mkdir <sid>/` + `rename <sid>.json → <sid>/session.json` + `mkdir <sid>/artifacts/`。

每个 sid 独立 `try`，单个失败只记 log、不抛出、不阻塞启动 —— 后端必须在半成品状态下也能起来。结果：现存 33 个会话变 33 个目录，各带一个空 `artifacts/`。

**顺手修一个既有缺陷**：`agent/tools/cronjob_tools.py:349` 已 `create_session()` 拿到 sid，但 `:400` 的 `agent.run_conversation(...)` 没传 `session_id`（该参数在冻结签名里已存在）。不补这一句，定时任务产出的报告没有归属会话。补参数不算破坏契约（§8 有回归测试守着）。

## 4. 后端契约

### 4.1 会话上下文（新文件 `agent/session_context.py`，~25 行）

```python
current_session_id: ContextVar[str | None]
def artifacts_dir_or_none() -> Path | None   # 供 hook / prompt 注入使用
```

在 `agent/core/agent_adapter.py` 的 `run_conversation_async` 入口（`effective_session_id` 算出后）`set`。覆盖性已核实：`run_conversation` 同步壳经 `asyncio.run` 委派给它（`agent_adapter.py:533-551`），工具执行走 `await asyncio.to_thread(registry.dispatch, ...)`（`agent/core/tool_dispatcher.py:304`），而 `asyncio.to_thread` 会 `copy_context()`，故 ContextVar 在 handler/hook 线程内可见；`FileMutationQueue.enqueue` 在调用线程内带锁执行、无独立 worker 线程，同样可见。**ContextVar 未 set（单测、直接调工具、未来 CLI）时一切路径行为退回今天的进程 cwd，保证现有 `test_file_tools.py` 零改动全绿。**

### 4.2 路径归一 + external 登记（新文件 `agent/tools/session_artifact_hook.py`，~60 行）

选择在**一处 before-hook + 一处 after-hook**里做完，不改 `file_tools.py` 内部：规则需要知道工具名和参数名，而 `_expand_path()` 是读写共用且看不到工具名。before-hook 在 `dispatch` 内先于 handler 运行，改写后的绝对路径自然流进 handler，结果串里也带回真实路径。

| 工具 | 参数 | 相对路径处理 |
|---|---|---|
| `write_file` / `patch` / `read_file` / `ls` / `glob` / `search_files` | `path` | → `artifacts_dir(sid) / path` |
| `terminal` | `workdir`（缺省时视为 `.`） | → `artifacts_dir(sid)`（现为 `os.getcwd()`，`terminal_tool.py:173`） |
| 绝对路径 / `~` 开头 | — | 原样尊重，不改写 |

after-hook：工具是 `write_file`/`patch` 且 `success`，且解析后的绝对路径不在 `<sid>/artifacts/` 内 → 向 `external.jsonl` 追加一行 `{"path": "...", "tool": "write_file", "ts": "..."}`。只记写出、不记读取；不做同步、不做清理（列表端点按 path 去重取最新，并现场 `exists` 校验）。

before-hook 只改写 `args`，永不返回 `__block__`；注册顺序在 `security_hooks`（❌ 区，零改动）之后，三层安全模型不受影响。

### 4.3 API（新文件 `backend/api/session_artifacts.py`，挂进 `backend/main.py`）

| 端点 | 说明 |
|---|---|
| `GET /api/sessions/{sid}/artifacts` | `{items:[{name, rel, size, mtime, kind}], external:[{abs_path, tool, exists, mtime}], count, truncated}`。递归扫 `artifacts/`（深度 ≤6，上限 300 项，超出 `truncated:true`）；`kind` ∈ `html/md/image/pdf/text/other` 由扩展名映射；目录不存在时懒重建。 |
| `GET /api/session-files/{sid}/{rel}` | 唯一的内容出口，通吃 iframe 加载与前端 fetch 文本。同一份路径校验（§4.5），返回 `FileResponse` + 准确 media_type + `X-Content-Type-Options: nosniff`；`?download=1` → `Content-Disposition: attachment; filename*=UTF-8''…`。**同源**是这套设计成立的前提：报告里的相对资源（`src="chart.js"`）顺同一前缀命中本端点。 |
| `GET /api/sessions/{sid}/artifacts/zip` | `StreamingResponse` + `zipfile` 流式打包 `artifacts/`；跳过软链接；总大小 >200MB → 413。 |
| `POST /api/sessions/{sid}/artifacts/reveal` | 入参 `rel` 或 `abs_path`；`abs_path` 仅当它已出现在本会话 `external.jsonl` 中才接受，否则 403。跨平台 `open -R` / `explorer /select,` / `xdg-open <父目录>`，`subprocess.Popen` 不 wait。 |

> 新模型 `ArtifactItem` / `ArtifactListResponse` / `RevealRequest` 放进**新文件** `backend/schemas/session_artifact.py`，不去动 `backend/schemas/session.py`（❌ 区）—— 既有响应契约零触碰。

### 4.4 Prompt 注入与 skill 文案

`build_system_prompt()`（`agent/core/message_builder.py:34`）新增 `artifact_dir: str = ""` 片段（与既有 `erp_context` 同一拼接机制），内容：本次会话产物目录的绝对路径 + "写文件用相对路径即自动落入该目录；不要把产物写到桌面或仓库目录"。`agent_adapter.py` 在每轮构建时从 ContextVar 取值（会话未定时不注入，零副作用）。

改写 `agent/skills/{u8,nc,yonsuite}/SKILL.md` 三处"默认保存到桌面"条目为会话产物目录（形如 `artifacts/U8_YYYY-MM-DD_类型.html`）。注意 §2.2：内置 skill 只读约定针对 API 层的 DELETE/EDIT，源码内文案修改是本仓库正常改动。

### 4.5 路径校验（两个读端点共用 `_resolve_in_artifacts(sid, rel)`）

1. `sid` 必须匹配 `^[A-Za-z0-9_-]{1,64}$`，否则 404（不 500）。这个校验同时是补一个既有洞：`session_id` 来自客户端可控的 `/ws/chat/{session_id}`（`backend/api/chat.py:96`），而 `session_manager` 直接拿它拼路径 —— 改前 `/ws/chat/../../../../tmp/pwn` 就能把会话文件写到仓库外；目录化 + reveal 端点让这个面变得更有吸引力，所以校验收在 `session_manager.is_valid_session_id()` 单一入口，存与读共用。不取更严的 `^[0-9a-f]{8}$` 是因为历史/测试数据里存在 `sess-stream` 这类合法 id，会误拒（两者都同样挡住 `../`）。
2. `rel` 拒绝绝对路径；反斜杠归一为正斜杠后重判（Windows 打包版）；拒绝任意 `..` 分段；
3. `resolve()` 后断言 `is_relative_to(artifacts_dir(sid).resolve())`，挡住软链接逃逸；
4. 名字黑名单 `session.json` / `external.jsonl` 双保险（它们本不在 `artifacts/` 下）。

**为什么不用 `StaticFiles` 挂载**：`app.mount(SESSIONS_DIR)` 会把 `session.json`（含完整对话记录与 ERP 数据）暴露给本机任意页面/进程 —— 后端无鉴权，桌面端只绑 `127.0.0.1` 并不等于本机无风险。显式路由多写约 25 行，换来作用域收紧。

## 5. 前端

### 5.1 布局与开关

`.app-layout` 是 flex row（`global.css:70`），右侧栏就是它的第三个 flex 子元素，**只在对话页**（`Layout.tsx` 的 `location.pathname === "/"`）渲染，切到历史/设置页自动消失。

- 默认宽 320px，可拖 260–560px（拖拽条是 `.app-layout` 的 flex 子元素，宽度状态由 `Layout` 持有，面板不管拖宽）；
- **两态手动切换**：`«` 或顶栏按钮即完全收起（对话区回全宽），收起态不留图标条；
- 顶栏 `.top-bar` 右侧新增常驻按钮（`IconPackage` + 产物数量角标），快捷键 `⌘B`（已核实全局 keydown 仅 `Drawer.tsx` 的 Esc，无冲突）；
- 折叠偏好存 `localStorage["zlink.artifactsPanel"]`；**用户从未手动操作过时**默认值取 `count > 0`（首次生成报告会自动弹出来）。

### 5.2 组件与 hook

- `web/src/components/ArtifactsPanel.tsx`（新，~230 行）：头部（标题 + 计数 + 刷新 + 收起）/ 列表区 / 预览区（固定占面板 55%，不做可拖分隔条 —— YAGNI）/ 底部操作（打包下载 zip）。
- `web/src/hooks/useSessionArtifacts.ts`（新，~50 行）：`fetch /api/sessions/{sid}/artifacts`，参数 `(sid, version)`，`sid` 变化立即拉，`version` 变化 300ms 防抖重拉；请求失败保留上次数据并显示重试条。
- 无新依赖：Markdown 复用 `StreamingMarkdown.tsx`（react-markdown + gfm），代码复用 `CodeBlock.tsx`（highlight.js）。

### 5.3 刷新链路（零新 WS 事件类型）

`hooks/useChat.ts` 已有的 `tool_result` 分支加一个可选 `onToolResult` 回调（与现有 `onApprovalRequest` 同一模式）→ `ChatPage` 递增 `artifactsVersion` → hook 防抖重拉；`done` 帧再兜一次。面板右上角常驻手动刷新按钮，兜住"用户自己往目录里塞文件"。

### 5.4 预览按 kind 渲染

| kind | 方式 | 备注 |
|---|---|---|
| html | `<iframe src="/api/session-files/{sid}/{rel}" sandbox="allow-scripts">` | **不给** `allow-same-origin`：ECharts 等 CDN 脚本照常跑，但产物拿不到同源 API |
| pdf | `<iframe src=…>` | 浏览器内置 viewer |
| image | `<img>` | 点击原尺寸 |
| md | fetch 文本 → `StreamingMarkdown` | 不做 Mermaid |
| text/code | fetch 文本 → `CodeBlock` | >5MB 退化为下载卡片 |
| other | 下载卡片 | — |

列表为主，预览是**尽力而为**：加载失败或不支持的类型 → 预览区退化为一张卡片（大字文件名 + 「在浏览器打开 / 下载」）。每个条目 hover 三个操作：**在浏览器打开**（`<a href target="_blank">`，靠 §5.5 的 CSP 兜安全，不需要后端 `open`）、**下载**（`?download=1`）、**在 Finder 显示**（`/reveal`）。

「会话外文件」灰显折叠组只做「在 Finder 显示 / 复制路径」，路径已失效则标灰。

### 5.5 「在浏览器打开」的安全洞

顶层页面直接打开产物 URL 时，产物 JS 会以我们源名的顶层文档运行，就能 `fetch("/api/sessions")` 拖走全部会话内容（含 ERP 数据）。解法：文件端点对 html 响应加 `Content-Security-Policy: sandbox allow-scripts`，浏览器让它在独立源里运行。iframe 侧再叠一个 `sandbox` 属性，两道独立生效。

## 6. 错误处理与边界

| 场景 | 处理 |
|---|---|
| 迁移单个会话失败 | 记 log、跳过、启动不阻塞；`load_session` 旧路径回退可读 |
| 目录与旧文件并存 | 目录优先 |
| `artifacts/` 被手删 | 列表端点懒重建；文件端点 404 |
| 未知 sid | 404；前端 `.catch` → 空态（与现有 `?s=` 处理同风格） |
| 无当前会话（新对话未落库） | 面板显示空态文案"开始对话后，这次会话的产物会出现在这里" |
| `external.jsonl` 坏行 | 逐行 `json.loads`，失败跳过（沿用 `_load_index` 容错风格） |
| 并发写登记 | 单行 `open("a")` 追加（POSIX 短写原子）；前端只读，无锁 |
| 文件 >5MB / 列表 >300 项 / zip >200MB | 分别：下载卡片、`truncated` 提示、413 |
| 离线且 CDN 不可达 | iframe 图表空白 → 「在浏览器打开」按钮兜底 |
| 产物读 `localStorage` | 不透明源下抛 SecurityError，属预期（报告模板不写这个） |

## 7. 测试计划

零网络零 LLM，沿用 `isolated_config` / `MockLLMProvider`：

- **`tests/test_session_layout.py`**：迁移幂等（造 3 个 `<sid>.json` → 迁移 → 断言结构 → 再迁移一次不重复搬不报错）、非法 sid 跳过、目录版 create/save/load/delete、delete 连带清产物与 external、旧路径回退读。
- **`tests/test_session_artifacts_api.py`**：列表 kind 分类 / 300 项截断 / `truncated`；文件端点攻击集全 404（`../`、`..%2f`、绝对路径、指向 `/etc/passwd` 的软链、指向 `session.json` 的软链、`Session.json` 大小写绕过）；html 响应含 `Content-Security-Policy: sandbox allow-scripts`；`?download=1` 的 `Content-Disposition`；zip 条目清单正确；reveal 对未登记的 `abs_path` 返 403。
- **`tests/test_session_artifact_hook.py`**：ContextVar set 时 `write_file("a.html")` 落 `artifacts/`；未 set 时落 cwd（回归保护）；绝对路径不改写；`terminal` 缺省 `workdir` = 产物目录；仅写出且落在会话外才追加 external；坏行跳过。
- **`tests/test_cronjob_artifact_session.py`**：`MockLLMProvider` 脚本化一次 `write_file`，断言产物落在该 job 的会话目录内（守住 §3 那句补漏）。
- **`tests/test_contract_freeze.py`**：加断言 —— `run_conversation` 签名与 6 个返回键零改动。
- **存量**：591 个测试全绿 + `ruff check . && ruff format --check .`。
- **前端**：仓库无 vitest（已核实 `web/package.json`），A 档不为它引测试框架。验证 = `tsc -b` + `npm run build` + 手工 5 条验收：生成报告 → 面板自动弹出 → iframe 预览可交互 → 浏览器打开全屏正常 → 切会话列表随之变化 → 删除会话后目录消失。

## 8. 改动文件清单

**新增**（后端 5 / 前端 2 / 测试 4）
`agent/session_context.py`、`agent/tools/session_artifact_hook.py`、`backend/api/session_artifacts.py`、`backend/schemas/session_artifact.py`、`tests/{test_session_layout,test_session_artifacts_api,test_session_artifact_hook,test_cronjob_artifact_session}.py`、`web/src/components/ArtifactsPanel.tsx`、`web/src/hooks/useSessionArtifacts.ts`

**修改**
`agent/session_manager.py`（目录化 + 访问器 + sid 校验 + 迁移）、`backend/main.py`（lifespan 迁移 + hook 安装 + 挂 router）、`agent/core/agent_adapter.py`（set ContextVar + `artifact_dir` 注入）、`agent/core/message_builder.py`（`artifact_dir` 片段）、`agent/tools/cronjob_tools.py`（传 `session_id`）、`agent/skills/{u8,nc,yonsuite}/SKILL.md`（产物目录文案）、`web/src/components/Layout.tsx`（第三列 + 顶栏按钮 + `⌘B` + Outlet context）、`web/src/pages/ChatPage.tsx`（`bumpArtifacts`）、`web/src/hooks/useChat.ts`（`onToolActivity`）、`web/src/api/http.ts`（导出 `apiUrl`）、`web/src/types/index.ts`（产物类型）、`web/src/styles/global.css`（面板样式）、`.gitignore`（`!docs/superpowers/`）、`pyproject.toml` + `package.json`（1.13.0）、`CHANGELOG.md`、`README.md`、`AGENTS.md`（会话目录结构 + 产物约定 + 记忆同步）

## 9. 已知限制与 v1.1 候选

- `read_file` 等只读工具的相对路径也归一到产物目录 —— 模型想看仓库里某文件时必须给绝对路径。这是"会话工作目录"语义的必然代价。
- **已修复**：`agent/skills/{china-hotdata,minimax-docx,minimax-pdf,pptx-generator}` 四段 skill 文案的相对路径命令已改为从仓库根出发的绝对路径（`commit 51e07e9`）。
- MCP 工具（如 chart server）写出的文件不归一，也不登记；`external.jsonl` 是给它们的接口位。
- v1.1 候选：`sidebar_open` 工具（模型主动把产物推到本会话侧边栏，复用 `external.jsonl` + 一个 WS 推送通道）、"本轮文件"分组（面板上标第几轮生成）、会话导出（单 sid 的自包含 zip 已在 v1）。
