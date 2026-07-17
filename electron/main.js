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

async function waitForBackend(maxRetries = 60) {
  if (IS_DEV) return;
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(`${BACKEND_HOST}/api/config`);
      if (res.ok) return;
    } catch { /* not ready yet */ }
    await new Promise((r) => setTimeout(r, 1000));
  }
  console.warn("[electron] Backend did not start in time");
}

let mainWindow = null;

async function createWindow() {
  startBackend();
  await waitForBackend();

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

  mainWindow.loadURL(getLoadURL());
  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.on("closed", () => { mainWindow = null; });

  if (IS_DEV) mainWindow.webContents.openDevTools({ mode: "detach" });
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
