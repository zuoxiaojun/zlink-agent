import { useEffect, useState } from "react";
import { IconTool } from "@tabler/icons-react";
import { useAppState } from "../context/AppContext";

function formatElapsed(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const mm = String(Math.floor(totalSec / 60)).padStart(2, "0");
  const ss = String(totalSec % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

export default function AgentStatusBar() {
  const { state } = useAppState();
  const [elapsed, setElapsed] = useState(0);

  const running = state.agentRunning;

  useEffect(() => {
    if (!running) return;
    const start = Date.now();
    const id = window.setInterval(() => {
      setElapsed(Date.now() - start);
    }, 1000);
    return () => window.clearInterval(id);
  }, [running]);

  // 未运行时显示 00:00（派生值而非在 effect 内同步 setState，避免级联重渲染）
  const displayElapsed = running ? elapsed : 0;

  const label = state.currentToolName
    ? `调用工具 ${state.currentToolName}`
    : state.progressMessage
      ? state.progressMessage
      : "思考中…";

  return (
    <div className="agent-status-bar" role="status" aria-live="polite">
      <span className="agent-status-icon">
        {state.currentToolName ? (
          <IconTool size={14} />
        ) : (
          <span className="agent-status-dots">
            <span />
            <span />
            <span />
          </span>
        )}
      </span>
      <span className="agent-status-label">{label}</span>
      <span className="agent-status-elapsed">{formatElapsed(displayElapsed)}</span>
    </div>
  );
}
