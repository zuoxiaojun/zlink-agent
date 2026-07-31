# Changelog

## v1.8.0 — 2026-07-31 (桌面端冷启动优化：十几秒 → 1 秒级)

**范围**: 打包版 Electron 桌面客户端冷启动从十几秒优化到 1 秒级（实测 0.8~1.8s，目标 ≤5s）。

### 改动

- **PyInstaller onefile → onedir** (`scripts/build-pyinstaller.sh`, `electron-builder.yml`, `electron/main.js`): 后端默认打包为目录形式，消除每次启动的自解压（最大耗时项）；`--onefile` 保留为显式回退；冒烟测试等待上限 45s → 15s 作为回归保护
- **延迟工具发现** (`backend/api/chat.py`, `backend/api/tools_api.py`): `discover_tools()` 从模块顶层移到首次使用时（`threading.Lock` 幂等），24 个工具模块不再阻塞后端启动；对话路径本就走 `AIAgent._ensure_discovered()` 懒加载
- **Electron 启动并行化** (`electron/main.js`): 端口检查与窗口创建/loading 渲染并行；健康轮询 1000ms → 100ms；全链路 `[startup]` 计时日志
- **启动计时埋点** (`backend/pyinstaller_entry.py`, `backend/main.py`): import 各阶段 + lifespan 各步骤耗时日志；uvicorn 日志级别 info → warning

### 修复

- **onedir 布局下 Chart MCP 路径错层** (`backend/main.py`): onedir 时 `sys.executable` 位于 `Resources/zlink-backend/` 内，Resources 目录定位需向上一层，否则打包版 Chart MCP 永久失效

### 已知现象

- onedir 首次启动（安装后第一次运行）macOS 会对 `_internal/` 内所有 dylib 做一次性校验，可能超过 10 秒；仅发生一次，之后即进入 1 秒级

### 测试

- 新增 `tests/test_tools_api.py`（3 个：懒发现幂等 / 线程安全 / 端点触发发现）

## v1.7.2 — 2026-07-21 (聊天流式输出美化 + 图标统一)

**范围**: 聊天页流式输出体验全量美化（纯前端，后端零改动）；修复启动页图标与主图标不一致。

### 新增

- **代码块升级** (`web/src/components/CodeBlock.tsx`): 语法高亮（新增依赖 rehype-highlight + highlight.js github 浅色主题）、语言标签、复制按钮；`MessageContent` 从 ChatMessage 抽取为独立文件并 memo
- **工具调用卡重做** (`web/src/components/ToolStepCard.tsx`): 工具名 + 完成/失败状态图标，参数与返回 JSON 格式化默认折叠，调用与结果按 tool_call_id（缺失时按顺序）配对；clarify choices 可点 chips 行为保留
- **推理内容折叠** (`web/src/components/ReasoningBlock.tsx`): "思考过程"流式时自动展开、回合结束自动收起、可手动切换
- **回到底部按钮** (`web/src/pages/ChatPage.tsx`): 上滚超过 150px 出现悬浮按钮，点击平滑回底并恢复跟随
- **图标生成脚本** (`scripts/gen_loading_icon.py`): 从 `packaging/app-icon.png` 一键同步启动页内嵌图标与 favicon（macOS sips，零第三方依赖，幂等）

### 改动

- **流式渲染性能** (`web/src/hooks/useChat.ts`): token/reasoning_token 50ms 批量缓冲 flush，取代每 token 一次 dispatch 导致的全量重渲染 + 整段 markdown 重解析
- **宽表格**: markdown 表格外包 `.table-wrap` 横向滚动容器，`table-layout` fixed → auto，宽表不再被压扁
- **图标统一** (`electron/loading.html`): 启动页手画 SVG 近似图替换为真实图标的内嵌 base64 PNG（CSP 放行 `img-src data:`）；`web/public/favicon.png` 用 app-icon.png 重新导出为 256px 真 PNG（原文件实为 JPEG 冒充 PNG）

### 修复

- **流式光标从不生效**: `StreamingText.tsx` 是死代码导致 `.streaming-text` 闪烁光标样式永远挂不上；已将类挂到流式气泡并删除死文件
- **思考完成后三点动画永久跳动** (`web/src/components/ChatMessage.tsx`): 空内容 assistant 消息（如纯 tool_calls 消息）无条件渲染 thinking-indicator，改为仅流式进行中且无内容时显示
- **`--text-muted` 未定义** (`web/src/styles/global.css`): blockquote 引用了不存在的 CSS 变量，已在 `:root` 补充定义

### 删除

- 死代码/死资源: `web/src/components/StreamingText.tsx`、`web/public/logo-ios5.png`、`web/src/assets/react.svg`；`.streaming-bubble` / `.tool-card` / `.tool-result-inline` 无引用样式

## v1.7.1 — 2026-07-18 (打包版点击修复 + 启动体验)

**范围**: 修复打包版窗口点击完全无响应的严重 bug（loading.html 整页拖拽区残留），重设计启动加载页，全新安装默认启用内置技能。

### 修复

- **打包版点击/悬停完全无响应** (`electron/loading.html`): 加载页 `html, body { -webkit-app-region: drag }` 把整页设为窗口拖拽区，拖拽区是窗口级状态，`loadURL` 跳转正式前端后残留，整窗鼠标事件被系统截去拖窗口。已删除并加防回退注释
- **窗口无法拖动**: `titleBarStyle: hiddenInset` 无原生拖动区，改由 `.electron .top-bar { -webkit-app-region: drag }` 提供（`web/src/styles/global.css`）

### 改动

- **全新安装默认启用全部内置技能** (`agent/skill_manager.py`): `active_skills.json` 不存在时以全部内置技能为初始值并落盘；之后以文件为准，用户显式全关（`[]`）也会被尊重。老用户行为不变
- **启动加载页重设计**: 与前端一致的浅色 Ant/Arco 风格（浅灰底 + 白卡片 + 橙红渐变 logo），替换原深色 Tokyo Night 风格
- **Electron** 43.1.1
- **构建脚本** (`scripts/build-electron.sh`): 默认 `ELECTRON_MIRROR=npmmirror` 镜像，避免 Electron 运行时从 GitHub 下载停滞（可用 `ELECTRON_MIRROR=""` 覆盖回官方源）

### 测试

- `tests/test_skill_manager.py`: +2 用例（全新安装默认启用并落盘、显式 `[]` 被尊重），全量 397 通过

## v1.7.0 — 2026-07-17 (ERP 工具内置化，MCP 子进程移除)

**范围**: 将 YonSuite 和 NC 从 MCP 子进程迁移为内置工具 (`agent/tools/erp_*_tools.py`)，移除 `mcp_server/` 中 40+ 文件，解决打包时 dylib relocation 问题。新增 Python bundle @rpath 修复。Chart MCP 保留为预置 MCP。

### 新增

