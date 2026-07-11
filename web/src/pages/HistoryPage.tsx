import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MessageSquare } from "lucide-react";
import { api } from "../api/http";
import { useAppState } from "../context/AppContext";
import type { SessionSummary, SessionDetail, MemorySummary } from "../types";

export default function HistoryPage() {
  const navigate = useNavigate();
  const { state, dispatch } = useAppState();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [summaries, setSummaries] = useState<MemorySummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<SessionSummary[]>("/sessions"),
      api.get<MemorySummary[]>("/memory/summaries"),
    ]).then(([s, m]) => { setSessions(s); setSummaries(m); }).finally(() => setLoading(false));
  }, []);

  const handleOpen = async (sid: string) => {
    try {
      const detail = await api.get<SessionDetail>(`/sessions/${sid}`);
      dispatch({ type: "SET_SESSION", sessionId: detail.id, title: detail.title, messages: detail.messages });
      navigate("/");
    } catch {
      return;
    }
  };

  const handleDelete = async (sid: string) => {
    await api.del(`/sessions/${sid}`);
    setSessions((p) => p.filter((s) => s.id !== sid));
    if (state.currentSessionId === sid) dispatch({ type: "NEW_SESSION" });
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate("/")}>←</button>
        <h1 className="page-title">历史对话</h1>
      </div>

      {loading ? (
        <>
          <div className="skeleton skeleton-title" />
          <div className="skeleton skeleton-card" />
          <div className="skeleton skeleton-card" />
          <div className="skeleton skeleton-card" />
        </>
      ) : sessions.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon"><MessageSquare size={48} /></div>
          <p>暂无历史对话</p>
        </div>
      ) : (
        sessions.map((s) => {
          const summary = summaries.find((m) => m.session_id === s.id);
          const isCurrent = s.id === state.currentSessionId;
          return (
            <div key={s.id} className="card">
              <div className="card-header">
                <div>
                  <div className="card-title">
                    {isCurrent && <span className="badge badge-primary" style={{ marginRight: "8px" }}>当前</span>}
                    {s.title || "未命名对话"}
                  </div>
                  <div className="card-subtitle" style={{ marginTop: "4px" }}>
                    {new Date(s.created_at).toLocaleString()} · {s.message_count} 条消息
                  </div>
                </div>
                <span className="badge badge-primary" style={{ fontSize: "12px" }}>{s.id.substring(0, 6)}</span>
              </div>
              {summary?.summary && <div className="card-body">{summary.summary}</div>}
              <div className="card-actions">
                <button className="btn btn-primary" onClick={() => handleOpen(s.id)}>打开对话</button>
                <button className="btn btn-danger" onClick={() => handleDelete(s.id)}>删除</button>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
