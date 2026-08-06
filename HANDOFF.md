# HANDOFF — v1.9.0 维护发布已完成（2026-08-06）

> 供新 opencode 会话快速接续。所有工作已提交并推送，无未保存改动。

## 当前状态

- 分支：`main`，与 `origin/main`（atomgit）同步，HEAD = `23296ca`
- Tag：`v1.9.0` → `23296ca`（已 force-push 到 atomgit；先打在 b106717，后因最终文档修复移动）
- 版本：v1.9.0（`pyproject.toml` 为版本唯一事实源）
- 测试：**509 passed**（基准 501 + 8 新增），`ruff check .` clean，前端 `npm run build` + `npm run lint` 全绿
- 工作区干净，无未提交改动

## 本次会话完成的事

**主线：v1.9.0 维护发布**（承接上一会话 Pi 内核重写，spec/plan 见 §关键文档）。用户确认：单 spec 单 plan、先代码后发布、直接在 main 上执行。18 个功能 commit（`756854e` → `23296ca`）。

**A 组 — parked minors 清理（每个配测试）：**
1. **M-1 审批拒绝卡片**：`ToolExecutionEnd` 加 `denied` 字段 → `_HandlerResult` → WS `tool_result.denied`（仅 true 时附加）→ 前端 `_denied` 标记 → ToolStepCard 显示"已拒绝"（`tool-step-denied` 类）
2. **M-2 取消持久化**：`_partial_response` 累积 + 每轮重置 + 去重守卫（评审发现真实缺陷后追加修复）；`_final_response` 保持空 → WS/UI 零变化
3. **M-3 桥工具卡片**：`effectiveArgs` 回退链 + `extractSubtitle` 补 tool_search/tool_describe/tool_call case
4. **M-5 压缩 session_id**：`_transform_context_hook` 两处 `_set_phase` 补 `session_id`
5. **M-6 Agent 复用**：`run_async` 采纳新 token / 取消后重置 + `subscribe` 幂等
6. **M-7 死代码**：删除同步 `dispatch_tool` + `sys` import + re-export（零引用已核实）

**B 组 — TAVILY key 运行时加载（用户拍板：不打包）：**
- `backend/config.py` `load_dotenv` → `_load_env_files()` 候选列表：`~/.zlink-agent/.env`（`DATA_DIR.parent`）优先，仓库根 `.env` 次之，`override=False`
- **key 已由用户提供并写入 `~/.zlink-agent/.env`**（chmod 600，dev 验证注入成功）；打包版启动即读，无需重打包
- `build-pyinstaller.sh` / `main.js` / `backend_launcher.py` 零改动

**C 组 — 前端优化（168 处内联样式 → 42 处）：**
1. **C-1 宽屏**：`.page-container` 1040→1280px；列表页 `.card-grid`（History/Memory/Tools）；配置页 `.form-grid-2`（LLM/Agent/ERP）；CronJobPage（表格）与 SkillManager/SettingsExtensions（已有 skill-grid）明确不套网格
2. **C-2 内联样式收敛 3 批**：65 个工具类集中在 global.css 末尾（`/* ── Utility classes (C-2: inline-style consolidation) ── */`）；McpPage 51 处（45 迁 6 留）→ SkillManager/Memory/SettingsAgent（45 迁 11 留）→ 剩余 11 文件（35 迁 21 留）；动态样式保留 inline 并注 `// dynamic:`
3. **C-3 颜色**：ERP 测试结果条 → `.test-result-ok/error`（`var(--success)`/`var(--danger)`，删 `#B7EB8F`/`#FFA39E`）
4. **C-4 历史页**：hash 徽章 → `.badge-neutral`（保留 6 位 ID）+ 删除 `window.confirm`

**D 组 — 发布 v1.9.0**：pyproject/package.json/CHANGELOG/README 四件套 + tag。

## 关键决策与原因

- **直接在 main 上执行**：项目惯例（HANDOFF/HANDOVER 均如此），用户确认
- **M-2 去重守卫追加**：评审确认真实缺陷（真实流式路径下工具执行期取消会重复追加 partial 气泡），用户拍板追加 per-turn reset + last-message 比对守卫
- **M-3 subtitle 增强纳入**：用户拍板（参数为空时卡片不整卡空白）
- **C-4 hash 中性灰保留**：用户拍板（保留排障用途）
- **B 组运行时读取而非打包嵌入**：用户拍板（避免 dmg 提取 key）；`override=False` 保证环境变量优先
- **M-6 可复用语义**：用户拍板（显式 token 始终采纳 + 取消后重置）
- **MCP tooltip 跳过**：核实 McpPage 所有图标已有 title，HANDOVER 此项过时

## 改动文件（按模块）

- `agent/core/`：kernel_types（denied 字段）、tool_dispatcher（_HandlerResult/删 dispatch_tool）、agent_adapter（M-2/M-5）、agent（M-6）、`__init__.py`（删 re-export）
- `backend/`：config.py（_load_env_files）、api/chat.py（tool_result.denied）
- `web/src/`：types/useChat/AppContext/ToolStepCard（M-1/M-3）、global.css（denied 类/工具类/布局/颜色/badge）、8 个页面（C-1/C-2/C-3/C-4）
- `tests/`：+8（M-1×2、M-2×2、M-5、M-6×3、B×2 分布）
- 版本四件套：pyproject/package.json/CHANGELOG/README

## 验证命令与结果（实测）

```bash
.venv/bin/python -m pytest tests/ -q   # 509 passed, 1 warning, 7.75s
ruff check .                            # All checks passed
cd web && npm run build && npm run lint # 全绿（仅 pre-existing chunk>500kB warning）
```

## 已知问题 / 注意事项

- **打包版验证未做**：dev 已验证 key 注入成功；打包版 `web_search` 命中 Tavily 需实际打包后人工确认（本会话未跑 build-pyinstaller.sh）
- `HANDOFF.md` 已覆盖：本文件取代上一会话的 Pi 内核重写交接（其内容仍可从 git log 追溯）
- 仓库 `.env` 仅端口配置（key 在 `~/.zlink-agent/.env`，两处均 gitignored）
- 全程四个冻结契约零破坏（contract_freeze 7/7）：run_conversation 6-key dict、WS 消息（仅新增可选 denied）、EventBus 8 事件、registry 接口

## 遗留事项（不阻塞，按优先级）

1. **打包版验证**：`bash scripts/build-pyinstaller.sh` + 打包版 `web_search` 走 Tavily 档
2. 观察线上使用，无回归后清理 parked minors 残留文档引用（HANDOFF.md 已更新、AGENTS.md 已修）
3. 可选：`package-lock.json` 根 version 字段仍 1.7.0（过时，不影响构建）

## 新会话启动提示词

```
Read HANDOFF.md 和 AGENTS.md。当前 main 与 origin 同步，v1.9.0 已发布（509 tests 全绿）。
上次会话完成了 v1.9.0 维护发布（parked minors + TAVILY .env + 前端优化）。
本次任务：<在这里填你的任务>
```

第一个动作：`git log --oneline -5` 确认提交历史与上文一致。
