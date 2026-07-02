import { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Plus, Trash2, ToggleLeft, ToggleRight, FlaskConical, RefreshCw, ChevronDown, ChevronRight, Server, Braces, FormInput, Edit3, Wifi, WifiOff, Loader2 } from "lucide-react";
import { api } from "../api/http";
import type { MCPServerStatus, MCPServerConfig, MCPTestResult } from "../types";

const DEFAULT_CONFIG: MCPServerConfig = {
  name: "",
  transport: "stdio",
  command: "",
  args: [],
  url: "",
  headers: {},
  env: {},
  enabled: true,
  timeout: 120,
};

export default function McpPage() {
  const navigate = useNavigate();
  const [servers, setServers] = useState<MCPServerStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [addMode, setAddMode] = useState<"form" | "json">("form");
  const [form, setForm] = useState<MCPServerConfig>({ ...DEFAULT_CONFIG });
  const [jsonText, setJsonText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [testResults, setTestResults] = useState<Record<string, MCPTestResult | null>>({});
  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});
  const [reloading, setReloading] = useState(false);
  const [editingServer, setEditingServer] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<MCPServerConfig>({ ...DEFAULT_CONFIG });
  const [reconnecting, setReconnecting] = useState<Record<string, boolean>>({});
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadServers = useCallback(() => {
    api.get<MCPServerStatus[]>("/mcp/servers").then((data) => {
      setServers(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  useEffect(() => { loadServers(); }, [loadServers]);

  // Auto-poll every 15 seconds
  useEffect(() => {
    pollRef.current = setInterval(loadServers, 15000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [loadServers]);

  const handleAdd = async () => {
    setError("");
    let config: MCPServerConfig;

    if (addMode === "json") {
      try {
        config = JSON.parse(jsonText);
      } catch {
        setError("JSON 格式无效，请检查语法");
        return;
      }
      // Auto-unwrap Claude Code .mcp.json format: {"mcpServers": {"name": {...}}}
      if (config.mcpServers && typeof config.mcpServers === "object") {
        const entries = Object.entries(config.mcpServers as Record<string, any>);
        if (entries.length === 0) { setError("mcpServers 中无服务器配置"); return; }
        const [name, serverCfg] = entries[0];
        if (typeof serverCfg !== "object" || !serverCfg) { setError("mcpServers 中服务器配置无效"); return; }
        config = { name, transport: "stdio", timeout: 120, ...serverCfg };
      }
      if (!config.name?.trim()) { setError("JSON 中缺少必填字段 name"); return; }
    } else {
      if (!form.name.trim()) { setError("服务器名称不能为空"); return; }
      if (form.transport === "stdio" && !form.command?.trim()) { setError("stdio 传输需要填写 command"); return; }
      if (form.transport === "http" && !form.url?.trim()) { setError("HTTP 传输需要填写 url"); return; }
      config = { ...form, args: form.args || [], headers: form.headers || {}, env: form.env || {} };
    }

    setSubmitting(true);
    try {
      await api.post("/mcp/servers", config);
      setShowAdd(false);
      setForm({ ...DEFAULT_CONFIG });
      setJsonText("");
      loadServers();
    } catch (e: any) {
      setError(e.message);
    }
    setSubmitting(false);
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`确认删除 MCP 服务器「${name}」？`)) return;
    try {
      await api.del(`/mcp/servers/${name}`);
    } catch {
      // proceed even if disconnect fails
    }
    loadServers();
  };

  const handleToggle = async (name: string) => {
    try {
      await api.put(`/mcp/servers/${name}/toggle`);
      loadServers();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleTest = async (name: string) => {
    setTestResults((prev) => ({ ...prev, [name]: null }));
    try {
      const result = await api.post<MCPTestResult>(`/mcp/servers/${name}/test`);
      setTestResults((prev) => ({ ...prev, [name]: result }));
    } catch (e: any) {
      setTestResults((prev) => ({ ...prev, [name]: { success: false, tools_discovered: 0, tool_names: [], error_message: e.message } }));
    }
  };

  const handleReconnect = async (name: string) => {
    setReconnecting((prev) => ({ ...prev, [name]: true }));
    try {
      await api.post(`/mcp/servers/${name}/reconnect`);
      loadServers();
    } catch (e: any) {
      setError(e.message);
    }
    setReconnecting((prev) => ({ ...prev, [name]: false }));
  };

  const startEdit = (s: MCPServerStatus) => {
    setEditingServer(s.name);
    setEditForm({
      name: s.name,
      transport: s.transport as "stdio" | "http",
      command: "",
      args: [],
      url: "",
      headers: {},
      env: {},
      enabled: true,
      timeout: 120,
    });
  };

  const saveEdit = async () => {
    if (!editingServer) return;
    setSubmitting(true);
    try {
      await api.put(`/mcp/servers/${editingServer}`, editForm);
      setEditingServer(null);
      loadServers();
    } catch (e: any) {
      setError(e.message);
    }
    setSubmitting(false);
  };

  const handleReload = async () => {
    setReloading(true);
    try {
      await api.post("/mcp/reload");
      loadServers();
    } catch (e: any) {
      setError(e.message);
    }
    setReloading(false);
  };

  const toggleTools = (name: string) => {
    setExpandedTools((prev) => ({ ...prev, [name]: !prev[name] }));
  };

  const statusColor = (status: string) => {
    if (status === "connected") return "var(--success)";
    if (status === "error") return "var(--error)";
    return "var(--text-4)";
  };

  const statusText = (status: string) => {
    if (status === "connected") return "已连接";
    if (status === "error") return "错误";
    return "未连接";
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate("/")}><ArrowLeft size={16} /></button>
        <h1 className="page-title">MCP 服务器</h1>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "16px", flexWrap: "wrap" }}>
        <button className="btn btn-primary" onClick={() => setShowAdd(!showAdd)}>
          <Plus size={14} /> 添加服务器
        </button>
        <button className="btn btn-ghost" onClick={handleReload} disabled={reloading}>
          <RefreshCw size={14} style={{ animation: reloading ? "spin 1s linear infinite" : undefined }} />
          {reloading ? "重载中..." : "重载所有"}
        </button>
        <span style={{ fontSize: "13px", color: "var(--text-3)" }}>共 {servers.length} 个服务器</span>
      </div>

      {error && (
        <div className="toast toast-error" style={{ marginBottom: "12px" }}>
          {error}
          <button onClick={() => setError("")} style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "inherit" }}>×</button>
        </div>
      )}

      {showAdd && (
        <div className="skill-card" style={{ marginBottom: "16px", padding: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
            <h3 style={{ margin: 0, fontSize: "15px", fontWeight: 600 }}>添加 MCP 服务器</h3>
            <div style={{ display: "flex", gap: "4px", background: "var(--bg-2)", borderRadius: "6px", padding: "2px" }}>
              <button
                className={`btn ${addMode === "form" ? "btn-primary" : "btn-ghost"}`}
                style={{ height: "28px", padding: "0 10px", fontSize: "12px" }}
                onClick={() => { setAddMode("form"); setError(""); }}
              >
                <FormInput size={12} /> 表单
              </button>
              <button
                className={`btn ${addMode === "json" ? "btn-primary" : "btn-ghost"}`}
                style={{ height: "28px", padding: "0 10px", fontSize: "12px" }}
                onClick={() => { setAddMode("json"); setError(""); }}
              >
                <Braces size={12} /> JSON
              </button>
            </div>
          </div>

          {addMode === "form" ? (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
              <div>
                <label className="form-label">名称 *</label>
                <input className="form-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="my-mcp-server" />
              </div>
              <div>
                <label className="form-label">传输方式</label>
                <select className="form-input" value={form.transport} onChange={(e) => setForm({ ...form, transport: e.target.value as "stdio" | "http" })}>
                  <option value="stdio">stdio (子进程)</option>
                  <option value="http">HTTP</option>
                </select>
              </div>
              {form.transport === "stdio" ? (
                <>
                  <div>
                    <label className="form-label">Command *</label>
                    <input className="form-input" value={form.command || ""} onChange={(e) => setForm({ ...form, command: e.target.value })} placeholder="npx" />
                  </div>
                  <div>
                    <label className="form-label">Args (逗号分隔)</label>
                    <input className="form-input" value={(form.args || []).join(", ")} onChange={(e) => setForm({ ...form, args: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} placeholder="-y, @playwright/mcp@latest" />
                  </div>
                </>
              ) : (
                <div>
                  <label className="form-label">URL *</label>
                  <input className="form-input" value={form.url || ""} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="http://localhost:3000/mcp" />
                </div>
              )}
              <div>
                <label className="form-label">超时 (秒)</label>
                <input className="form-input" type="number" min={10} max={600} value={form.timeout || 120} onChange={(e) => setForm({ ...form, timeout: Number(e.target.value) })} />
              </div>
            </div>
          ) : (
            <div>
              <label className="form-label">JSON 配置</label>
              <textarea
                className="form-input"
                rows={10}
                style={{ fontFamily: "var(--mono-font, monospace)", fontSize: "12px", resize: "vertical" }}
                value={jsonText}
                onChange={(e) => setJsonText(e.target.value)}
                placeholder={`{
  "name": "playwright",
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@playwright/mcp@latest"],
  "timeout": 120,
  "enabled": true
}`}
              />
              <p style={{ fontSize: "11px", color: "var(--text-4)", marginTop: "4px" }}>
                必填: name、transport，以及对应传输方式的 command (stdio) 或 url (HTTP)
              </p>
            </div>
          )}

          <div style={{ marginTop: "12px", display: "flex", gap: "8px" }}>
            <button className="btn btn-primary" onClick={handleAdd} disabled={submitting}>
              {submitting ? "添加中..." : "添加并连接"}
            </button>
            <button className="btn btn-ghost" onClick={() => { setShowAdd(false); setError(""); setJsonText(""); setAddMode("form"); }}>取消</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="empty-state">
          <Loader2 size={40} className="empty-state-icon spin" style={{ opacity: 0.3 }} />
          <p>加载中...</p>
        </div>
      ) : servers.length === 0 ? (
        <div className="empty-state">
          <Server size={40} className="empty-state-icon" style={{ opacity: 0.3 }} />
          <p>暂无 MCP 服务器，点击上方按钮添加</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {servers.map((s) => (
            <div key={s.name} className="skill-card">
              <div className="skill-card-header">
                <div className="skill-card-name">
                  <span style={{
                    width: "8px",
                    height: "8px",
                    borderRadius: "50%",
                    background: statusColor(s.status),
                    flexShrink: 0,
                  }} />
                  <span style={{ fontSize: "14px", fontWeight: 600 }}>{s.name}</span>
                  <span style={{ fontSize: "11px", color: "var(--text-4)" }}>{s.transport}</span>
                  <span style={{ fontSize: "12px", color: statusColor(s.status) }}>{statusText(s.status)}</span>
                  {s.status === "connected" && (
                    <span style={{ fontSize: "12px", color: "var(--text-3)" }}>{s.tool_count} 个工具</span>
                  )}
                </div>
                <div className="skill-card-actions">
                  <button
                    className="btn btn-ghost"
                    style={{ height: "28px", width: "28px", padding: "0", justifyContent: "center" }}
                    onClick={() => handleTest(s.name)}
                    title="测试连接"
                  >
                    <FlaskConical size={14} color="var(--text-3)" />
                  </button>
                  <button
                    className="btn btn-ghost"
                    style={{ height: "28px", width: "28px", padding: "0", justifyContent: "center" }}
                    onClick={() => startEdit(s)}
                    title="编辑配置"
                  >
                    <Edit3 size={13} color="var(--text-3)" />
                  </button>
                  <button
                    className="btn btn-ghost"
                    style={{ height: "28px", width: "28px", padding: "0", justifyContent: "center" }}
                    onClick={() => handleReconnect(s.name)}
                    disabled={reconnecting[s.name]}
                    title="重新连接"
                  >
                    {reconnecting[s.name] ? <Loader2 size={14} className="spin" /> : <WifiOff size={14} color="var(--text-3)" />}
                  </button>
                  <button
                    className="btn btn-ghost"
                    style={{ height: "28px", width: "28px", padding: "0", justifyContent: "center" }}
                    onClick={() => handleToggle(s.name)}
                    title={s.enabled ? "停用" : "启用"}
                  >
                    {s.enabled ? <ToggleRight size={16} color="var(--success)" /> : <ToggleLeft size={16} color="var(--text-4)" />}
                  </button>
                  <button
                    className="btn btn-ghost"
                    style={{ height: "28px", width: "28px", padding: "0", justifyContent: "center" }}
                    onClick={() => handleDelete(s.name)}
                    title="删除服务器"
                  >
                    <Trash2 size={14} color="var(--text-3)" />
                  </button>
                </div>
              </div>

              {s.error_message && (
                <p className="skill-card-desc" style={{ color: "var(--error)" }}>{s.error_message}</p>
              )}

              {testResults[s.name] !== undefined && testResults[s.name] !== null && (
                <div style={{ marginTop: "8px", padding: "8px 12px", background: "var(--bg-2)", borderRadius: "6px", fontSize: "13px" }}>
                  {testResults[s.name]!.success ? (
                    <>
                      <span style={{ color: "var(--success)", fontWeight: 600 }}>测试通过</span>
                      <span style={{ color: "var(--text-3)", marginLeft: "8px" }}>
                        发现 {testResults[s.name]!.tools_discovered} 个工具
                      </span>
                      <button
                        className="action-link"
                        style={{ marginLeft: "8px" }}
                        onClick={() => toggleTools(s.name)}
                      >
                        {expandedTools[s.name] ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                        {expandedTools[s.name] ? "收起" : "展开"}
                      </button>
                      {expandedTools[s.name] && (
                        <div style={{ marginTop: "4px", display: "flex", flexWrap: "wrap", gap: "4px" }}>
                          {testResults[s.name]!.tool_names.map((t) => (
                            <span key={t} className="skill-card-tag">{t}</span>
                          ))}
                        </div>
                      )}
                    </>
                  ) : (
                    <span style={{ color: "var(--error)" }}>测试失败: {testResults[s.name]!.error_message}</span>
                  )}
                </div>
              )}

              {editingServer === s.name && (
                <div style={{ marginTop: "12px", padding: "12px", background: "var(--bg-2)", borderRadius: "6px" }}>
                  <h4 style={{ margin: "0 0 12px", fontSize: "14px", fontWeight: 600 }}>编辑配置</h4>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                    <div>
                      <label className="form-label">名称</label>
                      <input className="form-input" value={editForm.name} disabled />
                    </div>
                    <div>
                      <label className="form-label">传输方式</label>
                      <select className="form-input" value={editForm.transport} onChange={(e) => setEditForm({ ...editForm, transport: e.target.value as "stdio" | "http" })}>
                        <option value="stdio">stdio (子进程)</option>
                        <option value="http">HTTP</option>
                      </select>
                    </div>
                    {editForm.transport === "stdio" ? (
                      <>
                        <div>
                          <label className="form-label">Command</label>
                          <input className="form-input" value={editForm.command || ""} onChange={(e) => setEditForm({ ...editForm, command: e.target.value })} />
                        </div>
                        <div>
                          <label className="form-label">Args (逗号分隔)</label>
                          <input className="form-input" value={(editForm.args || []).join(", ")} onChange={(e) => setEditForm({ ...editForm, args: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} />
                        </div>
                      </>
                    ) : (
                      <div>
                        <label className="form-label">URL</label>
                        <input className="form-input" value={editForm.url || ""} onChange={(e) => setEditForm({ ...editForm, url: e.target.value })} />
                      </div>
                    )}
                    <div>
                      <label className="form-label">超时 (秒)</label>
                      <input className="form-input" type="number" min={10} max={600} value={editForm.timeout || 120} onChange={(e) => setEditForm({ ...editForm, timeout: Number(e.target.value) })} />
                    </div>
                  </div>
                  <div style={{ marginTop: "12px", display: "flex", gap: "8px" }}>
                    <button className="btn btn-primary" onClick={saveEdit} disabled={submitting}>
                      {submitting ? "保存中..." : "保存并重连"}
                    </button>
                    <button className="btn btn-ghost" onClick={() => setEditingServer(null)}>取消</button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
