# HANDOVER

> 2026-09-02 会话交接。状态：**v1.13.2 已提交、已推 origin、已打 tag、macOS 安装包已构建并按偏好只留当前版本**。
> 本轮三件事：单会话执行约束、会话视图串台修复（含切回重放）、打包版 node 可达性。

## 当前状态

- `main` @ `3df8845`，版本 **1.13.2**（`pyproject.toml` 单一来源 + 根 `package.json` 同步，`_get_version()` 实测读到 1.13.2）
- tag `v1.13.2` 已推（peel 到 `3df8845`）；本轮推送区间 `1be7a6d..3df8845`，远端 hooks 两批 `[PASSED]`；origin = `gitcode.com:gcw_cJbJuamU/zlink-agent.git`（AtomGit 现行域名）
- 安装包：`dist-electron/ZLink Agent-1.13.2-arm64.dmg`（174M，arm64，ad-hoc 本地签名）。挂载卷上 `codesign --verify --deep --strict` **exit 0**；`spctl` 预期 rejected（不是 damaged，用包内 `install.command` 清 quarantine 绕过）
- **历史包已按常设偏好清掉**（1.13.0 / 1.13.1 均不在，目录 352M → 176M），无 `.dmg.zip` 压缩副本残留
- ⚠️ `/Applications` 里装的那份是 **1.13.1，不含本轮 node 修复** —— 要验证 node 相关行为必须先覆盖安装 1.13.2
- 校验：`602 passed`（本轮 +11）· `ruff check` 干净 · `ruff format --check` 383 files 全清 · 前端 `tsc -b` / `eslint` / `vite build` 全绿（1.13.1 那轮验的，1.13.2 前端零改动）
- 服务：**全部停止**（8088 / 8089 无监听，无 vite / uvicorn 残留，DMG 卷已弹）

## 本会话产出

| commit | 内容 |
|---|---|
| `f5a0e56` | 会话执行中置灰「新建对话」（`disabled={state.agentRunning}` + tooltip），`.sidebar-new-btn` 的 hover/active 补 `:not(:disabled)` 防灰态被点亮 |
| `28e4cce` | **WS 帧按 session id 归属**：`AppAction` 新增 `SCOPED`（串台裁决收在 reducer，那里有权威的 `currentSessionId`）与 `ADD_MESSAGE`（相对动作）；`web/src/hooks/useChat.ts` 整体重写，连接按 sid 存进 `runsRef`，`stopAgent` / `sendApproval` / `steerMessage` 回到正确连接；`ChatPage` 审批卡片改按 sid 归属 |
| `632592c` | **切回正在执行的会话时重放本轮视图**：每条 run 用 `LiveRun` 记账（`recorded` 只放改 messages 的相对动作 + `tokenAll` / `reasoningAll` / `progress` / `toolName`），切回时 `attach()` 在刚从磁盘读回的历史上重放，进度条 / 停止按钮 / 本轮气泡 / 新建置灰一起接回，工具耗时原样保留 |
| `1be7a6d` | 版本 1.13.1 + CHANGELOG |
| `a7a12d0` | **打包版 node 可达性**：新增 `agent/node_env.py`（本机 node 优先探测 → 探不到落 Electron-as-node shim）+ `backend/main.py` lifespan 早期挂载 + `tests/test_node_env.py` 11 例 + AGENTS.md 同步 |
| `3df8845` | 版本 1.13.2 + CHANGELOG |

## 本轮最值钱的知识：打包版 node 为什么 127

根因链条：从 Finder / Dock 启动的 GUI 进程**不读 `~/.zshrc`、不读 `/etc/paths.d`** → 后端环境 `PATH=/usr/bin:/bin:/usr/sbin:/sbin`（实测 8089 上的打包后端进程 env）→ 本机 brew 的 `/opt/homebrew/bin/node` 不可见 → `terminal_tool.py:181` 是 `"env": os.environ`，原样继承 → 技能里 `node *.js` 一律 exit 127 → **模型把 127 误读成「本机没有安装 Node.js」**（会话 `aef60f42` 就是这么错的，84 条消息）。

