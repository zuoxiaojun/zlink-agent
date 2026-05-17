import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, FileText, User, ClipboardList, ChevronDown, ChevronRight } from "lucide-react";
import { api } from "../api/http";
import type { MemoryFacts, MemorySummary } from "../types";

const SECTIONS = [
  { key: "notes", icon: FileText, label: "Agent 笔记" },
  { key: "profile", icon: User, label: "用户画像" },
  { key: "summaries", icon: ClipboardList, label: "对话摘要" },
];

export default function MemoryPage() {
  const navigate = useNavigate();
  const [facts, setFacts] = useState<MemoryFacts>({ memory: [], user: [] });
  const [summaries, setSummaries] = useState<MemorySummary[]>([]);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  useEffect(() => {
    Promise.all([
      api.get<MemoryFacts>("/memory/facts"),
      api.get<MemorySummary[]>("/memory/summaries"),
    ]).then(([f, s]) => { setFacts(f); setSummaries(s); });
  }, []);

  const toggle = (key: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const expandAll = () => setCollapsed(new Set());
  const collapseAll = () => setCollapsed(new Set(SECTIONS.map((s) => s.key)));

  const total = facts.memory.length + facts.user.length + summaries.length;

  return (
    <div className="page-container">
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate("/")}><ArrowLeft size={16} /></button>
        <h1 className="page-title">记忆管理</h1>
      </div>

      <div style={{ marginBottom: "16px", display: "flex", alignItems: "center", gap: "12px" }}>
        <span style={{ fontSize: "13px", color: "var(--text-3)" }}>
          共 {total} 条记忆，{SECTIONS.length} 个分类
        </span>
        <button onClick={expandAll} className="action-link">全部展开</button>
        <span style={{ color: "var(--border)" }}>|</span>
        <button onClick={collapseAll} className="action-link">全部收起</button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {/* Agent 笔记 */}
        <div className="toolset-group">
          <div className="toolset-header" onClick={() => toggle("notes")}>
            <span className="toolset-header-left">
              {collapsed.has("notes") ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
              <FileText size={14} />
              <span className="toolset-name">Agent 笔记</span>
              <span className="toolset-count">{facts.memory.length} 条</span>
            </span>
          </div>
          {!collapsed.has("notes") && (
            <div style={{ padding: "8px 16px 12px" }}>
              {facts.memory.length === 0 ? (
                <div style={{ color: "var(--text-3)", fontSize: "13px" }}>暂无笔记</div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {facts.memory.map((e, i) => (
                    <div key={i} style={{ padding: "8px 12px", background: "var(--bg-hover)", borderRadius: "var(--radius-sm)", fontSize: "13px", color: "var(--text-2)" }}>
                      {e}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* 用户画像 */}
        <div className="toolset-group">
          <div className="toolset-header" onClick={() => toggle("profile")}>
            <span className="toolset-header-left">
              {collapsed.has("profile") ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
              <User size={14} />
              <span className="toolset-name">用户画像</span>
              <span className="toolset-count">{facts.user.length} 条</span>
            </span>
          </div>
          {!collapsed.has("profile") && (
            <div style={{ padding: "8px 16px 12px" }}>
              {facts.user.length === 0 ? (
                <div style={{ color: "var(--text-3)", fontSize: "13px" }}>暂无画像</div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {facts.user.map((e, i) => (
                    <div key={i} style={{ padding: "8px 12px", background: "var(--bg-hover)", borderRadius: "var(--radius-sm)", fontSize: "13px", color: "var(--text-2)" }}>
                      {e}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* 对话摘要 */}
        <div className="toolset-group">
          <div className="toolset-header" onClick={() => toggle("summaries")}>
            <span className="toolset-header-left">
              {collapsed.has("summaries") ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
              <ClipboardList size={14} />
              <span className="toolset-name">对话摘要</span>
              <span className="toolset-count">{summaries.length} 条</span>
            </span>
          </div>
          {!collapsed.has("summaries") && (
            <div style={{ padding: "8px 16px 12px" }}>
              {summaries.length === 0 ? (
                <div style={{ color: "var(--text-3)", fontSize: "13px" }}>暂无摘要</div>
              ) : (
                summaries.map((s) => (
                  <div key={s.session_id} style={{ padding: "6px 0", borderBottom: "1px solid var(--border-light)" }}>
                    <div className="card-subtitle">{s.title}</div>
                    <div style={{ fontSize: "13px", color: "var(--text-2)", marginTop: "2px" }}>{s.summary}</div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