- **YonSuite 内置工具** (`agent/tools/erp_ys_tools.py`): 从 `mcp_server/ys_mcp_server/` 迁移 11 个工具（`ys_api`、`query_sale_orders`、`query_purchase_orders`、`query_production_orders`、`query_stock`、`query_customers`、`query_vendors`、`query_products`、`query_opportunities`、`query_vouchers`、`query_user_todos`）
- **NC 内置工具** (`agent/tools/erp_nc_tools.py`): 从 `mcp_server/nc_mcp_server/` 迁移 4 个工具（`nc_query`、`nc_list_tables`、`nc_describe_table`、`nc_raw_sql`）
- **Python bundle @rpath 修复** (`scripts/build_utils.py`): 自动修复 Rust 原生扩展（pydantic_core、watchfiles、cryptography 等）的 `@rpath` 自引用，解决用户机器上 import 崩溃问题
- **MCP 添加预设** (MCP 页面): 一键填充 Chart 图表、Playwright 等常用 MCP 配置

### 改动

- **`backend/main.py`**: 移除 YonSuite/NC MCP 子进程启动逻辑，Chart MCP 保留为预置自动启动
- **`backend/api/config_api.py`**: 移除 yonsuite MCP 重连逻辑
- **`backend/api/erp_clients_api.py`**: 移除 MCP 同步逻辑，NC 测试连接改为直连 Oracle
- **`backend/api/tools_api.py`**: `/api/tools` 过滤外部 MCP 注册的工具（toolset 以 `mcp-` 开头的不显示）
- **`agent/erp_clients/base.py`**: 移除 `MCPStarterConfig`（不再需要）
- **`agent/context_compactor.py`**: 修正 DeepSeek 模型上下文窗口为 1M（之前误为 128K）
- **`electron-builder.yml`**: Chart MCP 打包进 `Resources/mcp-chart/`

### 删除

- **`mcp_server/`** 整个目录（ys_mcp_server、nc_mcp_server、nc_mcp 共 40+ 文件）
- **`tests/test_nc_mcp_config.py`**、**`tests/test_nc_mcp_starter.py`**

### 构建

- **`build_utils.py`**: 新增 `_fix_rpath_self_references()` 函数，Step 7 验证增强为逐包 import
- Python bundling 不再需要手工 dylib relocation（ERP 不走 MCP 子进程）

## Unreleased — 配置存储 doc/code 对齐

> v1.6.0 的发布说明里把"密钥改存到 `data/.env`+chmod 0600"列为已完成的改动，但实际落地后走了更简单的路径：**全部写入 `data/config.json` 明文**，既无 `.env` 拆分也无 Fernet。本节只补齐文档/代码对账，不影响运行行为。

### 文档/代码对账补充

- **浏览器工具正式移除**：删除 `agent/tools/browser_tool.py` 及 `tests/test_browser_tool.py`，共移除 9 个工具（`browser_navigate` 等）。README 工具计数同步更新为 54。需要浏览器自动化的用户可通过 MCP 管理页添加 `@playwright/mcp`。
- **工具/技能计数更新**：README 中 41 个内置工具 → 54 个，19 个内置技能 → 20 个，与当前 `agent/tools/registry.py` 和 `agent/skills/` 扫描结果一致。
- **默认审批模式调整**（`agent/config_model.py`）：新安装的默认 `approval_mode` 从 `allow_all` 改为 `approve`，高风险工具（如 `terminal`）首次执行会触发前端确认弹窗。已有配置的 `config.json` 中的值不受影响。
- **修复打包版 NC 查询报 `No module named 'cryptography.hazmat.primitives.kdf'`**（`scripts/build-pyinstaller.sh`）：PyInstaller 未自动包含 `oracledb` thin mode 依赖的 `cryptography` 子模块，显式添加 `cryptography.hazmat.primitives.kdf` 等 hidden imports。需重新打包生效。
- **新增 PyInstaller 依赖管理工具链**：
  - `scripts/pyinstaller_hidden_imports.py`：集中维护 hidden imports 清单，按功能分类（Web 框架/LLM/数据库/工具模块等），打包脚本直接引用。
  - `scripts/check_dynamic_imports.py`：自动扫描代码中的函数内 import、try-except ImportError、importlib 动态导入，与清单比对并提示补录；已知可选依赖（如 `playwright.sync_api`）单独标记。
  - `scripts/build-pyinstaller.sh`：接入集中清单，打包前自动扫描动态导入，打包后自动冒烟测试（启动 exe、验证版本接口、62 个工具注册、NC 工具注册）。

### 改动

- **`agent/config_model.py` docstring**: 改为与 `config_manager.py` 实际行为一致（明文存 `config.json`，目录 0700 / 文件 0600）。
- **`agent/config_manager.py`**: `save()` 现在每次写入后将 `data/config.json` chmod 0600（best-effort，Windows/网络盘上无 chmod 时静默 no-op）。
- **`agent/core/agent.py`**: 注释里删除对已不存在的 `config_manager.ERP_SECRET_FIELDS` 的引用。
- **`mcp_server/nc_mcp/config.py`**: `_decrypt_password` → `_password_or_empty`，去掉"解密"函数名带来的错觉，实际行为没变。
- **新增测试**: 断言 `config_manager.save()` 写出的 `config.json` 权限为 `0o600`。
- **`AGENTS.md`**: 删除所有引用 `encrypt_secret` / `decrypt_secret` / `Fernet` / `encrypted:` 前缀的描述（包括 Flow C、`config_manager` 函数签名块、`Configuration Encryption Convention` 整节、ERP 设置步骤、Hub diagram 等共 13 处）。

### 注意（向后兼容）

- v1.6.0 提到的"`.env` 拆分"从未生效；老用户的密钥如果存在于 `~/.zlink-agent/data/.env` 中会被忽略（`config_manager` 只读 `config.json`）。如需保留，请把密钥从 `.env` 复制到 `config.json` 对应字段后重启动后端。

## v1.6.2 — 2026-07-14 (MCP 管理工具 + 自动审批)

**范围**: 新增 6 个 agent 可调用的 MCP 管理工具，opencode 配置添加自动审批。

### 新增

- **MCP 管理工具** (`agent/tools/mcp_management_tool.py`): 注册 6 个工具供 LLM 在对话中直接管理 MCP 服务器
  - `mcp_list_servers` — 列出所有 MCP 服务器状态
  - `mcp_add_server` — 添加并连接新 MCP 服务器
  - `mcp_delete_server` — 删除 MCP 服务器（内置服务器受保护）
  - `mcp_toggle_server` — 启用/停用切换
  - `mcp_test_server` — 测试连接
  - `mcp_reload_servers` — 全部断开后重连
- **自动审批**: `~/.config/opencode/opencode.json` 添加 `"permission": "allow"`

### 版本号同步

- `pyproject.toml` / `package.json` / `CHANGELOG.md` / `README.md` 四文件统一

## v1.6.1 — 2026-07-12 (代码优化 + 测试覆盖增强 + 构建修复)

**范围**: 代码质量优化、安全修复、测试覆盖从 44% 提升至 53%、Windows 构建脚本重写。

