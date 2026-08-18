import { useNavigate, useLocation } from "react-router-dom";
import { useAppState, WELCOME_MESSAGE } from "../context/AppContext";
import { api } from "../api/http";
import type { SessionSummary } from "../types";
import {
    IconPlus,
    IconMessage,
    IconBrain,
    IconTool,
    IconPuzzle,
    IconCpu,
    IconDatabase,
    IconSettings,
    IconPlug,
    IconBoxMultiple,
    IconClock,
} from "@tabler/icons-react";

const NAV = [
    { label: "历史对话", Icon: IconMessage, path: "/history", section: 1 },
    { label: "记忆管理", Icon: IconBrain, path: "/memory", section: 1 },
    { label: "技能管理", Icon: IconTool, path: "/skills", section: 1 },
    { label: "内置工具", Icon: IconPuzzle, path: "/tools", section: 1 },
    { label: "定时任务", Icon: IconClock, path: "/cronjobs", section: 1 },
    { label: "MCP 服务器", Icon: IconPlug, path: "/mcp", section: 1 },
    { label: "大模型配置", Icon: IconCpu, path: "/settings/llm", section: 2 },
    {
        label: "ERP 连接",
        Icon: IconDatabase,
        path: "/settings/erp",
        section: 2,
    },
    {
        label: "Agent 设置",
        Icon: IconSettings,
        path: "/settings/agent",
        section: 2,
    },
    {
        label: "扩展管理",
        Icon: IconBoxMultiple,
        path: "/settings/extensions",
        section: 2,
    },
];

export default function Sidebar() {
    const navigate = useNavigate();
    const location = useLocation();
    const { state, dispatch } = useAppState();
    const appVersion = state.config?.version || "unknown";

    const handleNewChat = async () => {
        try {
            const s = await api.post<Pick<SessionSummary, "id" | "title">>(
                "/sessions",
                { title: "" },
            );
            dispatch({
                type: "SET_SESSION",
                sessionId: s.id,
                title: s.title,
                messages: WELCOME_MESSAGE,
            });
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
                    <img
                        src="./favicon.png"
                        alt="智链 Agent"
                        style={{ width: 22, height: 22, borderRadius: 6 }}
                    />
                </div>
                <div>
                    <h3>智链 Agent</h3>
                    <p>多 ERP AI 助手</p>
                </div>
            </div>

            <button className="sidebar-new-btn" onClick={handleNewChat}>
                <IconPlus size={16} /> 新建对话
            </button>

            <div className="sidebar-section-label">功能</div>
            <nav className="sidebar-nav">
                {NAV.map(({ label, Icon, path, section }, i) => (
                    <div key={path}>
                        {section !== (NAV[i - 1]?.section ?? 0) &&
                            section === 2 && (
                                <div className="sidebar-section-label">
                                    设置
                                </div>
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
                ZLink Agent v{appVersion}
            </div>
        </aside>
    );
}
