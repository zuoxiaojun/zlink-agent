import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { IconArrowLeft, IconFileText, IconUser, IconClipboardList, IconChevronDown, IconChevronRight } from "@tabler/icons-react";
import { api } from "../api/http";
import type { MemoryFacts, MemorySummary } from "../types";

const SECTIONS = [
  { key: "notes", icon: IconFileText, label: "Agent 笔记" },
  { key: "profile", icon: IconUser, label: "用户画像" },
  { key: "summaries", icon: IconClipboardList, label: "对话摘要" },
];

export default function MemoryPage() {
  const navigate = useNavigate();
  const [facts, setFacts] = useState<MemoryFacts>({ memory: [], user: [] });
  const [summaries, setSummaries] = useState<MemorySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  useEffect(() => {
    const start = Date.now();
    Promise.all([
      api.get<MemoryFacts>("/memory/facts"),
      api.get<MemorySummary[]>("/memory/summaries"),
    ]).then(([f, s]) => { setFacts(f); setSummaries(s); }).finally(() => {
      const elapsed = Date.now() - start;
      if (elapsed < 300) setTimeout(() => setLoading(false), 300 - elapsed);
      else setLoading(false);
    });
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
        <button className="back-btn" onClick={() => navigate("/")}><IconArrowLeft size={16} /></button>
        <h1 className="page-title">记忆管理</h1>
      </div>

      {loading ? (
        <>
          <div className="skeleton skeleton-title" />
          <div className="skeleton skeleton-card" style={{ height: 60 }} />
          <div className="skeleton skeleton-card" style={{ height: 60 }} />
          <div className="skeleton skeleton-card" style={{ height: 200 }} />
        </>
      ) : (
        <>
      <div style={{ marginBottom: "16px", display: "flex", alignItems: "center", gap: "12px" }}>
        <span style={{ fontSize: "13px", color: "var(--text-3)" }}>
          共 {total} 条记忆，{SECTIONS.length} 个分类
        </span>
        <button onClick={expandAll} className="action-link">全部展开</button>
        <span style={{ color: "var(--border)" }}>|</span>
        <button onClick={collapseAll} className="action-link">全部收起</button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <div className="toolset-group">
          <div className="toolset-header" onClick={() => toggle("notes")}>
            <span className="toolset-header-left">
              {collapsed.has("notes") ? <IconChevronRight size={14} /> : <IconChevronDown size={14} />}
              <IconFileText size={14} />
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
                    <div key={i} style={{ padding: "8px 12px", background: "var(--bg-hover)", borderRadius: "var(--radius-sm)", fontSize: "13px", color: "var(--text-2)" }}>{e}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="toolset-group">
          <div className="toolset-header" onClick={() => toggle("profile")}>
            <span className="toolset-header-left">
              {collapsed.has("profile") ? <IconChevronRight size={14} /> : <IconChevronDown size={14} />}
              <IconUser size={14} />
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
                    <div key={i} style={{ padding: "8px 12px", background: "var(--bg-hover)", borderRadius: "var(--radius-sm)", fontSize: "13px", color: "var(--text-2)" }}>{e}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="toolset-group">
          <div className="toolset-header" onClick={() => toggle("summaries")}>
            <span className="toolset-header-left">
              {collapsed.has("summaries") ? <IconChevronRight size={14} /> : <IconChevronDown size={14} />}
              <IconClipboardList size={14} />
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
        </>
      )}
    </div>
  );
}
