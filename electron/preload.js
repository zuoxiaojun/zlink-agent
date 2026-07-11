/**
 * Electron preload — exposes backend configuration to the renderer.
 *
 * The renderer (React app) reads `window.electron` to know where the
 * Python backend is running.  In dev mode the user starts it manually;
 * in production Electron spawns it automatically.
 */

const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("electron", {
  // The Python backend API + WebSocket address
  backendUrl: "http://localhost:8089",
  wsUrl: "ws://localhost:8089",
  // Whether running inside Electron (vs plain browser)
  isElectron: true,
});