### 新增

- **356 个测试**（新增 72 个）: 覆盖 file_tools、config_api、mcp_api、skills_api、skill_manager、slash_commands、web_tools、vision_tool、memory_tool、project_tools、process_tool、session_search_tool、web_extract_tool、message_builder、openai_compat、chat.py 辅助函数
- **Win 构建脚本**: 从 PyInstaller 重写为 Electron（`electron-builder --win`），修复引用不存在的 `.spec`/NSIS 文件问题

### 改动

- **tiktoken 默认启用**: 移除 `YS_USE_TIKTOKEN` 环境变量开关，改设 `YS_USE_TIKTOKEN=0` 可禁用
- **`cryptography` 依赖移除**: Fernet 加密已在 v1.5.2 移除，不再需要
- **`zip(strict=False)` → `strict=True`**: 防止 `names`/`results` 长度不匹配时静默截断
- **`AgentPhase` 别名清理**: 移除 `Phase→AgentPhase` 向后兼容别名
- **`_generate_summary` OpenAI 客户端缓存**: 改用 `lru_cache` 复用实例
- **`os.environ` 全局污染修复**: 从 `chat.py`（每 WebSocket 连接）移到 `main.py`（启动时一次设置）
- **DDG 搜索 `html.parser` 替代正则**: 用 stdlib `HTMLParser` 替代脆弱的 `re.findall` 解析
- **统一图标库**: 移除 `lucide-react`（0 次 import），仅保留 `@tabler/icons-react`
- **`ResourceWarning` 修复**: `search_index.py` 添加 `close_all_connections()`，测试自动清理
- **ruff 全清**: 213 个 Python 文件全部格式化，零 lint 错误

## v1.6.0 — 2026-07-12 (技能工具增强 + 密钥管理重构 + 定时任务系统)

**范围**: 大幅扩展技能和工具系统，重构密钥存储方式，新增定时任务管理。共计 41 个内置工具 + 19 个内置技能。

### 新增

- **密钥存储重构**: 移除 Fernet 加密，改为 `data/.env` 明文 + `chmod 0600`。不再依赖 hostname + salt 派生密钥，项目改名也不会导致密钥丢失
- **8 个新工具**:
  - `execute_code` (code): 沙箱 Python 执行（安全模块白名单）
  - `project_*` (project): 项目管理（创建/列表/切换）
  - `vision_analyze` (vision): 图片视觉分析
  - `read_terminal` / `close_terminal` (terminal): 终端历史读取和进程终止
  - `cronjob_*` (cron): 定时任务（创建/列表/删除/启停/立即执行/编辑）
  - `process` (system): 系统进程管理（列表/终止）
- **5 个新内置技能**: `research`、`china-hotdata`、`调研分析`、`skill-vetter`、`anysearch`、`westock-data`（共 19 个）
- **定时任务前端管理页**: 侧边栏「定时任务」菜单，支持 CRUD、立即执行（通过 WebSocket 流式展示 AI 执行过程）、执行结果查看
- **斜杠命令弹窗**: 输入 `/` 弹出命令 + 技能列表，支持键盘导航和自动补全
- **可点击 clarify 选项**: clarify 工具结果渲染为按钮，点击直接发送消息
- **开场引导词**: 重写为简洁版，覆盖全部能力分类

### 改动

- **`agent/config_model.py`**: 移除 `_encrypt`/`_decrypt`/`_derive_key`/`model_dump_encrypted`/`model_validate_decrypted`。所有字段改为明文
- **`agent/config_manager.py`**: 新增 `.env` 读写，`load()`/`save()` 自动合并 `.env` 中的密钥。新增 `_load_env()`/`_save_env_value()`/`_save_env_batch()`/`_save_erp_secret()`
- **`agent/slash_commands.py`**: 新增 `/skills`（列出所有技能）、`/skill`（查看/启用/停用技能）。未知斜杠命令自动匹配技能名
- **`backend/api/chat.py`**: 斜杠命令未命中时自动匹配技能，加载完整指令后交给 AI 执行
- **`backend/api/erp_clients_api.py`**: `GET` 改为从 `config_manager.load()` 读取（含 `.env` 中的密钥）。`PUT` 时密钥写入 `.env` 而非加密到 `config.json`
- **`backend/api/cronjob_api.py`**: 新增 REST API 支持定时任务前端管理
- **`web/src/hooks/useChat.ts`**: 重构 `sendMessage`，支持 sessionOverride 参数；`runningRef` 替代 `state.agentRunning` 避免闭包问题
- **`web/src/api/http.ts` + `ws.ts`**: 移除 `any` 类型，使用 `Record<string, unknown>`
- **`web/src/pages/CronJobPage.tsx`**: 新增完整定时任务管理页面
- **`web/src/components/ChatMessage.tsx`**: clarify 选项渲染为可点击按钮
- **`web/src/components/ChatInput.tsx`**: 集成斜杠命令弹窗组件

### 修复

- **密钥丢失问题**: Fernet 加密 salt 变更导致的历史密钥无法解密 → 改用 `.env` 明文存储 + 文件权限保护
- **React 19 警告**: 修复 `setState in effect`、`refs during render` 等 7 处 React 19 禁止模式
- **ERP 密码不显示**: `GET /api/config/erp-clients` 改为从 `.env` 读取
- **保存按钮卡住**: `ErpTabPanel` 保存后复位 `editing` 状态
- **clarfiy 渲染**: 选项从原始 JSON 改为可点击按钮面板
- **三个点持续闪烁**: `useRef` 追踪运行状态代替闭包中的 `state.agentRunning`
- **定时任务 auto-send**: 从 URL 直接读取 session_id 而非 `state.currentSessionId`
- **ruff 28 处警告**: 全部修复，包括未使用的 import、`datetime.UTC` 别名、import 排序等
- **`no-explicit-any` 12 处**: 替换为 `unknown` + 类型窄化
- **测试隔离**: `.env` 文件隔离到临时目录，避免测试污染用户配置

### 工具数

- 内置工具: 27 → 41 (+ 14 新工具 + MCP 工具不变)
- 内置技能: 15 → 19 (+ 4 新技能)
- 测试: 99/99 通过

### 已知问题

- `html-presentation` 在用户技能区有残留记录（已清理，不影响使用）
- `research` 技能需要手动激活（已激活）


## v1.5.3 — 2026-07-10 (终极破坏式清理: 移除所有 ys-agent 命名兼容)

**范围**: 把 v1.5.0 重命名留下的最后一丝 ys-agent 痕迹全部清除。从这个版本起,项目可以当作 100% 全新项目来对待 — 不再有兼容层、不再有旧命名 shim、不再有 fallback。

**这是最后一次破坏式重命名。v1.6.0 起所有 API 与 CLI 都将保持稳定。**

### 改动

