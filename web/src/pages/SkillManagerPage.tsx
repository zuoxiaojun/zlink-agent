import { useEffect, useState, useRef, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Upload, Package, ToggleLeft, ToggleRight, Trash2, ChevronDown, Search, Edit3, Download, X } from "lucide-react";
import { api } from "../api/http";
import { getErrorMessage } from "../utils/errors";
import type { SkillInfo } from "../types";

export default function SkillManagerPage() {
  const navigate = useNavigate();
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [skillContent, setSkillContent] = useState<Record<string, string>>({});
  const [uploading, setUploading] = useState(false);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [saving, setSaving] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadSkills = () => api.get<SkillInfo[]>("/skills").then(setSkills);

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

  const handleToggle = async (name: string, active: boolean) => {
    await api.put(`/skills/${name}/toggle`, { active: !active });
    loadSkills();
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`确认删除技能「${name}」？此操作不可撤销。`)) return;
    await api.del(`/skills/${name}`);
    loadSkills();
  };

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
        <button className="back-btn" onClick={() => navigate("/")}><ArrowLeft size={16} /></button>
        <h1 className="page-title">技能管理</h1>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "16px", marginBottom: "20px", flexWrap: "wrap" }}>
        <label className="btn btn-primary" style={{ padding: "0 16px", cursor: "pointer" }}>
          <Upload size={14} />
          {uploading ? "安装中..." : "安装技能"}
          <input ref={fileRef} type="file" accept=".zip" onChange={handleUpload} style={{ display: "none" }} />
        </label>
        <div className="search-input-wrap" style={{ flex: "1", minWidth: "200px" }}>
          <Search size={14} className="search-input-icon" />
          <input
            className="search-input"
            placeholder="搜索技能名称、描述或标签..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <span style={{ fontSize: "13px", color: "var(--text-3)" }}>
          {search.trim() ? `找到 ${filtered.length} 个` : `共 ${skills.length} 个技能`}
        </span>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">
          <Package size={40} className="empty-state-icon" style={{ opacity: 0.3 }} />
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
                  <span style={{ fontSize: "14px", fontWeight: 600 }}>{s.name}</span>
                  {s.version && (
                    <span style={{ fontSize: "11px", color: "var(--text-4)" }}>v{s.version}</span>
                  )}
                </div>
                <div className="skill-card-actions">
                  <button
                    className="btn btn-ghost"
                    style={{ height: "28px", width: "28px", padding: "0", justifyContent: "center" }}
                    onClick={() => handleEdit(s.name)}
                    title="编辑内容"
                  >
                    <Edit3 size={13} color="var(--text-3)" />
                  </button>
                  <button
                    className="btn btn-ghost"
                    style={{ height: "28px", width: "28px", padding: "0", justifyContent: "center" }}
                    onClick={() => handleExpand(s.name)}
                    title="查看详情"
                  >
                    <ChevronDown
                      size={14}
                      style={{
                        transition: "transform 0.2s",
                        transform: expanded[s.name] ? "rotate(180deg)" : "rotate(0)",
                        color: "var(--text-3)",
                      }}
                    />
                  </button>
                  <button
                    className="btn btn-ghost"
                    style={{ height: "28px", width: "28px", padding: "0", justifyContent: "center" }}
                    onClick={() => handleToggle(s.name, s.active)}
                    title={s.active ? "停用" : "启用"}
                  >
                    {s.active ? <ToggleRight size={16} color="var(--success)" /> : <ToggleLeft size={16} color="var(--text-4)" />}
                  </button>
                  <button
                    className="btn btn-ghost"
                    style={{ height: "28px", width: "28px", padding: "0", justifyContent: "center" }}
                    onClick={() => handleDelete(s.name)}
                    title="删除技能"
                  >
                    <Trash2 size={14} color="var(--text-3)" />
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
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                      <textarea
                        style={{
                          width: "100%", minHeight: "300px",
                          fontFamily: "var(--mono-font, monospace)", fontSize: "12px",
                          padding: "8px", borderRadius: "6px",
                          border: "1px solid var(--border)",
                          background: "var(--bg)",
                          color: "var(--text)",
                          resize: "vertical",
                        }}
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                      />
                      <div style={{ display: "flex", gap: "8px" }}>
                        <button className="btn btn-primary" onClick={() => handleSave(s.name)} disabled={saving}>
                          {saving ? "保存中..." : "保存"}
                        </button>
                        <button className="btn btn-ghost" onClick={() => setEditing(null)} disabled={saving}>
                          <X size={14} /> 取消
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
                          <Download size={12} /> 导出
                        </button>
                      </div>
                      <pre>{skillContent[s.name]}</pre>
                    </>
                  ) : (
                    <span style={{ fontSize: "12px", color: "var(--text-4)" }}>加载中...</span>
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
