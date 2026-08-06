import { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { IconArrowLeft, IconPlus, IconTrash, IconToggleLeft, IconToggleRight, IconPlayerPlay, IconRefresh, IconChevronDown, IconChevronRight, IconServer, IconCode, IconForms, IconEdit, IconLoader } from "@tabler/icons-react";
import { api } from "../api/http";
import { getErrorMessage } from "../utils/errors";
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
  const [editJsonMode, setEditJsonMode] = useState<"form" | "json">("form");
  const [editJsonText, setEditJsonText] = useState("");
  const [reconnecting, setReconnecting] = useState<Record<string, boolean>>({});
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadServers = useCallback(() => {
    const start = Date.now();
    api.get<MCPServerStatus[]>("/mcp/servers").then((data) => {
      setServers(data);
      const elapsed = Date.now() - start;
      if (elapsed < 300) setTimeout(() => setLoading(false), 300 - elapsed);
      else setLoading(false);
    }).catch(() => setTimeout(() => setLoading(false), 300));
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
        config = JSON.parse(jsonText) as MCPServerConfig;
      } catch {
        setError("JSON 格式无效，请检查语法");
        return;
      }
      // Auto-unwrap Claude Code .mcp.json format: {"mcpServers": {"name": {...}}}
      const raw = JSON.parse(jsonText) as Record<string, unknown>;
      if (raw.mcpServers && typeof raw.mcpServers === "object") {
        const entries = Object.entries(raw.mcpServers as Record<string, object>);
        if (entries.length === 0) { setError("mcpServers 中无服务器配置"); return; }
        const [name, serverCfg] = entries[0];
        if (typeof serverCfg !== "object" || !serverCfg) { setError("mcpServers 中服务器配置无效"); return; }
        config = { name, transport: "stdio", timeout: 120, ...serverCfg } as MCPServerConfig;
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
    } catch (e: unknown) {
      setError(getErrorMessage(e));
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
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
  };

  const handleTest = async (name: string) => {
    setTestResults((prev) => ({ ...prev, [name]: null }));
    try {
      const result = await api.post<MCPTestResult>(`/mcp/servers/${name}/test`);
      setTestResults((prev) => ({ ...prev, [name]: result }));
    } catch (e: unknown) {
      setTestResults((prev) => ({ ...prev, [name]: { success: false, tools_discovered: 0, tool_names: [], error_message: getErrorMessage(e) } }));
    }
  };

  const handleReconnect = async (name: string) => {
    setReconnecting((prev) => ({ ...prev, [name]: true }));
    try {
      await api.post(`/mcp/servers/${name}/reconnect`);
      loadServers();
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
    setReconnecting((prev) => ({ ...prev, [name]: false }));
  };

  const startEdit = (s: MCPServerStatus) => {
    setEditingServer(s.name);
    setEditJsonMode("form");
    const cfg: MCPServerConfig = {
      name: s.name,
      transport: s.transport as "stdio" | "http",
      command: s.command || "",
      args: s.args || [],
      url: s.url || "",
      headers: s.headers || {},
      env: s.env || {},
      enabled: s.enabled ?? true,
      timeout: s.timeout ?? 120,
    };
    setEditForm(cfg);
    setEditJsonText(JSON.stringify(cfg, null, 2));
  };

  const saveEdit = async () => {
    if (!editingServer) return;
    setSubmitting(true);
    setError("");
    let config: MCPServerConfig;

    if (editJsonMode === "json") {
      try {
        config = JSON.parse(editJsonText);
      } catch {
        setError("JSON 格式无效，请检查语法");
        setSubmitting(false);
        return;
      }
      if (!config.name?.trim()) {
        setError("JSON 中缺少必填字段 name");
        setSubmitting(false);
        return;
      }
    } else {
      config = { ...editForm };
    }

    try {
      await api.put(`/mcp/servers/${editingServer}`, config);
      setEditingServer(null);
      loadServers();
    } catch (e: unknown) {
      setError(getErrorMessage(e));
    }
    setSubmitting(false);
  };

  const handleReload = async () => {
    setReloading(true);
    try {
      await api.post("/mcp/reload");
      loadServers();
    } catch (e: unknown) {
      setError(getErrorMessage(e));
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
        <button className="back-btn" onClick={() => navigate("/")}><IconArrowLeft size={16} /></button>
        <h1 className="page-title">MCP 服务器</h1>
      </div>

      <div className="toolbar-md">
        <button className="btn btn-primary" onClick={() => setShowAdd(!showAdd)}>
          <IconPlus size={14} /> 添加服务器
        </button>
        <button className="btn btn-ghost" onClick={handleReload} disabled={reloading}>
          {/* dynamic: reloading */}
          <IconRefresh size={14} style={{ animation: reloading ? "spin 1s linear infinite" : undefined }} />
          {reloading ? "重载中..." : "重载所有"}
        </button>
        <span className="text-meta">共 {servers.length} 个服务器</span>
      </div>

      {error && (
        <div className="toast toast-error mb-md">
          {error}
          <button onClick={() => setError("")} className="toast-close">×</button>
        </div>
      )}

      {showAdd && (
        <div className="skill-card mb-lg p-md">
          <div className="flex-between">
            <h3 className="card-title-sm">添加 MCP 服务器</h3>
            <div className="seg-group">
              <button
                className={`btn ${addMode === "form" ? "btn-primary" : "btn-ghost"} seg-btn`}
                onClick={() => { setAddMode("form"); setError(""); }}
              >
                <IconForms size={12} /> 表单
              </button>
              <button
                className={`btn ${addMode === "json" ? "btn-primary" : "btn-ghost"} seg-btn`}
                onClick={() => { setAddMode("json"); setError(""); }}
              >
                <IconCode size={12} /> JSON
              </button>
            </div>
          </div>

          <div className="mb-lg">
            <span className="label-sm">推荐预设</span>
            <div className="chip-row">
              <button className="btn btn-ghost btn-xs"
                onClick={() => {
                  setForm({ name: "mcp-server-chart", transport: "stdio", command: "npx", args: ["-y", "@antv/mcp-server-chart"], url: "", headers: {}, env: {}, enabled: true, timeout: 120 });
                  setAddMode("form");
                }}>
                📊 Chart 图表
              </button>
              <button className="btn btn-ghost btn-xs"
                onClick={() => {
                  setJsonText(JSON.stringify({ name: "playwright", transport: "stdio", command: "npx", args: ["-y", "@playwright/mcp@latest"], timeout: 120, enabled: true }, null, 2));
                  setAddMode("json");
                }}>
                🌐 Playwright 浏览器
              </button>
              <button className="btn btn-ghost btn-xs"
                onClick={() => {
                  setForm({ name: "my-mcp-server", transport: "stdio", command: "", args: [], url: "", headers: {}, env: {}, enabled: true, timeout: 120 });
                  setAddMode("form");
                }}>
                ✏️ 自定义
              </button>
            </div>
          </div>

          {addMode === "form" ? (
            <div className="grid-2">
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
                className="form-input mono-input"
                rows={14}
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
              <p className="text-tiny-mt">
                必填: name、transport，以及对应传输方式的 command (stdio) 或 url (HTTP)
              </p>
            </div>
          )}

          <div className="row-actions">
            <button className="btn btn-primary" onClick={handleAdd} disabled={submitting}>
              {submitting ? "添加中..." : "添加并连接"}
            </button>
            <button className="btn btn-ghost" onClick={() => { setShowAdd(false); setError(""); setJsonText(""); setAddMode("form"); }}>取消</button>
          </div>
        </div>
      )}

      {loading ? (
        <>
          <div className="skeleton skeleton-title" />
          <div className="skeleton skeleton-text" style={{ width: "60%", marginBottom: 24 }} />
          <div className="skeleton skeleton-card" />
          <div className="skeleton skeleton-card" />
        </>
      ) : servers.length === 0 ? (
        <div className="empty-state">
          <IconServer size={40} className="empty-state-icon empty-state-icon-dim" />
          <p>暂无 MCP 服务器，点击上方按钮添加</p>
        </div>
      ) : (
        <div className="flex-col-gap">
          {servers.map((s) => (
            <div key={s.name} className="skill-card">
              <div className="skill-card-header">
                <div className="skill-card-name">
                  <span style={{
                    width: "8px",
                    height: "8px",
                    borderRadius: "50%",
                    background: statusColor(s.status), // dynamic: statusColor
                    flexShrink: 0,
                  }} />
                  <span className="text-name">{s.name}</span>
                  {s.builtin && (
                    <span className="badge badge-primary badge-xs">内置</span>
                  )}
                  <span className="text-tiny">{s.transport}</span>
                  <span style={{ fontSize: "12px", color: statusColor(s.status) /* dynamic: statusColor */ }}>{statusText(s.status)}</span>
                  {s.status === "connected" && (
                    <span className="text-hint">{s.tool_count} 个工具</span>
                  )}
                </div>
                <div className="skill-card-actions">
                  <button
                    className="btn btn-ghost icon-btn-sm"
                    onClick={() => handleTest(s.name)}
                    title="测试连接"
                  >
                    <IconPlayerPlay size={13} color="var(--primary)" />
                  </button>
                  {!s.builtin && (
                    <button
                      className="btn btn-ghost icon-btn-sm"
                      onClick={() => startEdit(s)}
                      title="编辑配置"
                    >
                      <IconEdit size={13} color="var(--text-3)" />
                    </button>
                  )}
                  <button
                    className="btn btn-ghost icon-btn-sm"
                    onClick={() => handleReconnect(s.name)}
                    disabled={reconnecting[s.name]}
                    title="重新连接"
                  >
                    {reconnecting[s.name] ? <IconLoader size={14} className="spin" /> : <IconRefresh size={13} color="var(--text-3)" />}
                  </button>
                  <button
                    className="btn btn-ghost icon-btn-sm"
                    onClick={() => handleToggle(s.name)}
                    title={s.enabled ? "停用" : "启用"}
                  >
                    {s.enabled ? <IconToggleRight size={16} color="var(--success)" /> : <IconToggleLeft size={16} color="var(--text-4)" />}
                  </button>
                  {!s.builtin && (
                    <button
                      className="btn btn-ghost icon-btn-sm"
                      onClick={() => handleDelete(s.name)}
                      title="删除服务器"
                    >
                      <IconTrash size={14} color="var(--text-3)" />
                    </button>
                  )}
                </div>
              </div>

              {s.error_message && (
                <p className="skill-card-desc" style={{ color: "var(--error)" /* --error 未定义，当前为继承父级颜色，保持现状 */ }}>{s.error_message}</p>
              )}

              {testResults[s.name] !== undefined && testResults[s.name] !== null && (
                <div className="test-panel">
                  {testResults[s.name]!.success ? (
                    <>
                      <span className="text-success">测试通过</span>
                      <span className="text-muted ml-sm">
                        发现 {testResults[s.name]!.tools_discovered} 个工具
                      </span>
                      <button
                        className="action-link ml-sm"
                        onClick={() => toggleTools(s.name)}
                      >
                        {expandedTools[s.name] ? <IconChevronDown size={12} /> : <IconChevronRight size={12} />}
                        {expandedTools[s.name] ? "收起" : "展开"}
                      </button>
                      {expandedTools[s.name] && (
                        <div className="tag-row">
                          {testResults[s.name]!.tool_names.map((t) => (
                            <span key={t} className="skill-card-tag">{t}</span>
                          ))}
                        </div>
                      )}
                    </>
                  ) : (
                    <span style={{ color: "var(--error)" /* --error 未定义，当前为继承父级颜色，保持现状 */ }}>测试失败: {testResults[s.name]!.error_message}</span>
                  )}
                </div>
              )}

              {editingServer === s.name && (
                <div className="panel-pad">
                  <div className="flex-between">
                    <h4 className="card-title-xs">编辑配置</h4>
                    <div className="seg-group-page">
                      <button
                        className={`btn ${editJsonMode === "form" ? "btn-primary" : "btn-ghost"} icon-btn-xs`}
                        onClick={() => { setEditJsonMode("form"); setError(""); }}
                      >
                        <IconForms size={11} /> 表单
                      </button>
                      <button
                        className={`btn ${editJsonMode === "json" ? "btn-primary" : "btn-ghost"} icon-btn-xs`}
                        onClick={() => { setEditJsonMode("json"); setError(""); }}
                      >
                        <IconCode size={11} /> JSON
                      </button>
                    </div>
                  </div>

                  {editJsonMode === "json" ? (
                    <div>
                      <textarea
                        className="form-input mono-input"
                        rows={14}
                        value={editJsonText}
                        onChange={(e) => setEditJsonText(e.target.value)}
                      />
                    </div>
                  ) : (
                  <div className="grid-2-sm">
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
                  )}
                  <div className="row-actions">
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