- **`agent/config_model.py`** (破坏): 加密 salt `hostname + "::ys-agent::salt_v1"` → `hostname + "::zlink-agent::salt_v1"`。**所有现有用户的加密 config.json 必须重新输入 API key**
- **`agent/plugin_system/__init__.py` + `agent/extensions/__init__.py`**: 删除 `ys-agent.extensions` plugin entry point 兼容扫描,只保留 `zlink-agent.extensions`
- **`scripts/ys-agent.sh`**: 删除整个文件 (兼容 shim 不再存在)
- **`setup.sh`**: 移除安装兼容 shim 的逻辑 (SHIM_SRC/SHIM_DST/sed-install 块)
- **`scripts/zlink.sh`**: 删除 help 文本中的 `ys-agent` 命令提示
- **`backend/config.py` + `web/vite.config.ts` + `scripts/zlink.sh`**: 删除 `YS_AGENT_HOST` / `YS_AGENT_PORT` / `YS_FRONTEND_PORT` / `YS_AGENT_CORS` 端口变量 fallback,只读 `ZLINK_*`
- **`.env` + `.env.example`**: 端口变量改名 `YS_*` → `ZLINK_*`
- **`AGENTS.md`**: 删除 "v1.5.0 起 `ys-agent` 命令仍可作为兼容 shim" 描述;删除 `~/.ys-agent/data/` 兼容目录说明
- **`README.md`**: 重写 "升级说明" 段为 "全新部署" 段,不再提旧命名

### 净减

- 10 文件, +23 / -42 (净 19 行)
- 1 个文件删除 (`scripts/ys-agent.sh`)

### 破坏式影响清单 (用户必须执行的动作)

1. **加密 config 失效**: 加密 salt 改了,所有老用户的 `config.json` 中 `llm_api_key` / `ys_app_key` / `ys_app_secret` 解密失败。需要重新进入前端「设置」页面输入密钥 (会自动用新 salt 重加密)
2. **CLI 命令**: 老脚本里写的 `ys-agent ...` 必须改成 `zlink ...`
3. **端口变量**: `YS_FRONTEND_PORT` / `YS_AGENT_PORT` / `YS_AGENT_CORS` / `YS_AGENT_HOST` 必须改名 `ZLINK_*`
4. **第三方 plugin**: 如果有第三方包通过 `[project.entry-points."ys-agent.extensions"]` 注册扩展,需要改成 `zlink-agent.extensions`
5. **数据目录**: `~/.ys-agent/` 已被前述迁移为 `~/.zlink-agent/`,如果之前没迁移,会找不到数据

### 保留 (已经无可保留)

无。v1.5.3 已经 0 ys-agent 残留。

### 历史归档 (不改)

- `CHANGELOG.md` v1.5.0 / v1.5.1 / v1.5.2 / 更早的版本段 (历史叙述)
- `docs/superpowers/plans/` (规划文档)
- `dist/release-notes-*` (历史 release notes)


## v1.5.2 — 2026-07-10 (破坏式收尾: 移除 YS_DATA_DIR + ~/.ys-agent/data 兼容层)
**范围**: v1.5.1 完成 CLI 命令名清理, 本 patch 继续把兼容层的「数据目录双兼容」也清掉。物理上已经 `~/.ys-agent` → `~/.zlink-agent`, 这层 fallback 已经没有意义。

### 改动

- **`agent/utils.py`**: `_resolve_data_dir()` 删除 `YS_DATA_DIR` 读取 + 删除 `~/.ys-agent/data/` fallback。优先级链简化为 `ZLINK_DATA_DIR > ~/.zlink-agent/data/`
- **`scripts/migrate.py`**: 读 `ZLINK_DATA_DIR` 而非 `YS_DATA_DIR`
- **`agent/core/metrics.py`**: 12 个 Prometheus 指标前缀 `ys_agent_*` → `zlink_agent_*`。**下游 scraper 与 Grafana 仪表板过滤规则需同步更新**
- **`backend/main.py` + `packaging/launcher.py` + `mcp_server/ys_mcp_server/utils.py`**: 注释同步
- **`tests/test_utils_data_dir.py`**: 删 2 个 YS fallback 测试, 移除冗余 delenv
- **`tests/test_erp_clients_api.py`**: 改用 `ZLINK_DATA_DIR`

### 净减

- agent/utils.py: 5 行代码净减少 (1 个 fallback 分支)
- agent/core/metrics.py: 字符串前缀替换 (0 行业务逻辑变动)
- tests: 1 个测试 (剩 64 PASS)

### 破坏式影响

- 老脚本里 `export YS_DATA_DIR=...` 直接失效, 需改 `ZLINK_DATA_DIR`
- 任何写过 `~/.ys-agent/` 路径的硬编码自动化需更新
- 监控 scraper 抓 `ys_agent_*` 指标全部失效, 必须改成 `zlink_agent_*` (或保留别名/variant scraper)

### 保留兼容 (破坏性超出可接受)

- `agent/config_model.py` 加密 salt (`hostname + "::ys-agent::salt_v1"`) — 删了所有老用户 config.json 解密失败
- `agent/plugin_system/__init__.py` + `agent/extensions/__init__.py` 的 `ys-agent.extensions` plugin entry point group — 老插件兼容
- `scripts/ys-agent.sh` 兼容 shim (CLI) + `setup.sh` 安装该 shim 的逻辑
## v1.5.1 — 2026-07-10 (破坏式 CLI 清理: 镜像环境变量 + sessionStorage key)

**范围**: 把 CLI 残留的旧 `ys-agent` 命名一次清干净,与 v1.5.0 重命名配套形成完整收尾。**破坏式变更,老用户必须重新运行 `setup.sh` / `setup.bat` 才能识别新环境变量名。**

### 改动

- **`setup.sh` + `setup.bat`**: 镜像环境变量 `YS_USE_MIRROR` / `YS_PIP_MIRROR` / `YS_NPM_MIRROR` → `ZLINK_USE_MIRROR` / `ZLINK_PIP_MIRROR` / `ZLINK_NPM_MIRROR` (直接改名, 无回退)
- **`scripts/update.sh`**: 同上
- **`web/src/hooks/useChat.ts`**: sessionStorage key `ys_agent_last_session` → `zlink_agent_last_session` (老浏览器里的旧 key 失效, 最多丢失"记住上次会话"功能, 下次启动重置)

### 净减

- 0 行代码净变化 (仅字符串替换)
- 4 个文件, 22 删 / 24 增

### 保留兼容 (未纳入本次清理)

- `agent/utils.py` 仍读 `YS_DATA_DIR` 环境变量 (数据目录兼容层, 与独立决策点)
- `ys-agent.extensions` plugin entry point group (老插件)
- `agent/config_model.py` 加密 salt 中的 `ys-agent` 字串 (删了会破坏老用户配置解密)
- `scripts/ys-agent.sh` 兼容 shim (AGENTS.md 明确约定)


## v1.5.0 — 2026-07-10 (重命名 ZLink Agent + 多 ERP 架构)
**范围**: 把 YS-Agent 改名为 ZLink Agent（智链 Agent），引入声明性 ERPClient 协议，集成外部 nc-mcp-server 包作为首个非 builtin ERP 客户端。

