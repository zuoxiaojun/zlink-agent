# HANDOFF — Pi 风格内核重写已合并上线（2026-08-06）

> 供新 opencode 会话快速接续。所有工作已提交并推送，无未保存改动。

## 当前状态

- 分支：`main`，与 `origin/main`（atomgit）同步，HEAD = `1671a13`
- 测试：**501 passed**，`ruff check .` 全绿
- 版本：pyproject 仍为 1.8.1（**本次重写未 bump 版本**）
- dev 服务可能仍在跑（:8089/:8088），`./start.sh stop` 可停

## 本次会话完成的事

**主线：借鉴 Pi（~/vibecoding/agent-frameworks/pi）架构，Python 原生重写 agent 内核**（merge commit `1671a13`，43 文件 +5128/−1159）：

- 新内核 `agent/core/`：`kernel_types.py`（10 种 AgentEvent + AgentLoopConfig 钩子 + CancelToken）、`loop.py`（零策略双层 async loop，AgentEnd 保证收尾）、`agent.py`（有状态 Agent：subscribe/steer/cancel/wait_idle）、`agent_adapter.py`（AIAgent 兼容层 + EventBus 8 事件映射 + Phase 机）
- 并行工具执行：prepare 串行（安全 hook 无竞态）→ gather 并发 → 保序；批次含 sequential 工具整批降级；25 个写工具已标 sequential（`registry.register(..., execution_mode=)`）
- `finish_reason→stop_reason` 映射补全（openai_compat/anthropic）+ `stop_reason=="length"` 截断防护（截断消息的工具调用拒绝执行）
- CancelToken 全链路 + steering 队列（WS `{"type":"steering","payload":{"content"}}`）+ 前端生成中可发消息（`useChat.steerMessage`）
- 旧内核与 ZLINK_KERNEL 开关已删除（P4 完成，无回退开关）

**附带修复/特性**：glob 根目录护栏（`file_tools._is_root_scope`）、`web_search` provider 降级链（SEARCH_API_URL → Tavily → Brave → DDG 末档，错误分类降级，聚合报错）、`start.sh` 不再自动开浏览器。

**真机冒烟抓到并已修的关键 bug**：assistant 消息未进 loop context 导致工具结果孤儿 → DeepSeek 400（`d93d7a4`，已补回归测试）；审批通过的 handler 与 `_generate_summary` 阻塞事件循环（`d27216c`）。

## 关键文档

- Spec：`docs/superpowers/specs/2026-08-06-pi-style-kernel-design.md`
- 计划：`docs/superpowers/plans/2026-08-06-pi-style-kernel.md`（P1–P4 全部执行完毕）
- 架构说明：`AGENTS.md` §2/§3/§4 已更新为新内核结构

## 验证命令

```bash
.venv/bin/python -m pytest tests/ -q   # 501 passed
ruff check .                            # clean
./start.sh --dev                        # 后端 :8089 + Vite :8088（不再自动开浏览器）
```

## 遗留事项（parked minors，均不阻塞）

1. 被拦截（block/拒绝）工具不再下发 WS tool 卡片（最终评审 M-1）
2. 取消时会话持久化丢失部分 transcript（M-2，仅影响持久化，不影响 UI）
3. 截断工具的 WS 卡片 args 显示为空（M-3，纯展示）
4. 压缩 PhaseChange 的 session_id 为空串（M-5，与旧内核行为一致）
5. `Agent` 复用 footgun：cancelled 后忽略新 token、AIAgent 重复 subscribe（M-6，latent，chat.py 每次新建实例故无实际影响）
6. 同步 `dispatch_tool` 已成生产死代码（M-7，下个清理窗口可删）
7. opencode 全局配置已改 `permission: allow`（`~/.config/opencode/opencode.jsonc`），**需重启 opencode 生效**
8. `TAVILY_API_KEY` 只在 shell 环境，未写入 `.env`——Electron 打包版不继承 shell env，建议写入 `.env`

## 下一步建议（按优先级）

1. **版本发布**：本次改动量够 minor 版本（1.9.0）——bump pyproject + package.json + CHANGELOG + README + tag（流程见 AGENTS.md §10）
2. 观察线上使用一周，确认无回归后清理 parked minors（尤其 M-1/M-2）
3. 可选：`TAVILY_API_KEY` 写入 `.env`；Settings UI 加"搜索配置"卡片

## 新会话启动提示词

```
Read HANDOFF.md 和 AGENTS.md。上次会话完成了 Pi 风格内核重写（已合并 main，501 测试全绿）。
本次任务：<在这里填你的任务>
```
