# PyInstaller 迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-subagent-driven-development (recommended) or superpowers-executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 ZLink Agent Electron 客户端的 Python 打包方案从 `scripts/bundle-python.sh`（Homebrew venv）迁移到 PyInstaller `--onefile`，使后端能在用户机器上独立运行

**Architecture:** PyInstaller 将 `backend/main.py` + uvicorn + 所有第三方依赖打包成一个单文件 `zlink-backend`；Electron 直接 spawn 这个二进制，不再需要`backend_launcher.py`和`python-bundle/`目录；electron-builder 的 extraResources 精简为只包含 PyInstaller 产物 + Chart MCP server

**Tech Stack:** PyInstaller 6.21.0 / Python 3.13 / Electron / electron-builder

---

### Task 1: 创建 PyInstaller 专用构建脚本

**Files:**
- Create: `scripts/build-pyinstaller.sh`
- (不影响现有文件)

构建脚本负责执行 PyInstaller 打包，包含所有必要参数。这样 `build-electron.sh` 只需调用此脚本，保持步骤清晰。

- [ ] **Step 1: 创建 `scripts/build-pyinstaller.sh`**

```bash
#!/bin/bash
# build-pyinstaller.sh — PyInstaller 打包 ZLink Agent Python 后端
#
# 用法:
#   bash scripts/build-pyinstaller.sh            # 打包为单文件
#   bash scripts/build-pyinstaller.sh --onedir   # 打包为单目录（调试用）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$(dirname "$0")/.."

MODE="${1:---onefile}"
PLATFORM_TAG=""
case "$(uname -s)" in
  Darwin) PLATFORM_TAG="macos-$(uname -m)" ;;
  Linux)  PLATFORM_TAG="linux-$(uname -m)" ;;
  MINGW*|MSYS*) PLATFORM_TAG="win" ;;
esac

echo "╔══════════════════════════════════════════════╗"
echo "║     PyInstaller 打包 ZLink 后端              ║"
echo "║     模式: $MODE"
echo "║     平台: $PLATFORM_TAG"
echo "╚══════════════════════════════════════════════╝"

# 确保 venv 里有 pyinstaller
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "安装 PyInstaller..."
    pip install pyinstaller
fi

echo ""
echo "▶ 打包中..."

python3 -m PyInstaller \
    --clean \
    --noconfirm \
    $MODE \
    --name zlink-backend \
    --add-data "agent/skills:skills" \
    --hidden-import uvicorn \
    --hidden-import uvicorn.logging \
    --hidden-import uvicorn.loops \
    --hidden-import uvicorn.loops.auto \
    --hidden-import uvicorn.protocols \
    --hidden-import uvicorn.protocols.http \
    --hidden-import uvicorn.protocols.http.auto \
    --hidden-import uvicorn.middleware \
    --hidden-import uvicorn.middleware.asgi2 \
    --hidden-import uvicorn.middleware.debug \
    --hidden-import uvicorn.middleware.proxy_headers \
    --hidden-import uvicorn.middleware.wsgi \
    --hidden-import oracledb \
    backend/main.py

echo ""
echo "✅ PyInstaller 打包完成"
echo "   产物: dist/zlink-backend"
ls -lh dist/zlink-backend*
```

- [ ] **Step 2: 测试 PyInstaller 构建是否成功**

Run: `bash scripts/build-pyinstaller.sh`
Expected: 退出码 0，`dist/zlink-backend` 文件存在且 >10MB

- [ ] **Step 3: 测试二进制能否独立启动（后台运行后 kill）**

```bash
# 启动后端（后台运行，限制 5 秒后自动 kill）
./dist/zlink-backend &
BACKEND_PID=$!
sleep 3
# 测试健康检查
curl -s http://localhost:8089/api/health 2>/dev/null && echo "✅ 后端正常运行" || echo "❌ 后端未响应"
# 测试内置技能列表
curl -s http://localhost:8089/api/skills 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'✅ 技能数: {len(d)}')" 2>/dev/null || echo "⚠️ 技能列表异常"
kill $BACKEND_PID 2>/dev/null
wait $BACKEND_PID 2>/dev/null
```

Expected: 后端启动成功，`/api/health` 返回 200，技能列表返回 20 个

- [ ] **Step 4: 如果测试失败，排查并修复**（常见问题：漏了某个 hidden-import；`agent/skills/` 路径不对；某个动态加载模块没找到）

- [ ] **Step 5: 提交构建脚本**

```bash
git add -f dist/zlink-backend 2>/dev/null || true
git add scripts/build-pyinstaller.sh
git commit -m "build: add PyInstaller build script for backend"
```

### Task 2: 修改 `scripts/build-electron.sh`

