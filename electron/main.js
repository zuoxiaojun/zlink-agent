/**
 * Electron main process — wraps the ZLink Agent Python backend in a
 * desktop window.
 *
 * Development mode (Vite HMR):
 *   npm run electron:dev
 *   → expects backend running on localhost:8089, Vite on localhost:8088
 *
 * Production mode (PyInstaller + Electron):
 *   bash build-electron.sh
 *   → bundles PyInstaller binary + Electron into a single .app / .exe
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

function findBackendBinary() {
  // In production: look for PyInstaller binary next to Electron
  const searchPaths = [
    path.join(process.resourcesPath, "zlink-agent"),       // macOS .app
    path.join(process.resourcesPath, "zlink-agent.exe"),    // Windows
    path.join(path.dirname(app.getPath("exe")), "zlink-agent"),
    path.join(path.dirname(app.getPath("exe")), "zlink-agent.exe"),
  ];
  for (const p of searchPaths) {
    if (fs.existsSync(p)) return p;
  }
  return null;
}

function startBackend() {
  if (IS_DEV) {
    console.log("[electron] Dev mode — backend should be started separately");
    return;
  }

  const binary = findBackendBinary();
  if (!binary) {
    dialog.showErrorBox("启动失败", "找不到后端程序 zlink-agent。请运行 build-electron.sh 重新打包。");
    app.quit();
    return;
  }

  console.log(`[electron] Starting backend: ${binary}`);
  backendProcess = spawn(binary, [], {
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, ZLINK_AGENT_PORT: String(BACKEND_PORT) },
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
  if (IS_DEV) {
    // Development: Vite dev server
    return "http://localhost:8088";
  }
  // Production: built frontend files
  return `file://${path.join(__dirname, "..", "web", "dist", "index.html")}`;
}

async function waitForBackend(maxRetries = 30) {
  if (IS_DEV) return; // assume backend is already running in dev mode
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(`${BACKEND_HOST}/api/config`);
      if (res.ok) return;
    } catch {
      // not ready yet
    }
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
    titleBarStyle: "hiddenInset", // macOS: compact title bar
    show: false,
  });

  mainWindow.loadURL(getLoadURL());

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  if (IS_DEV) {
    mainWindow.webContents.openDevTools({ mode: "detach" });
  }
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
