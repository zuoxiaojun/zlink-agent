import { useCallback, useEffect, useState, type MouseEvent as ReactMouseEvent } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { IconPackage } from "@tabler/icons-react";
import { useAppState } from "../context/AppContext";
import { useSessionArtifacts } from "../hooks/useSessionArtifacts";
import Sidebar from "./Sidebar";
import ArtifactsPanel from "./ArtifactsPanel";

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

const PREF_KEY = "zlink.artifactsPanel";
const WIDTH_KEY = `${PREF_KEY}.w`;
const MIN_W = 260;
const MAX_W = 560;
const DEFAULT_W = 320;

export interface LayoutOutlet {
  bumpArtifacts: () => void;
}

export default function Layout() {
  const location = useLocation();
  const { state } = useAppState();
  const title = PAGE_TITLES[location.pathname] || "智链 Agent";
  const isChat = location.pathname === "/";

  const [version, setVersion] = useState(0);
  const bumpArtifacts = useCallback(() => setVersion((v) => v + 1), []);
  const { data, loading, error, refresh } = useSessionArtifacts(isChat ? state.currentSessionId : null, version);

  // pref === null → 用户从未手动开合 → 有产物时自动展开
  const [pref, setPref] = useState<boolean | null>(() => {
    const stored = localStorage.getItem(PREF_KEY);
    return stored === null ? null : stored === "1";
  });
  const count = data?.count ?? 0;
  const open = isChat && (pref ?? count > 0);
  const [width, setWidth] = useState(() => Number(localStorage.getItem(WIDTH_KEY)) || DEFAULT_W);

  const toggle = useCallback(() => {
    const next = !open;
    localStorage.setItem(PREF_KEY, next ? "1" : "0");
    setPref(next);
  }, [open]);

  useEffect(() => {
    if (!isChat) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        toggle();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isChat, toggle]);

  const startResize = useCallback(
    (e: ReactMouseEvent) => {
      e.preventDefault();
      const startX = e.clientX;
      const startW = width;
      const move = (ev: MouseEvent) => {
        const next = Math.min(MAX_W, Math.max(MIN_W, startW + (startX - ev.clientX)));
        setWidth(next);
      };
      const up = () => {
        document.removeEventListener("mousemove", move);
        document.removeEventListener("mouseup", up);
        document.body.style.userSelect = "";
        localStorage.setItem(WIDTH_KEY, String(width));
      };
      document.body.style.userSelect = "none";
      document.addEventListener("mousemove", move);
      document.addEventListener("mouseup", up);
    },
    [width],
  );

  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-area">
        <div className="top-bar">
          <span className="top-bar-title">{title}</span>
          {state.currentSessionId && state.currentSessionTitle && location.pathname === "/" && (
            <span className="text-hint ml-sm">· {state.currentSessionTitle}</span>
          )}
          <span className="top-bar-meta">
            {state.agentRunning ? (
              <span className="flex-row-gap-6">
                <span className="sidebar-footer-dot" style={{ display: "inline-block" }} />
                思考中
              </span>
            ) : state.currentSessionId ? (
              `会话 ${state.currentSessionId.substring(0, 8)}`
            ) : (
              ""
            )}
            {isChat && (
              <button
                type="button"
                className={`top-bar-artifacts-btn${open ? " active" : ""}`}
                onClick={toggle}
                title="会话产物 (⌘B)"
              >
                <IconPackage size={15} />
                {count > 0 && <span className="top-bar-artifacts-badge">{count > 99 ? "99+" : count}</span>}
              </button>
            )}
          </span>
        </div>
        <div className="main-content">
          <Outlet context={{ bumpArtifacts } satisfies LayoutOutlet} />
        </div>
      </div>
      {open && (
        <>
          <div className="artifacts-resizer" onMouseDown={startResize} />
          <ArtifactsPanel
            key={state.currentSessionId ?? "none"}
            sid={state.currentSessionId}
            data={data}
            loading={loading}
            error={error}
            width={width}
            refresh={refresh}
            onCollapse={toggle}
          />
        </>
      )}
    </div>
  );
}
