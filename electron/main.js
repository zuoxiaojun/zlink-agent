const { app, BrowserWindow } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const http = require("http");

let backendProcess = null;
let mainWindow = null;
const BACKEND_PORT = 8089;
const FRONTEND_PORT = 8088;

const isDev = !app.isPackaged || process.env.NODE_ENV === "development";

function getBackendPath() {
  if (app.isPackaged) {
    const ext = process.platform === "win32" ? ".exe" : "";
    return path.join(process.resourcesPath, "backend", `ys-agent-backend${ext}`);
  }
  return null;
}

function waitForBackend(retries = 30, interval = 1000) {
  return new Promise((resolve, reject) => {
    const check = (attempt) => {
      const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/docs`, () => {
        resolve();
      });
      req.on("error", () => {
        if (attempt >= retries) {
          reject(new Error("Backend did not start in time"));
        } else {
          setTimeout(() => check(attempt + 1), interval);
        }
      });
      req.setTimeout(2000, () => {
        req.destroy();
        if (attempt >= retries) {
          reject(new Error("Backend did not start in time"));
        } else {
          setTimeout(() => check(attempt + 1), interval);
        }
      });
    };
    check(0);
  });
}

function startBackend() {
  const backendPath = getBackendPath();
  if (backendPath) {
    const dataDir = path.join(app.getPath("userData"), "data");
    backendProcess = spawn(backendPath, [], {
      stdio: ["ignore", "pipe", "pipe"],
      env: {
        ...process.env,
        YS_DATA_DIR: dataDir,
        YS_AGENT_HOST: "127.0.0.1",
        YS_AGENT_PORT: String(BACKEND_PORT),
        YS_AGENT_CORS: "*",
      },
    });
    backendProcess.stdout.on("data", (d) => console.log("[backend]", d.toString().trimEnd()));
    backendProcess.stderr.on("data", (d) => console.error("[backend]", d.toString().trimEnd()));
    backendProcess.on("exit", (code) => console.log(`[backend] exited with code ${code}`));
    console.log(`[electron] Backend spawned: ${backendPath}`);
  } else {
    console.log("[electron] Dev mode — assuming backend is already running");
  }
}

function getFrontendURL() {
  if (isDev) {
    return `http://localhost:${FRONTEND_PORT}`;
  }
  return `http://127.0.0.1:${BACKEND_PORT}`;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 900,
    minHeight: 600,
    title: "YS-Agent",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
    },
    titleBarStyle: "hiddenInset",
    show: false,
  });

  const url = getFrontendURL();
  console.log(`[electron] Loading ${url}`);
  mainWindow.loadURL(url);

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.whenReady().then(async () => {
  startBackend();
  try {
    await waitForBackend();
    console.log("[electron] Backend is ready");
  } catch (e) {
    console.error("[electron] Failed to start backend:", e.message);
  }
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (backendProcess) {
    backendProcess.kill("SIGTERM");
    backendProcess = null;
  }
});
