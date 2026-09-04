# HANDOVER

> 2026-09-04 会话交接。状态：**macOS Intel(x86_64) 打包支持已加、已提交、已推 origin，两个架构的包都已实际打出并校验**。
> 本轮只做打包工具链与文档，**未动任何运行时代码**，所以版本号仍停在 **1.13.2**（未升版）。

## 当前状态

- `main` @ `595cec2`（与 `origin/main` 同步，远端 hooks `[PASSED]`），工作区干净
- 版本 **1.13.2** 未动：`pyproject.toml` + 根 `package.json` 都是 1.13.2。本轮是构建脚本能力，不是功能发布
- 安装包（两个架构都在）：
  - `dist-electron/ZLink Agent-1.13.2-arm64.dmg` 174M — Electron arm64 + 后端 arm64
  - `dist-electron/ZLink Agent-1.13.2-x64.dmg` 180M — Electron x86_64 + 后端 x86_64
  - 两者都是 ad-hoc 本地签名，挂载卷上 `codesign --verify --deep --strict` 通过；`spctl` 预期 rejected（非 damaged，包内 `install.command` 清 quarantine 绕过）
- 证据是**实际构建 + 冻结包运行**，不是静态检查：从挂载卷里直接跑 `Contents/Resources/zlink-backend/zlink-backend` → `/api/health` 返回 `{"status":"ok","version":"1.13.2","mcp_servers_connected":1}`，app.log 打出 chart MCP `connected, 27 tools`（x64 包）
- 本轮**没跑测试套件**（零 Python 运行时代码改动，`agent/`/`backend/`/`web/` 源码未动）；上一轮基线是 `602 passed` + ruff/format/tsc/eslint 全绿，仍成立
- 服务：无遗留。构建脚本的 PyInstaller 冒烟测试用 18089 端口、跑完即 kill；DMG 卷已全部弹出
- 新增构建用 venv `.venv-x64`（167M，仓库内但已 `.gitignore`，可随时 `rm -rf` 重建）

## 本会话产出

| commit | 内容 |
|---|---|
| `595cec2` | `feat:` 打包脚本支持 macOS Intel(x86_64)。5 文件 +88/−28：`scripts/build-electron.sh`（`--arm64`/`--x64` 架构参数、`--x64` 时 Rosetta + `python3.14-intel64` 自动建 `.venv-x64`、整脚本 `arch -x86_64 bash` 跑后端打包）· `scripts/build-pyinstaller.sh`（新增 `ZLINK_BUILD_VENV` 选 venv）· `electron-builder.yml`（mac.target 去固定 arch、加 `mac.artifactName` 带 arch 宏）· `AGENTS.md` §8/§10/§13 · `.gitignore` 忽略 `.venv-x64/` |

用法：`bash scripts/build-electron.sh --mac --x64`（Intel）/ 不传即默认 `--mac --arm64`。

## 本轮最值钱的知识：三个会让 Intel 包翻车的坑

都已写进 `AGENTS.md` §13「macOS Intel（x86_64）打包」，这里只留结论与因果：

1. **PyInstaller 不能跨架构** —— 后端必须真用 x86_64 解释器跑。本机 arm64 靠 Rosetta + python.org **框架版** Python 的 `-intel64` 切片。
   坑中坑：`python3.x-intel64 -m venv` 建出来的 venv，其 `bin/python` 指向框架的 **universal2** 解释器，裸跑会落到 arm64 切片、pip 装一堆 arm64 wheel 还全程"看起来成功"。必须每条命令都带 `arch -x86_64` 前缀，用 `platform.machine()` 验证（判据：venv 建好后 `file .venv-x64/bin/python` 会显示两切片，`arch -x86_64 ... -c platform.machine()` 才是 x86_64）。
2. **wheel 平台标签** —— 框架版 Python 的 `sysconfig.get_platform()` 报 `macosx-10.15-universal2`（而实机 macOS 是 26.6.2），于是 `macosx_11_0+` 的 x86_64 wheel 全被判不兼容、回退 sdist —— `cryptography` 最新版会当场拉起 rustup 下载 + Rust 源码编译（慢且易挂）。解法：装依赖时 `MACOSX_DEPLOYMENT_TARGET=14.0` + `--only-binary=:all:`，pip 自动落到**有 x86_64 wheel 的最高版本**。副作用：**x64 包 cryptography 48.0.1，arm64 包 50.0.0**（功能等价，见遗留第 3 条）。
3. **`electron-builder.yml` 的 mac.target 不要写 arch 列表** —— 架构只由 CLI `--x64`/`--arm64` 决定。曾把 arch 写成 `[arm64, x64]`，`--prepackaged` 阶段就按 config 把**两个架构的 DMG 都发出来**，用同一份 x64 后端伪装成 `-arm64.dmg`，把真正的 arm64 包直接覆盖掉（现场表现为「arm64 包里 `file` 出来是 x86_64」）。本轮 `--prepackaged` 之后补跑了 `--mac --arm64` 重建，才把 arm64 包修回正确架构。

