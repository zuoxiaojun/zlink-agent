import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { IconArrowLeft, IconHammer, IconSearch } from "@tabler/icons-react";
import { api } from "../api/http";
import Drawer from "../components/Drawer";
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
  const [selected, setSelected] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.get<ToolInfo[]>("/tools").then(setTools);
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
  const toolsets = useMemo(() => {
    const map = new Map<string, ToolInfo[]>();
    for (const t of filtered) {
      const list = map.get(t.toolset) || [];
      list.push(t);
      map.set(t.toolset, list);
    }
    return map;
  }, [filtered]);

  const selectedTools = selected ? toolsets.get(selected) || [] : [];

  return (
    <div className="page-container">
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate("/")}><IconArrowLeft size={16} /></button>
        <h1 className="page-title">内置工具</h1>
      </div>

      <div className="toolbar-md">
        <div className="search-input-wrap">
          <IconSearch size={14} className="search-input-icon" />
          <input
            className="search-input"
            placeholder="搜索工具名称、描述或分类..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <span className="text-meta">
          {search.trim() ? `找到 ${filtered.length} 个` : `共 ${tools.length} 个工具`}，{toolsets.size} 个工具集
        </span>
      </div>

      {tools.length === 0 ? (
        <div className="empty-state">
          <IconHammer size={40} className="empty-state-icon empty-state-icon-dim" />
          <p>暂无已注册的内置工具</p>
        </div>
      ) : (
        <div className="card-grid">
          {Array.from(toolsets.entries()).map(([toolset, items]) => {
            const emoji = TOOLSET_EMOJI[toolset] || "🔧";
            return (
              <div
                key={toolset}
                className="skill-card"
                style={{ cursor: "pointer" }}
                onClick={() => setSelected(toolset)}
              >
                <div className="skill-card-header">
                  <div className="skill-card-name">
                    <span className="toolset-emoji">{emoji}</span>
                    <span className="text-name">{toolset}</span>
                    <span className="toolset-count">{items.length} 个</span>
                  </div>
                </div>
                <p className="skill-card-desc">
                  {items.map((t) => t.name).join("、")}
                </p>
              </div>
            );
          })}
        </div>
      )}

      <Drawer
        open={selected !== null}
        onClose={() => setSelected(null)}
        title={
          <>
            <span>{TOOLSET_EMOJI[selected || ""] || "🔧"}</span>
            <span>{selected}</span>
            <span className="toolset-count">{selectedTools.length} 个工具</span>
          </>
        }
      >
        {selectedTools.map((t) => (
          <div key={t.name} className="drawer-section">
            <div className="drawer-section-title">{t.emoji} {t.name}</div>
            {t.description && (
              <div className="drawer-section-desc">{t.description}</div>
            )}
          </div>
        ))}
      </Drawer>
    </div>
  );
}
