import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { IconArrowLeft, IconFileText, IconUser, IconClipboardList } from "@tabler/icons-react";
import { api } from "../api/http";
import Drawer from "../components/Drawer";
import type { MemoryFacts, MemorySummary } from "../types";

const SECTIONS = [
  { key: "notes", icon: IconFileText, label: "Agent 笔记" },
  { key: "profile", icon: IconUser, label: "用户画像" },
  { key: "summaries", icon: IconClipboardList, label: "对话摘要" },
] as const;

type SectionKey = (typeof SECTIONS)[number]["key"];

export default function MemoryPage() {
  const navigate = useNavigate();
  const [facts, setFacts] = useState<MemoryFacts>({ memory: [], user: [] });
  const [summaries, setSummaries] = useState<MemorySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<SectionKey | null>(null);

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

  const counts: Record<SectionKey, number> = {
    notes: facts.memory.length,
    profile: facts.user.length,
    summaries: summaries.length,
  };

  const emptyTexts: Record<SectionKey, string> = {
    notes: "暂无笔记",
    profile: "暂无画像",
    summaries: "暂无摘要",
  };

  const total = counts.notes + counts.profile + counts.summaries;
  const selectedSection = SECTIONS.find((s) => s.key === selected);

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
      <div className="toolbar-md">
        <span className="text-meta">
          共 {total} 条记忆，{SECTIONS.length} 个分类
        </span>
      </div>

      <div className="card-grid">
        {SECTIONS.map(({ key, icon: Icon, label }) => (
          <div
            key={key}
            className="skill-card"
            style={{ cursor: "pointer" }}
            onClick={() => setSelected(key)}
          >
            <div className="skill-card-header">
              <div className="skill-card-name">
                <Icon size={14} />
                <span className="text-name">{label}</span>
                <span className="toolset-count">{counts[key]} 条</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <Drawer
        open={selected !== null}
        onClose={() => setSelected(null)}
        title={
          selectedSection && (
            <>
              <selectedSection.icon size={15} />
              <span>{selectedSection.label}</span>
              <span className="toolset-count">{counts[selectedSection.key]} 条</span>
            </>
          )
        }
      >
        {selected && counts[selected] === 0 ? (
          <div className="text-meta">{emptyTexts[selected]}</div>
        ) : selected === "summaries" ? (
          summaries.map((s) => (
            <div key={s.session_id} className="drawer-section">
              <div className="drawer-section-title">{s.title}</div>
              <div className="drawer-section-desc">{s.summary}</div>
            </div>
          ))
        ) : selected ? (
          <div className="flex-col-gap-sm">
            {(selected === "notes" ? facts.memory : facts.user).map((e, i) => (
              <div key={i} className="chip">{e}</div>
            ))}
          </div>
        ) : null}
      </Drawer>
        </>
      )}
    </div>
  );
}