## 关键决策记录

1. **每架构单独出一个 dmg，不做 universal** —— universal2 只 fat 化 Electron 外壳，PyInstaller 后端是 `extraResources` 里的单架构产物；「universal 壳 + 单架构后端」会打出能在一种芯片上静默坏掉的包，比两个明确命名的包更糟。
2. **产物名带 arch**（`mac.artifactName: ${productName}-${version}-${arch}.${ext}`）—— 原默认命名 x64 不带后缀，`-arm64.dmg` 和 `-1.13.2.dmg` 混在一起极易拿错包。
3. **不升版本号**（停 1.13.2）—— 应用行为零变化，两个包的版本都是 1.13.2，只是芯片不同。若要把 Intel 支持作为发布内容讲出去，需在 `CHANGELOG.md` 补一条再升版。
4. **`.venv-x64` 走 ignore 而非塞进 `build/python-bundle` 那套 relocate 逻辑** —— `scripts/build-pyinstaller.sh` 里那套 `install_name_tool`/`/opt/homebrew` 重定位是给旧 bundle 路线用的，PyInstaller 自己会把 dylib 收进 `_internal`，不碰。

## ⚠️ 环境侧（机器级）前提 —— 换机器/重装会丢

1. **Rosetta 必须已装**：`arch -x86_64 /usr/bin/uname -m` 返回 `x86_64` 才算有。
2. **需要框架版 Python 的 intel 切片**：`/usr/local/bin/python3.14-intel64`（`file` 应为 Mach-O x86_64）。脚本硬编码了这个路径；若以后升到别的版本/位置，改 `scripts/build-electron.sh` 里的 `X64_PY`。
3. **`.venv-x64/`** —— 本轮新建，装的是 x86_64 wheel（走 tuna 镜像）。删了下次 `--x64` 会自动重建。
4. 上一轮留下的三条机器级改动（pi-lens python shim / editable 元数据刷新 / `.pi-lens.json` 关 autofix）仍然成立，详见 `git show 3817ced:HANDOVER.md`。

## 遗留待办 & 已知问题

1. [ ] **x64 包没在真实 Intel Mac 上跑过**（最关键缺口）：本机是 Apple Silicon，x64 后端是在 **Rosetta 翻译**下跑通的，不等于原生 Intel 上没问题。发 Intel 包前应找一台真 Intel Mac（或 CI 的 `macos-13` x86 runner）验一次启动 + 一次登录/取数回合。
2. [ ] 两个架构包都只有 **ad-hoc 签名、未公证（notarize）**：对外分发仍会被 Gatekeeper 拦，跟 arm64 一样，需要 Apple Developer ID 才能根治。
3. [ ] **两架构 cryptography 版本不一致**（48.0.1 vs 50.0.0）：因为 50.x 在 cp314 上没有 x86_64 macOS wheel。想强制对齐就把版本 pin 进 `pyproject.toml`，代价是 arm64 也一起降级。
4. [ ] CI 侧还没有 Intel 打包路径（仓库目前**没有 `.github/workflows`**，mac 包都靠本机手打）。若要自动化，x64 job 得跑在 x86 runner 上，别复用 `--prepackaged` 那套 config 里带 arch 的写法（见坑 3）。
5. [ ] 未修的既有项仍在：`./start.sh stop` 按端口杀进程会**误杀 /Applications 里已安装的客户端**；`/Applications` 那份还是 **1.13.1，不含 node 可达性修复**，验 node 相关行为要先覆盖安装。

## 上一轮留档（v1.13.2：单会话执行约束 / 会话视图串台 / 打包版 node 可达性）

结论仍然成立、细节不再复述：串台裁决收在 reducer 的 `scoped(sid, action)`；切回执行中会话靠 `LiveRun` 只重放**相对动作**；node 127 的根因是 GUI 进程不读 `~/.zshrc`/`/etc/paths.d`、`terminal_tool` 原样继承最小 `os.environ`，修法在 `agent/node_env.py` 启动补 PATH。完整记录见 `git show 3817ced:HANDOVER.md`；`-webkit-app-region` 禁令、会话产物目录约定等长期约束在 `AGENTS.md` §13。

## 新会话入口

1. `git log --oneline -5` 确认在 `main` @ `595cec2`（版本仍 1.13.2）
2. 打包（含 Intel）：`AGENTS.md` §13「macOS Intel（x86_64）打包」+ `scripts/build-electron.sh` 头部注释；命令 `bash scripts/build-electron.sh --mac --x64`
3. 想接着推 Intel 交付：先看上面遗留第 1 条（真机验收）和第 4 条（CI）
4. 会话视图 / node 可达性相关代码入口：`web/src/hooks/useChat.ts`、`agent/node_env.py`