### 新增

- **`agent/erp_clients/`** 新父目录, 含 `base.py`（ERPClient Protocol + 通用异常 + MCPStarterConfig）、`__init__.py`（声明性注册中心）
- **`agent/erp_clients/yonsuite/`** 从 `agent/yonsuite_client/` 整体 `git mv` 过来, 内部 0 行代码改动
- **`mcp_server/nc_mcp/`** NC MCP 集成入口 (config.py: erp_clients.nc → ORACLE_* env 转换; mcp_starter.py: 调 mcp_manager 启停 nc-mcp-server)
- **`agent/skills/nc/SKILL.md`** NC 工具使用指南
- **`backend/api/erp_clients_api.py`** `/api/config/erp-clients/*` REST 端点
- **`web/src/pages/SettingsERPPage.tsx`** `/settings/erp` 页面 (YonSuite + NC 双卡片)
- **`scripts/zlink.sh`** 新 CLI 入口
- **`tests/test_erp_clients*.py`** 10 个新测试 (覆盖 base 导出、配置转换、占位符、graceful 降级、启用状态联动)

### 改动

- **`pyproject.toml`**: name `ys-agent` → `zlink-agent`, description 重写, version 1.4.1 → 1.5.0, 加 `[nc]` optional extra
- **`agent/utils.py`**: `_resolve_data_dir()` 加 `~/.ys-agent/data/` fallback (双兼容老用户)
- **`agent/config_manager.py`**: 加 `get_erp_config(name)`, 加 `${nc.X}` 占位符解析
- **`agent/tools/mcp_manager.py`**: 启动 MCP server 前解析 env 占位符
- **`backend/api/config_api.py`**: 挂 `/api/config/erp-clients/*` 端点
- **`web/src/App.tsx`**: 加 `/settings/erp` 路由
- **`README.md`**: 标题/Tagline/克隆命令/功能列表/项目结构全量重写
- **`AGENTS.md`**: 标题 + 项目名引用更新
- **`scripts/ys-agent.sh`**: 软链接到 `zlink.sh` (保留兼容)
- **`scripts/update.sh` + `setup.sh` + `setup.bat`**: 镜像环境变量 `YS_USE_MIRROR` / `YS_PIP_MIRROR` / `YS_NPM_MIRROR` → `ZLINK_*`（破坏式）
- **`web/src/hooks/useChat.ts`**: sessionStorage key `ys_agent_last_session` → `zlink_agent_last_session`
- **`docs/architecture.md`**: 加 "多 ERP 抽象" 章节
- **`docs/extending-ys-agent.md`**: 改名为 `extending-zlink-agent.md` + 内容更新
- 其它 ~200 处 `ys-agent` 字符串批量替换

### 净增

- `agent/erp_clients/` 新增 ~150 行 (base.py + __init__.py)
- `mcp_server/nc_mcp/` 新增 ~80 行
- 10 个新测试 → 41+10 = **56/56 PASS**
- ruff check 0 errors
- 数据目录 `~/.zlink-agent/data/` 为新默认, `~/.ys-agent/data/` 兼容 v1.4.x

### 不变

- `YonSuiteClient` 1055 行内部代码 0 改动 (仅移动目录位置)
- builtin MCP server `ys_mcp_server` 0 改动
- 工具名 `mcp_yonsuite_*` 0 改名 (老用户无感)
- LLM provider 抽象 0 改动
- builtin skills 列表 0 改动
- 4 个 untracked Windows 文件 0 改动 (用户另外的事)

## v1.4.1 — 2026-07-10 (移除自动迁移: 项目仅服务新用户) (移除自动迁移: 项目仅服务新用户)

**范围**: 移除 v1.4.0 引入的自动迁移机制。后续只面向新用户,旧用户已通过 v1.4.0 完成升级,不再需要 `ys-agent migrate-data-path` 这类兼容性工具。

### 移除

- **`agent/utils.py`**:
  - `_maybe_migrate_from_legacy()`(首次启动自动复制旧位置)
  - `detect_legacy_data_dirs()`(列出旧位置)
  - `migrate_from()`(执行迁移)
  - `_find_legacy_data_dirs()` / `_has_real_data()` / `_do_migrate()`(内部辅助)
  - `DEFAULT_DATA_DIR` 改为模块级常量(从函数返回改为直接计算)
- **`backend/main.py`**: 启动时不再调用 `detect_legacy_data_dirs()`、不再打印"检测到旧位置"提示
- **`scripts/ys-agent.sh`**: 删除 `migrate-data-path` 子命令 + help 行 + usage 注释
- **`packaging/launcher.py`**: 注释去掉迁移相关说明

### 净减

- `agent/utils.py` 247 行 → 47 行 (-200 行)
- `scripts/ys-agent.sh` 少 1 个子命令分支
- 启动更快(无旧位置检测)
- 启动日志更干净(无警告)

### 不变

- 38 个 FastAPI 路由、9 个 LLM provider、3 个内置 extension、18 个内置工具
- `YS_DATA_DIR` 仍然最高优先级(覆盖默认值,便于测试/多实例)
- `~/.ys-agent/data/` 仍然是默认数据目录
- pytest 41/41 仍通过、ruff check 0 errors、smoke test 正常

## v1.4.0 — 2026-07-10 (数据目录统一: ~/.ys-agent/data)

**架构简化**: 把 5 级数据目录 fallback 砍到 2 级。源码启动和 .app 启动都使用 `~/.ys-agent/data/`,行为完全一致。

### 改动

- **数据目录唯一化**：`agent/utils.py` 的 `_resolve_data_dir()` 从 5 级 fallback (`YS_DATA_DIR` > `.app 旁边 data/` > `Resources/data/` > `~/YS-Agent/data/` > `~/.ys-agent/data/`) 砍到 2 级 (`YS_DATA_DIR` > `~/.ys-agent/data/`)。源码与 .app 不再有"看起来数据丢了"的问题
- **自动迁移**：`agent/utils.py` 新增 `_maybe_migrate_from_legacy()`,首次启动时若新位置完全为空 + 旧位置有数据,自动复制并写 `.migrated` 标记,跳过重复迁移。**不擅自覆盖任何已存在数据**——若新位置已有内容,启动时打印提示让用户显式运行 `ys-agent migrate-data-path` 合并
- **`ys-agent migrate-data-path` CLI**:`scripts/ys-agent.sh` 新增子命令,自动发现旧位置并迁移,支持 `--merge` 追加模式(同名词不覆盖,跳过的项备份到 `backups/merge-skipped-<ts>/`)
- **启动信息透明**:`backend/main.py` 每次启动在 stderr 打印 `[YS-Agent] Data directory: <路径>`,若检测到旧位置有数据则提示如何合并,消除"我设置到底存哪了"的不确定性
- **`mcp_server/ys_mcp_server/utils.py`** 复用 `agent.utils.DATA_DIR`,避免与主进程使用不同路径读 `config.json`(之前在 `.app` 模式下可能读到空配置)
- **`.app` 启动器简化**:`scripts/build-app.sh` 的 macOS launcher 去掉多级探测逻辑,只显示 `~/.ys-agent/data (源码与 .app 共享)`