**Files:**
- Modify: `scripts/build-electron.sh`

将 [2/4] 步骤从 `bash scripts/bundle-python.sh` 替换为调用新脚本。

- [ ] **Step 1: 修改 [2/4] 步骤**

将：
```bash
echo "[2/4] 打包 Python 运行环境..."
if [ -f "build/python-bundle/bin/python" ]; then
    echo "  ⏭️  build/python-bundle 已存在，跳过重新构建（如需重建请删除该目录）"
else
    bash scripts/bundle-python.sh
fi
echo "✅ Python 环境打包完成"
```

改为：
```bash
echo "[2/4] 打包 Python 后端 (PyInstaller)..."
bash scripts/build-pyinstaller.sh
echo "✅ PyInstaller 打包完成: dist/zlink-backend"
```

- [ ] **Step 2: 确认改动生效**

Run: `grep -n "build-pyinstaller\|bundle-python" scripts/build-electron.sh`
Expected: 只出现 `build-pyinstaller`，不出现 `bundle-python`

- [ ] **Step 3: 提交**

```bash
git add scripts/build-electron.sh
git commit -m "build: replace bundle-python.sh with PyInstaller in electron build"
```

### Task 3: 修改 `electron/main.js`

**Files:**
- Modify: `electron/main.js`

核心变化：
- `findBundledPython()` → `findBackendBinary()`：找 `zlink-backend` 单文件
- `findBackendLauncher()`：删除（不再需要 backend_launcher.py）
- `startBackend()`：改用 `spawn(zlink-backend, [])`，移除 `PYTHONPATH`
- 移除 `backend_launcher.py` 相关的 `preload.js` 逻辑（如果有）

- [ ] **Step 1: 修改函数 `findBundledPython()` 为 `findBackendBinary()`**

将：
```javascript
/** Resolve bundled Python path inside the app resources. */
function findBundledPython() {
  if (IS_DEV) return null;
  const dir = process.resourcesPath;
  const candidates = [
    // macOS/Linux: venv uses bin/
    path.join(dir, "python-bundle", "bin", "python3"),
    path.join(dir, "python-bundle", "bin", "python"),
    // Windows: venv uses Scripts/python.exe
    path.join(dir, "python-bundle", "Scripts", "python.exe"),
    path.join(dir, "python-bundle", "Scripts", "python3.exe"),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return null;
}
```

改为：
```javascript
/** Resolve bundled PyInstaller backend binary inside the app resources. */
function findBackendBinary() {
  if (IS_DEV) return null;
  const dir = process.resourcesPath;
  const candidates = [
    // macOS/Linux
    path.join(dir, "zlink-backend"),
    // Windows
    path.join(dir, "zlink-backend.exe"),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return null;
}
```

- [ ] **Step 2: 删除 `findBackendLauncher()`**

删除整个函数（后续没有调用它的地方了）。

- [ ] **Step 3: 删除 `findProjectRoot()`**

删除整个函数（不再需要 PYTHONPATH + app/ 源码包）。

- [ ] **Step 4: 修改 `startBackend()`**

将：
```javascript
function startBackend() {
  if (IS_DEV) {
    console.log("[electron] Dev mode — start backend separately");
    return;
  }

  const pythonBin = findBundledPython();
  if (!pythonBin) {
    dialog.showErrorBox("启动失败", "找不到内置 Python 运行环境。请运行 scripts/bundle-python.sh 重新构建。");
    app.quit();
    return;
  }

  // Use the launcher script so Python can import backend.main
  const launcher = findBackendLauncher();
  if (!launcher) {
    dialog.showErrorBox("启动失败", "找不到后端启动脚本 (backend_launcher.py)");
    app.quit();
    return;
  }

  console.log(`[electron] Starting backend: ${pythonBin}`);
  console.log(`[electron] Launcher: ${launcher}`);

  // Project source is at Resources/app/ (electron-builder extraResources)
  // Add to PYTHONPATH so subprocesses (MCP servers) can find agent/ etc.
  const pythonBundleDir = path.dirname(path.dirname(pythonBin));
  const resourcesPath = path.dirname(pythonBundleDir);
  const appDir = path.join(resourcesPath, "app");

  backendProcess = spawn(pythonBin, [launcher], {
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      ZLINK_AGENT_PORT: String(BACKEND_PORT),
      ZLINK_AGENT_CORS: "*",  // allow file:// origin in Electron
      PYTHONPATH: appDir,      // bundled project source for MCP subprocesses
    },
  });
  ...
}
```