- 预置的 node **没坏**：`ELECTRON_RUN_AS_NODE=1` + `ELECTRON_NODE_PATH`（Electron 二进制）实测可当 node 用（v24.18.1），此前只喂给了 chart MCP（`backend/main.py:167-176`），terminal 一点没继承
- 用户本机其实装着 node（brew v26.7.0；另有 pi-node v22.23.2）—— 所以修法必须**两条都要**：既补本机探测，也留包内兜底
- 受影响技能四个：`china-hotdata`（4 个脚本）/ `anysearch` CLI / `minimax-pdf` 的 `render_cover.js` / `pptx-generator`
- dev 模式从登录 shell 起，PATH 正常 → **这个洞只有打包版会撞**，所以长期没人发现
- 修复实证（不是静态检查）：`env -i` + 最小 PATH 直接跑 **DMG 里的冻结后端** → `/api/health` 返回 `version 1.13.2`，app.log 打出 `zlink.node_env: node 可达性：用本机 node /opt/homebrew/bin/node（目录已前置进 PATH）`，chart MCP 仍 `connected, 27 tools`（无回归）。注意 `_internal/` 里没有散装 `.py` 是正常的（模块进 PYZ，散装只有 datas）

## 关键决策记录

1. **放弃多会话并发改造，只支持单会话**（用户拍板「算了，回退吧，不折腾多会话了」）。执行中只堵「新建对话」按钮；从「历史对话」页点进另一个会话这条路径**没堵**，靠上面的 sid 归属保证不串台。
2. **串台裁决放 reducer 不放 hook**：`scoped(sid, action)` 包一层，由 reducer 用权威的 `state.currentSessionId` 决定生效与否 —— 不靠闭包猜、没有竞态窗口。附带原因：`react-hooks/refs` 禁止渲染期写 ref，所以 ref 只能影响 token flush 时机，正确性必须在 reducer。
3. **重放只录相对动作**（`ADD_MESSAGE` / `ADD_PENDING_TOOL` / `REPLACE_PENDING_TOOL`）：切回时消息列表是刚从磁盘读的全新历史，绝对式的 `SET_MESSAGES` 会把磁盘历史覆盖掉。
4. **node 可达性放后端启动统一补 PATH**，而不是往 terminal 塞特判 —— 一处生效给 terminal 与所有 MCP 子进程。顺序：PATH 已有 node 就完全不动 → 探本机真实 node（brew / `/usr/local/bin` / nvm·fnm 解析到最高版本 / volta / asdf / mise / pnpm / pi-node，Windows 加 `Program Files\nodejs`）→ 才落包内 shim。shim 每次启动重写（理由同 chart：app 被移动后旧路径会永久失效）。`ELECTRON_RUN_AS_NODE=1` **只活在 shim 脚本内部**，泄进本进程环境会让被 spawn 的 Electron 应用不开界面。
5. **明确不做：把技能目录绝对路径注入 prompt**（用户 2026-09-02 拍板「这个不用做」）。现状留着：`SKILL.md` 里写的是 `node agent/skills/<name>/scripts/x.js` 这种仓库相对路径，而终端 cwd 是会话产物目录，模型得自己找绝对路径（`aef60f42` 为此花了 60+ 条消息）。node 已可达，所以这条现在只是「绕路」不再是「卡死」。**若以后要重启此事**：改点在 `agent/skill_manager.py:162` 的拼装处（`"## {name}"` 标题下加一行技能目录），配套要在 `agent/tools/skills_tool.py` 暴露一个 `get_skill_dir(name)`（别改 `_get_skill_content` 签名，它有别的调用方）。
6. **打完包只留当前版本 dmg**（含 `.dmg.zip` 副本）—— 常设偏好，自动执行，不再征求确认。

## ⚠️ 环境侧（机器级）改动 —— 不在仓库里，换机器/重装会丢

1. **`~/.pi/agent/bin/python`（新增文件）** —— pi-lens 的 pytest runner 硬编码 `command:"python"`，本机只有 `python3` 和各项目 `.venv/bin/python`，每轮报 `spawn python ENOENT`。pi-lens 没有 python 路径配置项，所以补了项目感知包装（向上找 `.venv/bin/python` → `$VIRTUAL_ENV` → `python3`）。还原：`rm ~/.pi/agent/bin/python`
2. **刷新 editable 安装元数据** —— 本轮已重跑 `pip install -e . --no-deps --no-build-isolation`（新增顶层模块 `agent/node_env.py` 后必须做；此前元数据停在 1.13.0，会让 Pyright 对新建模块凭空报 unknown import）。现在元数据 = 1.13.2，从任意 cwd 都能 import。**以后每次新增 `agent/` 顶层模块，若 Pyright 报未知导入，先重跑这条**
3. **`.pi-lens.json`（已提交，仓库根）** —— 关掉 pi-lens 的 `autofix.enabled` 与 `format.enabled`（它此前反复自动改文件：吞过 CHANGELOG 标题、把 plan 重排 76 行、把 `web/src` 2 空格改成 4 空格）。项目级配置在会话启动时读取，**当轮不生效，下个会话起效**