### 顺手修

- **`MetricsCollector._Stub` 构造失败 bug**:`agent/core/metrics.py` 的 `_Stub` 没写 `__init__`,Python 3 默认 object 构造拒绝任何参数,导致 `prometheus_client` 未装时 `MetricsCollector()` 抛 `TypeError`,`MonitoringExtension` 注册失败,`/api/extensions` 列表里看不到 monitoring/security-event。补 `def __init__(self, *_args, **_kwargs): pass` 后 3 个内置 extension 全部正常注册
- **缺失依赖补全**:`.venv` 里没装 `prometheus_client` (虽然 `requirements.txt` 列了),补装 `prometheus_client>=0.21.0`
- **测试 41/41 通过**: 之前 `test_api_extensions.py` 有 2 failed + 1 error,根因即上面 `_Stub` bug,顺带修好

### 迁移说明 (v1.3.x → v1.4.0)

旧版本在 `.app` 模式下会把数据存到 `~/.ys-agent/data/`,在源码模式下存到 `<项目>/data/`,两边数据可能分散。

**首次启动 v1.4.0 时**:
- 若 `~/.ys-agent/data/` 为空 + 项目 `data/` 有数据 → 自动迁移,启动日志里会写 "已从旧位置自动迁移数据"
- 若 `~/.ys-agent/data/` 已有数据 + 项目 `data/` 还有数据 → 不会自动迁移,启动时打印警告,运行 `ys-agent migrate-data-path --merge` 合并
- 若你之前用 `YS_DATA_DIR` 环境变量覆盖路径 → 仍然有效,优先级最高

迁移前的旧数据会先完整备份到 `~/.ys-agent/data/backups/migration-<timestamp>-from-<旧名>/`,可手动回滚。

### 未变

- 38 个 FastAPI 路由、9 个 LLM provider、3 个内置 extension、18 个内置工具、11 个 YonSuite MCP、27 个 chart MCP、Extension 系统、Phase 状态机、记忆/会话/技能系统、前端结构

## v1.3.3 — 2026-07-08 (hotfix: .app 看不到项目数据)
## v1.3.3 — 2026-07-08 (hotfix: .app 看不到项目数据)

- **修复 .app 数据目录智能解析**：`packaging/launcher.py` 和 `backend/main.py` 不再强制 `YS_DATA_DIR=~/.ys-agent/data/`，改由 `agent/utils.py` 的 `_resolve_data_dir()` 智能解析。优先级：`YS_DATA_DIR` 环境变量 > .app 旁边的项目 data/ (sibling of dist/) > `~/YS-Agent/data/` > `~/.ys-agent/data/` (默认)
- **.app 启动信息按路径动态显示**：`scripts/build-app.sh` 启动器从写死 `~/.ys-agent/data/` 改为按 `.app` 位置探测真实数据目录

**实测：** .app 在 `dist/YS-Agent.app/` 启动后，`/api/sessions` 现在显示项目里的 111 个 session（v1.3.2 只显示 `~/.ys-agent/data/` 里的 4 个老 test session）。

**这是 v1.3.2 的关键 bug** —— 如果用户从源码模式（用项目 data/）切到 .app 模式，.app 会落到空的 `~/.ys-agent/data/`，看起来"数据丢了"。强烈建议 v1.3.2 用户升级到此版本。

**未变：** 18 个内置工具、.app 体积 73M、所有 v1.3.2 改进（Mac 安装加固、playwright 移除、anthropic 依赖）。

## v1.3.2 — 2026-07-08 (.app 体积优化 199M → 73M + 启动修复)

- **.app 真正自包含**：移除 `playwright` 依赖（之前打包了 127MB 的浏览器自动化库，但 v1.3.1 已经移除了 `browser_tool.py` 没人用了）。`packaging/ys-agent.spec` 把 `playwright` / `playwright.sync_api` / `playwright._impl` 加进 `excludes`；`scripts/build-app.sh` 的 chart MCP 预缓存段措辞改为"可选"
- **.app 不再隐式依赖 Node.js**：`backend/main.py` 的 chart MCP 注入在 `frozen` 模式下静默跳过（之前是 warning，会让 .app 用户疑惑）。开发模式保留 warning（缺 npx 是异常）
- **修复 _get_version 在 frozen 模式下返回 `"unknown"`**：`backend/main.py` 的 import 位置错误（之前 inline 在 `app = FastAPI(...)` 上面，触发 `NameError` 导致 .app 启动崩）；`backend/api/system_api.py` 加 `import sys` 并读 `sys._MEIPASS` 路径；`packaging/ys-agent.spec` 把 `VERSION` 文件以 3-tuple 形式打进 `datas`
- **yonsuite skill 软化**："必须使用 @antv/mcp-server-chart" 改为 "优先使用, 无则 matplotlib/ECharts 兜底"，避免 .app 用户（无 Node.js）撞强依赖
- **Mac 安装体验加固**：`setup.sh` 在 macOS 上新增 Homebrew（可选提示）和 Xcode Command Line Tools（强失败，pip 装包需要）检测；brew 警告改为"可选"措辞，给出 python.org / nodejs.org 手动安装路径
- **依赖补全**：`requirements.txt` / `pyproject.toml` 新增 `anthropic>=0.40.0`（v1.3.1 漏了）

**实测：** `dist/YS-Agent.app` 从 199M 降到 73M（-63%），双击启动 HTTP 200，`/api/health` 返回 `version: "1.3.2"`，无需系统装 Python / Node / Xcode CLT。

**未变：** 18 个内置工具、11 个 YonSuite MCP、9 个 LLM provider、Extension 系统、Phase 状态机、记忆/会话/技能系统。

**迁移说明：** 从 v1.3.1 升级只需 `ys-agent update`，会自动用新镜像回退链重装 Python 依赖；.app 用户下载新 .app 替换即可。

## v1.3.1 — 2026-07-08 (安装脚本加固 + 浏览器工具改 MCP 化)

