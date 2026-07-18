/**
 * port.js — 后端端口占用处理（生产模式启动后端前调用）。
 *
 * 策略：端口被占用时，只杀"自己人"（命令行包含 zlink-backend 的进程，
 * 通常是上次异常退出残留的后端）；占用者是外来进程时不做破坏性操作，
 * 通过 foreignPids 返回，让调用方提示用户自行处理。
 *
 * 本模块不依赖 electron，可用 node 直接做单测。
 */

const { execSync } = require("child_process");

const OWN_PROCESS_PATTERN = /zlink-backend/i;

/** 列出正在监听指定端口的进程 PID（字符串数组，去重）。 */
function listListenerPids(port) {
  if (process.platform === "win32") {
    try {
      const out = execSync("netstat -ano -p tcp", { encoding: "utf8" });
      return [
        ...new Set(
          out
            .split(/\r?\n/)
            .filter((l) => l.includes(`:${port}`) && l.includes("LISTENING"))
            .map((l) => l.trim().split(/\s+/).pop())
            .filter(Boolean)
        ),
      ];
    } catch {
      return [];
    }
  }
  try {
    const out = execSync(`lsof -nP -iTCP:${port} -sTCP:LISTEN -t`, {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    return out ? [...new Set(out.split(/\s+/))] : [];
  } catch {
    return []; // lsof 无匹配时 exit 1
  }
}

/** 查询进程命令行，用于判断是否为本应用残留的后端。 */
function processCommand(pid) {
  try {
    if (process.platform === "win32") {
      return execSync(`tasklist /FI "PID eq ${pid}" /FO CSV /NH`, { encoding: "utf8" });
    }
    return execSync(`ps -p ${pid} -o command=`, { encoding: "utf8" }).trim();
  } catch {
    return "";
  }
}

function killPid(pid, force) {
  try {
    if (process.platform === "win32") {
      execSync(`taskkill /PID ${pid} /T ${force ? "/F" : ""}`, { stdio: "ignore" });
    } else {
      process.kill(Number(pid), force ? "SIGKILL" : "SIGTERM");
    }
  } catch {
    /* 进程可能已自行退出 */
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * 确保端口可用：杀掉残留的自家后端进程并等待端口释放。
 *
 * @param {number} port
 * @param {{timeoutMs?: number}} opts
 * @returns {Promise<{ok: boolean, killedPids: string[], foreignPids: string[]}>}
 *   ok=false 且 foreignPids 非空 → 被外来进程占用，需用户处理；
 *   ok=false 且 foreignPids 为空 → 自家残留进程没能杀掉。
 */
async function ensurePortFree(port, { timeoutMs = 8000 } = {}) {
  const killed = [];
  const foreign = [];

  for (const pid of listListenerPids(port)) {
    if (OWN_PROCESS_PATTERN.test(processCommand(pid))) {
      killPid(pid, false);
      killed.push(pid);
    } else {
      foreign.push(pid);
    }
  }
  if (foreign.length > 0) return { ok: false, killedPids: killed, foreignPids: foreign };

  // 前半段等 SIGTERM 优雅退出；仍有残留则 SIGKILL，再等后半段。
  const deadline = Date.now() + timeoutMs;
  let escalated = false;
  while (Date.now() < deadline) {
    const pids = listListenerPids(port);
    if (pids.length === 0) return { ok: true, killedPids: killed, foreignPids: [] };
    if (!escalated && Date.now() > deadline - timeoutMs / 2) {
      escalated = true;
      for (const pid of pids) killPid(pid, true);
    }
    await sleep(200);
  }
  return { ok: listListenerPids(port).length === 0, killedPids: killed, foreignPids: [] };
}

module.exports = { ensurePortFree, listListenerPids, processCommand };