## 遗留待办 & 已知问题

**本轮新发现，未修**

- [ ] **`./start.sh stop` 按端口杀进程，会瞄上已安装的客户端**：本轮实测它打印「端口 8089 已被占用，停止进程 PID 85863 85869」，那两个 PID 正是 `/Applications/ZLink Agent.app` 的 Electron helper 与打包 backend；之后那个客户端就不在了。建议护栏：只杀命令行含 `uvicorn` / `backend.main` 的 dev 进程，碰到 Electron 打包进程跳过并提示。（Electron 侧 `electron/port.js` 早就有这个意识 —— 它只杀命令行含 `zlink-backend` 的残留，外来进程弹窗报错；`start.sh` 没有）
- [ ] 打包版端到端还差一步：在**装了 1.13.2 的客户端里**真跑一次热搜技能（node 可达性已在冻结二进制上验证，但整条 agent 回合还没在客户端里走过）

**1.13.1 那轮自审如实保留的三条**

- `save_session` 到 `done` 帧之间有亚秒窗口，正好那一刻切回来会重复渲染一轮，刷新自愈；根治需后端在落盘前发 `done`（后端未动）
- 审批的 sid 归属代码写好了但**没实测**（那几轮没触发审批）
- 后台 run 继续跑时，当前空闲会话的「新建对话」不置灰 —— 不串台，但「只允许一条」没强制

**其它既有债（本轮读到、未动）**

- `session_manager` 保存索引是整表读改写，并发新建会话有丢更新窗口
- `agent_adapter.py` 里 `_session_usage` 赋值后没人读（`/cost` 恒空）
- `terminal_tool` 的后台进程表是模块级全局，跨会话可见
- 后端无鉴权，只靠绑 `127.0.0.1`（`ZLINK_AGENT_HOST` 可覆盖，绝不能放 0.0.0.0）
- 冻结模式 `GET /` 返回 404：`backend/main.py:294` 只在 `web/dist` 存在时挂 `StaticFiles`，而 Electron 走 `file://` 加载 `app.asar.unpacked/web/dist/index.html` —— 无害，非回归

**v1.1 功能候选（上一轮遗留，仍有效）**

- [ ] `sidebar_open` 工具：模型主动把产物推到本会话侧边栏（`external.jsonl` 已留接口位）
- [ ] 「本轮文件」分组：按消息流里的 `args.path` 匹配生成轮次，不落盘
- [ ] MCP 工具写出的文件目前既不归一也不登记（第三方 server 自管子进程 cwd）

**已知限制（设计时已接受）**

- `read_file` 等只读工具的相对路径也归一到产物目录，模型想看仓库里某文件必须给绝对路径
- 离线 / CDN 不可达时报告图表空白，靠「在浏览器打开」兜底；iframe 内部渲染失败无法从父页面探测
- 产物 >5MB 不内嵌文本预览；列表 >300 项截断；zip >200MB 返回 413

## 上一轮留档（v1.13.0 会话产物侧边栏）

细节不再复述，看 `docs/superpowers/specs/2026-09-01-session-artifacts-sidebar-design.md` + 同名 plan。仍然成立的结论：会话目录化 `<sid>/{session.json,artifacts/,external.jsonl}`；列表以**目录为真相**（实时扫盘，不用登记表）；**不用 `StaticFiles`**（会把含 ERP 数据的 `session.json` 暴露给本机任意页面）；路径归一在 before-hook、登记在 after-hook（`file_tools.py` 零改动）；sid 过 `is_valid_session_id()`（`^[A-Za-z0-9_-]{1,64}$`）挡住 `%2e%2e%2f` 穿越。更早一版的本文件全文见 `git show 3466a8f:HANDOVER.md`。

## 新会话入口

1. `git log --oneline -5` 确认在 `main` @ `3df8845`（v1.13.2）
2. 会话视图规则：`web/src/hooks/useChat.ts`（顶部有 `LiveRun` / `scoped` 说明）+ `web/src/context/AppContext.tsx` 的 `SCOPED` case
3. node 可达性：`agent/node_env.py` 的模块 docstring + `AGENTS.md` §13「打包版 node 可达性」
4. 打包：`bash scripts/build-electron.sh`（两阶段 ad-hoc 签名；打完按偏好清历史包）
5. 提醒：`/Applications` 那份还是 1.13.1，要验 node 修复先覆盖安装 1.13.2