- **移除内置 browser 工具集**：`agent/tools/browser_tool.py` 删除（649 行）。`playwright` 不再是 YS-Agent 的运行时依赖，少装 ~500MB 浏览器二进制。需要浏览器自动化的用户，可在前端 MCP 管理页添加官方 `@playwright/mcp`（`npx -y @playwright/mcp@latest`）。`web/src/pages/ToolsPage.tsx` 同步移除 `browser` 工具集 emoji 映射
- **依赖补全**：`requirements.txt` / `pyproject.toml` 新增 `anthropic>=0.40.0`（Anthropic provider 的 SDK，之前缺失导致选 Anthropic 时需要手动 `pip install anthropic`）
- **setup.sh / setup.bat 加固**：
  - PyPI 镜像回退链（清华 → 阿里云 → 腾讯云 → PyPI 官方），单镜像挂掉自动切下一个；`--retries 1 --timeout 15` 快速失败，单镜像失败 ~3s 而不是 30s+
  - venv 创建后立即验证 `pip --version`（Debian/Ubuntu 上 `python3-venv` 缺失时 venv 会建成功但 pip 找不到，原版要到 `[4/8]` 才暴露错误）
  - venv 创建失败时按 OS 给具体修复指引（`apt install python3-venv` / `brew install python` / Windows 勾选 pip）
  - `pip install` 错误现在直接打到终端（移除 `-q 2>/dev/null` 静默吞错）
  - 装完最后跑 `pip check` 验证依赖图一致性
- **update.sh 同步加固**：升级时也用镜像回退链（之前只用单清华源，海外/挂掉时升级会卡住），加 `pip check`，npm install 加 `--no-audit --no-fund`
- **工具数 27 → 18**：去掉 9 个 `browser_*` 工具（`browser_navigate` / `browser_snapshot` / `browser_click` / `browser_type` / `browser_scroll` / `browser_back` / `browser_press` / `browser_get_images` / `browser_console`）。其余 18 个内置工具 + 11 个 YonSuite MCP 查询 + 27 个 chart MCP 查询保持不变

**未变：** 30 个 FastAPI 路由、9 个 LLM provider、Extension 系统、Phase 状态机、记忆/会话/技能系统、YonSuite 业务工具、前端结构。

**迁移说明：** 升级到 v1.3.1 后，已有的浏览器工具调用历史/记忆里的"用 browser_navigate..."描述会失效。LLM 会自动改用 `web_extract` 或提示用户装 `@playwright/mcp`。无数据迁移需要。

## v1.3.0 — 2026-07-04 (架构优化：Pydantic 配置 + Phase 枚举 + 插件发现)

- **Pydantic 配置化**：`agent/config_model.py` 新增 `AppConfig` 模型，`config_manager` 返回/写入类型安全的 Pydantic 对象而非裸 `dict`；加密字段自动处理；所有调用点（`config_api.py` / `chat.py` / `mcp_api.py` / `mcp_manager.py` / `agent.py` / `slash_commands.py` / `extensions_api.py` / `main.py`）改为属性访问
- **运行时状态机规范化**：`AgentPhase` 类 → `Phase` 枚举（`str` 子类，向后兼容）；新增 `Envelope` 数据类 `(seq, phase, payload_type, payload)` 为 SSE 提供状态追踪
- **插件系统动态化**：`agent/plugin_system/` 新增，支持 `[project.entry-points."ys-agent.extensions"]` 入口点发现 + `data/plugins/*.py` 目录扫描；`agent/extensions/__init__.py` 自动集成到注册流程
- **Windows 兼容**：`terminal_tool.py` 跨平台 shell 检测（cmd/powershell/bash）+ `taskkill` 替代 `os.killpg`；`context_compactor.py` 路径正则新增 `C:\...` Windows 格式；PDF skill 脚本 `--break-system-packages` 仅 Linux 平台使用
- **前端修复**：`McpPage.tsx` TS 类型错误（`mcpServers` 属性访问）和 `SettingsYSPage.tsx` TS 类型错误（`undefined` 处理）修复
- **后端清理**：FastAPI `on_event` → `lifespan` 上下文管理器；`agent/skills/*` E402 放行；测试文件同步适配 Pydantic
- **ruff 0 errors / pytest 41 passed / tsc 0 errors**

## v1.2.0 — 2026-07-04 (CLI 命令标准化)
- **未知命令拦截**：不匹配的子命令直接报错退出，不再默认落到启动服务
- **命令格式统一**：`--stop` → `stop`，字段说明统一为动词子命令格式（参考 git/docker 惯例）
- **精简帮助**：移除 `--help` 中的环境变量说明（配置统一走 `.env` 文件）
- **安装脚本清理**：`setup.sh` 安装 `ys-agent` CLI 到 `~/.local/bin/` 后，不再需要 `.zshrc` 中的 alias

## v1.2.1 — 2026-07-01 (内存模块修复：事实记忆注入 + list 操作 + 并发锁 + 上限)

- **修复事实记忆不注入的 bug**：`chat.py` 手动拼接 `system_message` 后传递给 `run_conversation`，覆盖了内部 `build_system_prompt` 对 `memory_store` 的调用；导致 `memory` 和 `user` 条目从未出现在系统提示中，LLM 在盲写记忆。现改用 `build_system_prompt(memory_store=fact_memory.init_store(), ...)` 统一构建
- **新增 `list` 操作**：`memory_tool` 的 `action` 枚举新增 `list`，LLM 可以 `memory list target=memory` 列出当前条目，不再盲写
- **新增 `MemoryStore.list_entries()`**：返回快照副本供 LLM 读取
- **`memory_manager.py` 添加文件锁**：`store_conversation_summary` 和 `clear_all` 现在使用 `fcntl.flock` 互斥，防止并发会话覆盖彼此的摘要
- **对话摘要上限**：`memory.json` 的 `conversations` 列表最多保留最近 **100 条**，超过时自动淘汰最旧的条目，避免无限增长
- **memory_tool 描述更新**：文档中增加了 `list` 操作说明

## v1.2 — 2026-07-01 (可观测性：Prometheus 指标 + 增强 Health)

新增监控系统，覆盖 agent 运行全生命周期的可观测性数据。

- **指标收集**：`agent/core/metrics.py` 新增，基于 `prometheus_client`；Counter/Gauge/Histogram 共 12 个指标（会话数、LLM 耗时/Tokens/重试、工具耗时、错误计数、MCP 连接数、内存操作、压缩节省 Tokens）
- **监控 Extension**：`agent/extensions/monitoring.py` 新增，通过 M2 事件总线实时记录指标；自动启用以实现零配置可观测性
- **Prometheus 端点**：`backend/api/metrics_api.py` 新增，`GET /api/metrics` 返回 Prometheus text exposition 格式
- **增强 Health**：`GET /api/health` 从简单的 `{"status": "ok"}` 升级为包含 `uptime_seconds`、`version`、`mcp_servers_connected` 的详情
- **新依赖**：`prometheus-client>=0.21.0` 添加到 requirements.txt
- **优雅降级**：`prometheus_client` 未安装时 MetricsCollector 和监控 Extension 均为 no-op，不阻塞启动

修复项目目录变更后 pre-commit 钩子失效的问题，并把钩子纳入仓库管理以便跨机器复用。

