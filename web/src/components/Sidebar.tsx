import { useNavigate, useLocation } from "react-router-dom";
import { useAppState, WELCOME_MESSAGE } from "../context/AppContext";
import { api } from "../api/http";
import { Bot, Plus, MessageSquare, Brain, Wrench, Puzzle, Cpu, Database, Settings, Plug } from "lucide-react";

const NAV = [
  { label: "历史对话", Icon: MessageSquare, path: "/history", section: 1 },
  { label: "记忆管理", Icon: Brain, path: "/memory", section: 1 },
  { label: "技能管理", Icon: Wrench, path: "/skills", section: 1 },
  { label: "内置工具", Icon: Puzzle, path: "/tools", section: 1 },
  { label: "MCP 服务器", Icon: Plug, path: "/mcp", section: 1 },
  { label: "LLM 配置", Icon: Cpu, path: "/settings/llm", section: 2 },
  { label: "YonSuite 配置", Icon: Database, path: "/settings/yonsuite", section: 2 },
  { label: "Agent 设置", Icon: Settings, path: "/settings/agent", section: 2 },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { dispatch } = useAppState();

  const handleNewChat = async () => {
    try {
      const s = await api.post<any>("/sessions", { title: "" });
      dispatch({ type: "SET_SESSION", sessionId: s.id, title: s.title, messages: WELCOME_MESSAGE });
      navigate(`/?s=${s.id}`);
    } catch {
      dispatch({ type: "NEW_SESSION" });
      navigate("/");
    }
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-icon">
          <Bot size={18} color="#fff" />
        </div>
        <div>
          <h3>YS-Agent</h3>
          <p>YonSuite AI 助手</p>
        </div>
      </div>

      <button className="sidebar-new-btn" onClick={handleNewChat}>
        <Plus size={16} /> 新建对话
      </button>

      <div className="sidebar-section-label">功能</div>
      <nav className="sidebar-nav">
        {NAV.map(({ label, Icon, path, section }, i) => (
          <div key={path}>
            {section !== (NAV[i - 1]?.section ?? 0) && section === 2 && (
              <div className="sidebar-section-label">设置</div>
            )}
            <button
              className={`sidebar-nav-item${location.pathname === path ? " active" : ""}`}
              onClick={() => navigate(path)}
            >
              <Icon size={16} className="nav-icon" />
              {label}
            </button>
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-footer-dot" />
        YS-Agent v1.0
      </div>
    </aside>
  );
}