改为：
```javascript
function startBackend() {
  if (IS_DEV) {
    console.log("[electron] Dev mode — start backend separately");
    return;
  }

  const backendBin = findBackendBinary();
  if (!backendBin) {
    dialog.showErrorBox("启动失败", "找不到后端程序 (zlink-backend)。请运行 scripts/build-pyinstaller.sh 重新构建。");
    app.quit();
    return;
  }

  console.log(`[electron] Starting backend: ${backendBin}`);

  backendProcess = spawn(backendBin, [], {
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      ZLINK_AGENT_PORT: String(BACKEND_PORT),
      ZLINK_AGENT_CORS: "*",  // allow file:// origin in Electron
    },
  });

  backendProcess.stdout.on("data", (d) => process.stdout.write(`[backend] ${d}`));
  backendProcess.stderr.on("data", (d) => process.stderr.write(`[backend] ${d}`));
  backendProcess.on("exit", (code) => {
    console.log(`[electron] Backend exited (code=${code})`);
    backendProcess = null;
  });
}
```

- [ ] **Step 5: 提交**

```bash
git add electron/main.js
git commit -m "refactor: switch from bundled Python venv to PyInstaller binary in Electron"
```

### Task 4: 修改 `electron-builder.yml`

**Files:**
- Modify: `electron-builder.yml`

精简 extraResources：移除 `python-bundle/` 和 `app/` 源码包，添加 PyInstaller 产物。

- [ ] **Step 1: 修改 extraResources 配置**

将：
```yaml
extraResources:
  # 自包含 Python 运行环境 (build by scripts/bundle-python.sh)
  - from: build/python-bundle/
    to: python-bundle
    filter:
      - "**/*"
  # 项目源码
  - from: .
    to: app
    filter:
      - "backend/**/*.py"
      - "agent/**/*"
      - "!agent/**/__pycache__/**"
      - "!agent/**/*.pyc"
      - "scripts/**/*.py"
      - "packaging/**/*"
      - "requirements.txt"
      - "pyproject.toml"
      - "LICENSE"
  # Chart MCP server (预置, npx @antv/mcp-server-chart)
  - from: node_modules/@antv/mcp-server-chart/
    to: mcp-chart
    filter:
      - "**/*"
  # 后端启动脚本
  - from: electron/
    to: .
    filter:
      - "backend_launcher.py"
```

改为：
```yaml
extraResources:
  # PyInstaller 打包的后端单文件二进制 (build by scripts/build-pyinstaller.sh)
  - from: dist/zlink-backend
    to: .
  # Chart MCP server (预置, npx @antv/mcp-server-chart)
  - from: node_modules/@antv/mcp-server-chart/
    to: mcp-chart
    filter:
      - "**/*"
```

- [ ] **Step 2: 检查 `electron/main.js:getLoadURL()` 中的 `app.asar.unpacked` 路径是否受影响**

读取 electron-builder.yml 确认 `asarUnpack` 只涉及前端文件：
```yaml
asarUnpack:
  - web/dist/**
```
这个不变，不需要改。

- [ ] **Step 3: 提交**

```bash
git add electron-builder.yml
git commit -m "build: replace python-bundle and app source with PyInstaller binary in extraResources"
```

### Task 5: 清理 `backend_launcher.py` 相关引用

**Files:**
- Read-only: `electron/backend_launcher.py`（不再需要，不删除文件，仅从构建流程移除）

Electron 不会再引用 `backend_launcher.py`，electron-builder.yml 已移除其 extraResources 配置。文件保留在仓库中作为参考。

- [ ] **Step 1: 确认不再有任何文件引用 `backend_launcher.py`**

Run: `grep -rn "backend_launcher" --include="*.js" --include="*.json" --include="*.yml" --include="*.yaml" .`
Expected: 没有匹配结果

- [ ] **Step 2: 提交清理确认**

```bash
git add electron/backend_launcher.py  # 不删除，保留
git commit -m "chore: remove backend_launcher.py from build pipeline (kept as reference)"
```

### Task 6: 完整构建并验证

**Files:**
- No file changes

执行全量构建，验证 .dmg 产物可用。

- [ ] **Step 1: 运行完整构建**

```bash
bash scripts/build-electron.sh
```

Expected: 构建成功，`dist-electron/ZLink Agent-1.7.0-arm64.dmg` 存在

- [ ] **Step 2: 验证 dmg 大小合理**

```bash
ls -lh dist-electron/*.dmg
```

Expected: 大小在 60-100MB 之间（PyInstaller ~40-60MB + Electron shell + Chart MCP）

- [ ] **Step 3: 验证构建日志无 Python 相关错误**

```bash
grep -i "error\|traceback\|exception" dist-electron/builder-debug.yml 2>/dev/null || echo "无构建错误"
```