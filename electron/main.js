/**
 * Electron main process — wraps the ZLink Agent Python backend in a
 * desktop window.
 *
 * Development mode:
 *   npm run dev:electron  (needs backend started separately)
 *
 * Production mode (self-contained):
 *   bash scripts/build-electron.sh
 */

const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const { ensurePortFree } = require("./port");

const IS_DEV = !app.isPackaged;

// ── Backend management ─────────────────────────────────────────────

let backendProcess = null;
const BACKEND_PORT = 8089;
const BACKEND_HOST = `http://localhost:${BACKEND_PORT}`;

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
      // Electron 自带 Node 运行时，供后端启动 Chart MCP（新用户机器没有 node）
      ELECTRON_NODE_PATH: process.execPath,
    },
  });

  backendProcess.stdout.on("data", (d) => process.stdout.write(`[backend] ${d}`));
  backendProcess.stderr.on("data", (d) => process.stderr.write(`[backend] ${d}`));
  backendProcess.on("exit", (code) => {
    console.log(`[electron] Backend exited (code=${code})`);
    backendProcess = null;
  });
}

function stopBackend() {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
}

// ── Window ────────────────────────────────────────────────────────

function getLoadURL() {
  if (IS_DEV) return "http://localhost:8088";
  // ASAR-unpacked frontend files (see asarUnpack in electron-builder.yml)
  return `file://${path.join(process.resourcesPath, "app.asar.unpacked", "web", "dist", "index.html")}`;
}

/** Poll until the backend answers /api/health. */
async function waitForBackend(maxRetries = 300) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(`${BACKEND_HOST}/api/health`);
      if (res.ok) return true;
    } catch { /* not ready yet */ }
    await new Promise((r) => setTimeout(r, 100));
  }
  return false;
}

const _T0 = Date.now();
function logStartup(stage) {
  console.log(`[startup] ${stage} ${Date.now() - _T0}ms`);
}

let mainWindow = null;

async function createWindow() {
  // 端口检查与窗口创建/loading 渲染并行：先发起（不 await），spawn 前再等结果
  const portPromise = IS_DEV ? null : ensurePortFree(BACKEND_PORT);

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 900,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
    titleBarStyle: "hiddenInset",
    show: false,
  });
  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.on("closed", () => { mainWindow = null; });

  // 先显示加载页：PyInstaller onefile 解包 + 后端启动需要十几秒，
  // 避免用户双击后长时间看不到任何反馈。
  await mainWindow.loadFile(path.join(__dirname, "loading.html"));
  logStartup("window created");

  if (IS_DEV) {
    mainWindow.loadURL(getLoadURL());
    mainWindow.webContents.openDevTools({ mode: "detach" });
    return;
  }

  // 端口被占用：杀掉上次异常退出残留的 zlink-backend；
  // 占用者是外来进程时不做破坏性操作，提示用户自行处理。
  const port = await portPromise;
  logStartup("port ready");
  if (!port.ok) {
    const detail = port.foreignPids.length
      ? `端口 ${BACKEND_PORT} 被其他程序占用（PID: ${port.foreignPids.join(", ")}）。\n请关闭该程序后重新打开 ZLink Agent。`
      : `端口 ${BACKEND_PORT} 未能释放（残留进程无法终止）。\n请重启电脑后重试。`;
    dialog.showErrorBox("启动失败", detail);
    app.quit();
    return;
  }

  startBackend();
  logStartup("backend spawned");

  const ready = await waitForBackend();
  logStartup(`backend healthy ready=${ready}`);
  if (!mainWindow) return; // 用户在启动期间关闭了窗口
  if (!ready) {
    dialog.showErrorBox(
      "启动失败",
      "后端服务启动超时。\n日志位置：~/.zlink-agent/data/logs/app.log",
    );
    app.quit();
    return;
  }
  mainWindow.loadURL(getLoadURL());
  logStartup("frontend loadURL");
}

// ── App lifecycle ─────────────────────────────────────────────────

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  stopBackend();
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (mainWindow === null) createWindow();
});

app.on("before-quit", () => {
  stopBackend();
});
