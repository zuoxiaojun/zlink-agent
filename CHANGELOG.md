# Changelog
## v1.2.0 — 2026-07-04 (CLI 命令标准化)

- **命令兼容性修复**：`version*|--version*` 前缀匹配替代精确匹配，`versionb` 等手误不再误启动服务
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
