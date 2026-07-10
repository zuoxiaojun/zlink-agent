# Changelog
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