- **修复钩子路径**：`.atomcode/settings.json` 的 `pytestRun.working_directory`、`agent/context_compactor.py` 的路径正则，从旧路径 `/Users/zuoxiaojun/claudeproject/YS-Agent` 更新到当前实际路径
- **新增 `.githooks/pre-commit`**：仓库内置的钩子入口；使用 `git rev-parse --show-toplevel` 解析仓库根，**不硬编码绝对路径**，跨机器/重命名项目目录都能直接使用；优先调用项目 `.venv` 里的 pre-commit，回退到 PATH 中的 `pre-commit`
- **pre-commit 离线可用**：`.pre-commit-config.yaml` 中 ruff / ruff-format 改用 `language: system`，复用项目 `.venv` 里的 ruff (`v0.15.17`，与 venv 一致)，无需联网即可工作；其他内置钩子（trailing-whitespace / end-of-file-fixer / check-yaml / check-toml / check-added-large-files / check-merge-conflict / detect-private-key）首次运行后缓存到 `~/.cache/pre-commit/`
- **清理**：删除 `.git/hooks/pre-commit` 旧钩子（其硬编码了旧绝对路径，自 `core.hooksPath` 指向 `.githooks/` 后已不再触发）
- **文档**：README 新增「开发工作流」小节，说明首次克隆后的初始化步骤与配置要点

**未变：** 全部 30 个 FastAPI 路由、26 个内置工具、9 个 LLM provider、Extension 系统、pytest 套件 36 tests、MCP server、skill 系统、YonSuite 业务工具、前端无任何改动。

**启用方法**（已在新克隆的机器上自动提示）：

```bash
pip install pre-commit
git config core.hooksPath .githooks
```

## v1.1.1 — 2026-06-02 (M5+ Extension 配置化)
## v1.1.1 — 2026-06-02 (M5+ Extension 配置化)

承接 v1.1 重构，让用户在 Web UI 上启用/停用 M2 事件系统的 extension（之前需要改 Python 源码）。

- **后端 API**：`backend/api/extensions_api.py` + `backend/schemas/extension.py` 新增；4 个端点（`GET /api/extensions`、`GET /api/extensions/active`、`PUT /api/extensions/{name}/toggle`、`POST /api/extensions/reload`）；状态持久化到 `config.json` 的 `disabled_extensions` 字段
- **内置扩展注册**：`agent/extensions/{__init__,log_everything,security_event}.py` 新增；`agent/agent.py` import 时自动调用 `register_built_in_extensions()`；启动时自动 apply 持久化的 disabled 列表
- **事件系统 API 扩展**：`agent/events/extensions.py` 加 `list_all_extensions` / `list_active_extensions` / `apply_config_overrides`；`register_extensions` 现在跟踪所有注册过的 instance（即使 disabled），方便 runtime toggle
- **安全冗余**：`SecurityEventExtension`（事件层）和 `agent/tools/security_hooks.py`（registry 层）并行工作，互为备份；M6+ 计划合并
- **前端**：`web/src/pages/SettingsExtensionsPage.tsx` 新增（参考 SkillManagerPage 的卡片 + ToggleRight/ToggleLeft 风格）；`App.tsx` +1 路由 `/settings/extensions`；`Sidebar.tsx` +1 入口（"扩展管理"，Boxes 图标）
- **真实冒烟**：后端 8 个 HTTP 端点全过；runtime toggle 真生效（disabled 后事件层不再 cancel，registry 层兜底）；前端 `vite build` 通过（2014 modules），新代码 0 个 tsc 错
- **pytest 套件落地**：`tests/` 36 个 test，0.47s 全过；覆盖 8 事件类型字段、Extension 注册/取消/双向 toggle、ToolRegistry + Hook 链（block/modify args/after-hook 改 result）、config_manager load/save round-trip、`compact_messages` 事件钩子（含 extension 改 summary 的端到端）、AIAgent `run_conversation` 5 个真实 turn、FastAPI 4 个 M5+ 端点 + health check。fixture 设计：autouse `clean_extensions` 隔离事件总线，`isolated_config` 重定向 `data/config.json` 到 tmp_path 不污染真 config。**未引入新依赖**（pytest 9.0.3 已有）

**未变：** 30 个 FastAPI 路由、26 个内置工具、YonSuite 业务工具、MCP server、skill 系统。

**回归测试注意事项：** M1 时代遗留 4 个 tsc 错（`McpPage.tsx` 1 个 `useRef` 未用 + 3 个 `mcpServers` 属性缺失；`SettingsYSPage.tsx` 1 个 `string | undefined`）。这些错**不在本次 M5+ 范围**，Karpathy 原则 3 不应顺手改。它们阻塞 `npm run build`（严格 tsc）但不影响 `npm run dev` 和 `vite build`（仅 transpile）。建议作为 M5.1/技术债单独处理。

## v1.1 — 2026-06-02 (M1+M2+M3+M4 重构)

架构升级，借鉴 Pi (earendil-works/pi) 的设计：

- **M1 分层**：`agent/agent.py` (481 行) 拆为 `agent/core/{agent,message_builder,llm_client,tool_dispatcher,iteration_budget}.py`；`agent/agent.py` 缩到 12 行 re-export，向后兼容
- **M2 事件系统**：`agent/events/{bus,types,extensions}.py` 新增；8 个事件类（session_start/end、user_message、before/after_llm_call、before/after_tool_call、session_before_compact）；Extension 基类 + Runner；typed handler 自动订阅
- **M3 LLM Provider 抽象**：`agent/core/llm_providers/{base,openai_compat,anthropic,factory}.py` 新增；`LLMClient` 变成薄壳委托给 `LLMProvider`；9 个 OpenAI-compat provider + Anthropic 原生 provider；`backend/llm_providers.py` 加 `protocol` 字段
- **M4 压缩增强**：`compact_messages` 改吃 `summary_caller` (不再依赖 OpenAI client)；新增文件追踪 (限 5 个/8KB，拒 /etc /System 等)；`SessionBeforeCompactEvent` 钩子，extension 可写 `event.extra` 追加到 summary
- **手测冒烟 10 项全部通过**（见 `docs/architecture.md`）
- 新增 `docs/architecture.md`（架构说明）+ `docs/extending-ys-agent.md`（Extension 开发指南）

**未变：** 30 个 FastAPI 路由、26 个内置工具、前端、YonSuite 业务工具、MCP server、skill 系统、security_hooks 老钩子（仍工作，与事件钩子并存）。

**M5 未做：** 树形会话 / TUI / 完整 Pydantic 化 / pytest 套件 / 任意时刻 session 快照 / `BaiduQianfanProvider` 实现。

## v1.0 — 2026-05-17

- FastAPI + React (Vite) 架构，替换原 Streamlit
- WebSocket 流式聊天，支持工具调用实时可见
- 36 个内置工具（终端、文件、网页、浏览器、YonSuite 等 10 个工具集）
- YonSuite 10 个高级查询工具（销售/采购/生产订单、库存、待办、商机等）
- 技能管理系统：安装、激活、停用、删除
- Agent 自主记忆系统（笔记 + 用户画像）
- 对话摘要自动生成 + FTS5 全文搜索
- 前端页面：聊天、内置工具、技能管理、记忆管理、历史会话
- 搜索过滤：工具、技能按名称/描述搜索
- 端口统一通过 .env 管理
