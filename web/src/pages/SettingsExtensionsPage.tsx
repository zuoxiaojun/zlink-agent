import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, ToggleLeft, ToggleRight, Plug, RefreshCw } from "lucide-react";
import { api } from "../api/http";
import { getErrorMessage } from "../utils/errors";
import type { ExtensionInfo, ExtensionReloadResult } from "../types";

const KIND_LABEL: Record<ExtensionInfo["kind"], string> = {
  log: "日志",
  policy: "策略",
  transform: "转换",
  other: "其他",
};

const KIND_COLOR: Record<ExtensionInfo["kind"], string> = {
  log: "var(--blue)",
  policy: "var(--orange)",
  transform: "var(--success)",
  other: "var(--text-3)",
};

export default function SettingsExtensionsPage() {
  const navigate = useNavigate();
  const [extensions, setExtensions] = useState<ExtensionInfo[]>([]);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const load = () => api.get<ExtensionInfo[]>("/extensions").then(setExtensions);
  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    if (!search.trim()) return extensions;
    const q = search.toLowerCase();
    return extensions.filter((e) =>
      e.name.toLowerCase().includes(q) ||
      (e.description || "").toLowerCase().includes(q)
    );
  }, [extensions, search]);

  const handleToggle = async (ext: ExtensionInfo) => {
    setBusy(true);
    try {
      const updated = await api.put<ExtensionInfo>(
        `/extensions/${encodeURIComponent(ext.name)}/toggle`,
        { enabled: !ext.enabled },
      );
      setExtensions((prev) =>
        prev.map((e) => (e.name === updated.name ? updated : e))
      );
      setToast(updated.enabled ? `「${updated.name}」已启用` : `「${updated.name}」已停用`);
      setTimeout(() => setToast(null), 2500);
    } catch (e: unknown) {
      setToast(`操作失败: ${getErrorMessage(e)}`);
      setTimeout(() => setToast(null), 3500);
    } finally {
      setBusy(false);
    }
  };

  const handleReload = async () => {
    setBusy(true);
    try {
      const result = await api.post<ExtensionReloadResult>("/extensions/reload");
      const msg = `已重载：新增 ${result.now_active.length} 个，停用 ${result.now_disabled.length} 个`;
      setToast(msg);
      setTimeout(() => setToast(null), 2500);
      await load();
    } catch (e: unknown) {
      setToast(`重载失败: ${getErrorMessage(e)}`);
      setTimeout(() => setToast(null), 3500);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate("/")}><ArrowLeft size={16} /></button>
        <h1 className="page-title">扩展管理</h1>
      </div>

      {toast && (
        <div className="toast toast-success" style={{ marginBottom: "16px" }}>
          {toast}
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "20px", flexWrap: "wrap" }}>
        <input
          className="form-input"
          style={{ maxWidth: "280px" }}
          placeholder="搜索扩展名称或描述"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <span style={{ fontSize: "13px", color: "var(--text-3)" }}>
          {search.trim() ? `找到 ${filtered.length} 个` : `共 ${extensions.length} 个扩展`}
        </span>
        <button
          className="btn btn-secondary"
          onClick={handleReload}
          disabled={busy}
          style={{ marginLeft: "auto" }}
        >
          <RefreshCw size={14} /> 从配置文件重载
        </button>
      </div>

      {extensions.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <Plug size={40} className="empty-state-icon" style={{ opacity: 0.3 }} />
            <p>暂无已注册的扩展。重启后端服务以触发内置扩展自动注册。</p>
          </div>
        </div>
      ) : filtered.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <p>没有匹配「{search}」的扩展</p>
          </div>
        </div>
      ) : (
        <div className="skill-grid">
          {filtered.map((ext) => (
            <div key={ext.name} className="skill-card">
              <div className="skill-card-header">
                <div className="skill-card-name">
                  <span
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      background: ext.enabled ? "var(--success)" : "var(--text-4)",
                      flexShrink: 0,
                    }}
                  />
                  <span style={{ fontSize: "14px", fontWeight: 600 }}>{ext.name}</span>
                  <span
                    className="badge"
                    style={{
                      background: KIND_COLOR[ext.kind],
                      color: "#fff",
                      fontSize: "10px",
                      padding: "1px 6px",
                      borderRadius: "4px",
                      fontWeight: 500,
                    }}
                  >
                    {KIND_LABEL[ext.kind]}
                  </span>
                </div>
                <div className="skill-card-actions">
                  <button
                    className="btn btn-ghost"
                    style={{ height: "28px", width: "28px", padding: 0, justifyContent: "center" }}
                    onClick={() => handleToggle(ext)}
                    disabled={busy}
                    title={ext.enabled ? "停用" : "启用"}
                  >
                    {ext.enabled ? (
                      <ToggleRight size={16} color="var(--success)" />
                    ) : (
                      <ToggleLeft size={16} color="var(--text-4)" />
                    )}
                  </button>
                </div>
              </div>
              <div style={{ padding: "0 14px 14px", fontSize: "12px", color: "var(--text-3)", lineHeight: 1.6 }}>
                {ext.description || "（暂无描述）"}
              </div>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: "24px", fontSize: "12px", color: "var(--text-3)", lineHeight: 1.6 }}>
        <strong>说明：</strong>
        <ul style={{ marginTop: "6px", paddingLeft: "20px" }}>
          <li>停用会立即从事件总线摘除，无需重启服务</li>
          <li>状态保存在 <code>config.json</code> 的 <code>disabled_extensions</code> 字段</li>
          <li>"策略"类扩展（如 security-event）和 <code>agent/tools/security_hooks.py</code> 的 registry 钩子<strong>并行工作</strong>，互相作为冗余备份</li>
          <li>新增内置扩展需在 <code>agent/extensions/__init__.py</code> 的 <code>_built_in_classes()</code> 列表里追加</li>
        </ul>
      </div>
    </div>
  );
}
