import { Outlet, useLocation } from "react-router-dom";
import { useAppState } from "../context/AppContext";
import Sidebar from "./Sidebar";

const PAGE_TITLES: Record<string, string> = {
  "/": "对话",
  "/history": "历史对话",
  "/memory": "记忆管理",
  "/skills": "技能管理",
  "/settings/llm": "大模型配置",
  "/settings/erp": "ERP 连接",
  "/settings/agent": "Agent 设置",
  "/cronjobs": "定时任务",
  "/mcp": "MCP 服务器",
};

export default function Layout() {
  const location = useLocation();
  const { state } = useAppState();
  const title = PAGE_TITLES[location.pathname] || "ZLink Agent";

  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-area">
        <div className="top-bar">
          <span className="top-bar-title">{title}</span>
          {state.currentSessionId && state.currentSessionTitle && location.pathname === "/" && (
            <span style={{ fontSize: "12px", color: "var(--text-3)", marginLeft: "8px" }}>
              · {state.currentSessionTitle}
            </span>
          )}
          <span className="top-bar-meta">
            {state.agentRunning ? (
              <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <span className="sidebar-footer-dot" style={{ display: "inline-block" }} />
                思考中
              </span>
            ) : (
              state.currentSessionId ? `会话 ${state.currentSessionId.substring(0, 8)}` : ""
            )}
          </span>
        </div>
        <div className="main-content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
