import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { IconArrowLeft, IconHammer, IconChevronDown, IconChevronRight, IconSearch } from "@tabler/icons-react";
import { api } from "../api/http";
import type { ToolInfo } from "../types";

const TOOLSET_EMOJI: Record<string, string> = {
  terminal: "💻",
  file: "📁",
  web: "🌐",
  skills: "🎯",
  yonsuite: "📊",
  todo: "✅",
  clarify: "❓",
  memory: "🧠",
  session_search: "🔍",
};

export default function ToolsPage() {
  const navigate = useNavigate();
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.get<ToolInfo[]>("/tools").then((data) => {
      setTools(data);
      const names = new Set(data.map((t) => t.toolset));
      setCollapsed(names);
    });
  }, []);

  const filtered = useMemo(() => {
    if (!search.trim()) return tools;
    const q = search.toLowerCase();
    return tools.filter((t) =>
      t.name.toLowerCase().includes(q) ||
      t.description.toLowerCase().includes(q) ||
      t.toolset.toLowerCase().includes(q)
    );
  }, [tools, search]);

  // Group tools by toolset
  const toolsets = new Map<string, ToolInfo[]>();
  for (const t of filtered) {
    const list = toolsets.get(t.toolset) || [];
    list.push(t);
    toolsets.set(t.toolset, list);
  }

  const toggle = (toolset: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(toolset)) next.delete(toolset);
      else next.add(toolset);
      return next;
    });
  };

  const expandAll = () => setCollapsed(new Set());
  const collapseAll = () => setCollapsed(new Set(Array.from(toolsets.keys())));

  return (
    <div className="page-container">
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate("/")}><IconArrowLeft size={16} /></button>
        <h1 className="page-title">内置工具</h1>
      </div>

      <div style={{ marginBottom: "16px", display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
        <div className="search-input-wrap">
          <IconSearch size={14} className="search-input-icon" />
          <input
            className="search-input"
            placeholder="搜索工具名称、描述或分类..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <span style={{ fontSize: "13px", color: "var(--text-3)" }}>
          {search.trim() ? `找到 ${filtered.length} 个` : `共 ${tools.length} 个工具`}，{toolsets.size} 个工具集
        </span>
        <button onClick={expandAll} className="action-link">全部展开</button>
        <span style={{ color: "var(--border)" }}>|</span>
        <button onClick={collapseAll} className="action-link">全部收起</button>
      </div>

      {tools.length === 0 ? (
        <div className="empty-state">
          <IconHammer size={40} className="empty-state-icon" style={{ opacity: 0.3 }} />
          <p>暂无已注册的内置工具</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {Array.from(toolsets.entries()).map(([toolset, items]) => {
            const emoji = TOOLSET_EMOJI[toolset] || "🔧";
            const isCollapsed = collapsed.has(toolset);
            return (
              <div key={toolset} className="toolset-group">
                <div className="toolset-header" onClick={() => toggle(toolset)}>
                  <span className="toolset-header-left">
                    {isCollapsed ? <IconChevronRight size={14} /> : <IconChevronDown size={14} />}
                    <span className="toolset-emoji">{emoji}</span>
                    <span className="toolset-name">{toolset}</span>
                    <span className="toolset-count">{items.length} 个</span>
                  </span>
                </div>
                {!isCollapsed && (
                  <div className="skill-grid" style={{ padding: "8px 0" }}>
                    {items.map((t) => (
                      <div key={t.name} className="skill-card">
                        <div className="skill-card-header">
                          <div className="skill-card-name">
                            <span style={{
                              width: "8px",
                              height: "8px",
                              borderRadius: "50%",
                              background: "var(--success)",
                              flexShrink: 0,
                            }} />
                            <span style={{ fontSize: "14px", fontWeight: 600 }}>{t.emoji} {t.name}</span>
                          </div>
                        </div>
                        {t.description && (
                          <p className="skill-card-desc">{t.description}</p>
                        )}
                        <div className="skill-card-tags">
                          <span className="skill-card-tag">{t.toolset}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
