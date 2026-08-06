import { useEffect, useState, useRef, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { IconArrowLeft, IconUpload, IconPackage, IconChevronDown, IconSearch, IconEdit, IconDownload, IconX } from "@tabler/icons-react";
import { api } from "../api/http";
import { getErrorMessage } from "../utils/errors";
import type { SkillInfo } from "../types";

export default function SkillManagerPage() {
  const navigate = useNavigate();
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [skillContent, setSkillContent] = useState<Record<string, string>>({});
  const [uploading, setUploading] = useState(false);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [saving, setSaving] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadSkills = () => {
    const start = Date.now();
    api.get<SkillInfo[]>("/skills").then(setSkills).finally(() => {
      const elapsed = Date.now() - start;
      if (elapsed < 300) setTimeout(() => setLoading(false), 300 - elapsed);
      else setLoading(false);
    });
  };

  useEffect(() => { loadSkills(); }, []);

  const filtered = useMemo(() => {
    if (!search.trim()) return skills;
    const q = search.toLowerCase();
    return skills.filter((s) =>
      s.name.toLowerCase().includes(q) ||
      (s.description || "").toLowerCase().includes(q) ||
      s.tags.some((t) => t.toLowerCase().includes(q))
    );
  }, [skills, search]);

  const handleExpand = async (name: string) => {
    if (!skillContent[name]) {
      const data = await api.get<{ name: string; content: string }>(`/skills/${name}`);
      setSkillContent((prev) => ({ ...prev, [name]: data.content }));
    }
    setExpanded((prev) => ({ ...prev, [name]: !prev[name] }));
  };

  const handleEdit = async (name: string) => {
    if (!skillContent[name]) {
      const data = await api.get<{ name: string; content: string }>(`/skills/${name}`);
      setSkillContent((prev) => ({ ...prev, [name]: data.content }));
    }
    setEditing(name);
    setEditContent(skillContent[name] || "");
  };

  const handleSave = async (name: string) => {
    setSaving(true);
    try {
      await api.put(`/skills/${name}`, { content: editContent });
      setSkillContent((prev) => ({ ...prev, [name]: editContent }));
      setEditing(null);
    } catch (e: unknown) {
      alert(getErrorMessage(e, "保存失败"));
    }
    setSaving(false);
  };

  const handleExport = (name: string, content: string) => {
    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${name}-SKILL.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch("/api/skills/install", { method: "POST", body: formData });
      const data = await res.json();
      if (res.ok) {
        alert(`技能「${data.skill_name}」安装成功！`);
        loadSkills();
      } else {
        alert(data.detail || "安装失败");
      }
    } catch {
      alert("安装失败");
    }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate("/")}><IconArrowLeft size={16} /></button>
        <h1 className="page-title">技能管理</h1>
      </div>

      <div className="toolbar-lg">
        <label className="btn btn-primary" style={{ padding: "0 16px", cursor: "pointer" }}>
          <IconUpload size={14} />
          {uploading ? "安装中..." : "安装技能"}
          <input ref={fileRef} type="file" accept=".zip" onChange={handleUpload} style={{ display: "none" }} />
        </label>
        <div className="search-input-wrap" style={{ flex: "1", minWidth: "200px" }}>
          <IconSearch size={14} className="search-input-icon" />
          <input
            className="search-input"
            placeholder="搜索技能名称、描述或标签..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <span className="text-meta">
          {search.trim() ? `找到 ${filtered.length} 个` : `共 ${skills.length} 个技能`}
        </span>
      </div>

      {loading ? (
        <div className="skill-grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 140, borderRadius: "var(--radius-lg)" }} />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <IconPackage size={40} className="empty-state-icon empty-state-icon-dim" />
          <p>暂无已安装的技能，点击上方按钮上传 .zip 技能包</p>
        </div>
      ) : (
        <div className="skill-grid">
          {filtered.map((s) => (
            <div key={s.name} className="skill-card">
              <div className="skill-card-header">
                <div className="skill-card-name">
                  <span style={{
                    width: "8px",
                    height: "8px",
                    borderRadius: "50%",
                    background: s.active ? "var(--success)" : "var(--text-4)",
                    flexShrink: 0,
                  }} />
                  <span className="text-name">{s.name}</span>
                  {s.version && (
                    <span className="text-tiny">v{s.version}</span>
                  )}
                  {s.builtin && (
                    <span className="badge badge-primary badge-xs">内置</span>
                  )}
                </div>
                <div className="skill-card-actions">
                  {!s.builtin && (
                    <button
                      className="btn btn-ghost icon-btn-sm"
                      onClick={() => handleEdit(s.name)}
                      title="编辑内容"
                    >
                      <IconEdit size={13} color="var(--text-3)" />
                    </button>
                  )}
                  <button
                    className="btn btn-ghost icon-btn-sm"
                    onClick={() => handleExpand(s.name)}
                    title="查看详情"
                  >
                    <IconChevronDown
                      size={14}
                      style={{
                        transition: "transform 0.2s",
                        transform: expanded[s.name] ? "rotate(180deg)" : "rotate(0)",
                        color: "var(--text-3)",
                      }}
                    />
                  </button>
                </div>
              </div>

              {s.description && (
                <p className="skill-card-desc">{s.description}</p>
              )}

              {s.tags.length > 0 && (
                <div className="skill-card-tags">
                  {s.tags.map((tag) => (
                    <span key={tag} className="skill-card-tag">{tag}</span>
                  ))}
                </div>
              )}

              {expanded[s.name] && (
                <div className="skill-card-body">
                  {editing === s.name ? (
                    <div className="flex-col-gap-sm">
                      <textarea
                        className="editor-textarea"
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                      />
                      <div className="flex-row-gap-sm">
                        <button className="btn btn-primary" onClick={() => handleSave(s.name)} disabled={saving}>
                          {saving ? "保存中..." : "保存"}
                        </button>
                        <button className="btn btn-ghost" onClick={() => setEditing(null)} disabled={saving}>
                          <IconX size={14} /> 取消
                        </button>
                      </div>
                    </div>
                  ) : skillContent[s.name] ? (
                    <>
                      <div style={{ display: "flex", gap: "4px", marginBottom: "8px" }}>
                        <button
                          className="action-link"
                          onClick={() => handleExport(s.name, skillContent[s.name])}
                        >
                          <IconDownload size={12} /> 导出
                        </button>
                      </div>
                      <pre>{skillContent[s.name]}</pre>
                    </>
                  ) : (
                    <span className="text-tiny">加载中...</span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
