import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { IconPlus, IconTrash, IconPlayerPlay, IconPlayerPause, IconRefresh, IconPlayerPlayFilled, IconEdit } from "@tabler/icons-react";
import { api } from "../api/http";

interface CronJob {
  id: string;
  name: string;
  schedule: string;
  prompt: string;
  enabled: boolean;
  last_run_at: string | null;
  last_status: string | null;
  last_session_id: string | null;
  next_run_at: string | null;
  created_at: string;
}

export default function CronJobPage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<CronJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", schedule: "", prompt: "" });
  const [error, setError] = useState("");
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);
  const [runLoading, setRunLoading] = useState(false);

  const showToast = (type: "success" | "error", msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  };

  const loadJobs = useCallback(async () => {
    try {
      const res = await api.get<{ jobs: CronJob[] }>("/cronjobs");
      setJobs(res.jobs || []);
    } catch {
      /* silent */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  const handleCreate = async () => {
    if (!form.name.trim() || !form.schedule.trim() || !form.prompt.trim()) {
      showToast("error", "请填写所有字段");
      return;
    }
    setError("");
    try {
      await api.post("/cronjobs", form);
      setForm({ name: "", schedule: "", prompt: "" });
      setShowCreate(false);
      showToast("success", "任务已创建");
      await loadJobs();
    } catch (e: any) {
      showToast("error", e.message || "创建失败");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.del(`/cronjobs/${id}`);
      showToast("success", "任务已删除");
      await loadJobs();
    } catch {
      showToast("error", "删除失败");
    }
  };

  const handleRun = async (id: string) => {
    setRunLoading(true);
    try {
      const res = await api.post<{ success: boolean; session_id?: string }>(`/cronjobs/${id}/run`, {});
      await loadJobs();
      if (res.session_id) {
        navigate(`/?s=${res.session_id}`);
      } else {
        showToast("success", "任务已触发执行");
      }
    } catch {
      setRunLoading(false);
      showToast("error", "执行失败");
    }
  };

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: "", schedule: "", prompt: "" });

  const startEdit = (job: CronJob) => {
    setEditingId(job.id);
    setEditForm({ name: job.name, schedule: job.schedule, prompt: job.prompt });
  };

  const handleSaveEdit = async () => {
    if (!editingId) return;
    if (!editForm.name.trim()) { showToast("error", "名称不能为空"); return; }
    setError("");
    try {
      await api.put(`/cronjobs/${editingId}`, editForm);
      setEditingId(null);
      showToast("success", "任务已更新");
      await loadJobs();
    } catch (e: any) {
      showToast("error", e.message || "更新失败");
    }
  };

  const handleToggle = async (id: string, enabled: boolean) => {
    try {
      await api.put(`/cronjobs/${id}/toggle`, { enabled });
      showToast("success", enabled ? "任务已启用" : "任务已停用");
      await loadJobs();
    } catch {
      showToast("error", "操作失败");
    }
  };

  const formatTime = (t: string | null) => {
    if (!t) return "-";
    try {
      const d = new Date(t);
      return d.toLocaleString("zh-CN");
    } catch {
      return t;
    }
  };

  if (loading) {
    return <div className="page-container"><p>加载中...</p></div>;
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>定时任务</h2>
        <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
          <IconPlus size={16} /> 新建任务
        </button>
      </div>

      {toast && (
        <div className={`toast toast-${toast.type}`} style={{ marginBottom: 12 }}>
          {toast.msg}
        </div>
      )}
      {error && <div className="form-error" style={{ color: "var(--danger)", marginBottom: 12 }}>{error}</div>}

      {showCreate && (
        <div className="card" style={{ marginBottom: 16, padding: 16 }}>
          <div className="form-group">
            <label>任务名称</label>
            <input
              className="form-input"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="如：每日销售日报"
            />
          </div>
          <div className="form-group">
            <label>调度表达式</label>
            <input
              className="form-input"
              value={form.schedule}
              onChange={(e) => setForm({ ...form, schedule: e.target.value })}
              placeholder="every day at 09:00 / every 30 minutes / ISO时间戳"
            />
            <small style={{ color: "var(--text-3)" }}>
              支持: "every N minutes/hours/days", "every day at HH:MM", ISO时间戳
            </small>
          </div>
          <div className="form-group">
            <label>执行提示词</label>
            <textarea
              className="form-input"
              value={form.prompt}
              onChange={(e) => setForm({ ...form, prompt: e.target.value })}
              placeholder="任务触发时要发送给 AI 的提示词"
              rows={3}
            />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-primary" onClick={handleCreate}>创建</button>
            <button className="btn" onClick={() => { setShowCreate(false); setError(""); }}>取消</button>
          </div>
        </div>
      )}

      {jobs.length === 0 ? (
        <div className="empty-state">
          <p>暂无定时任务</p>
          <small style={{ color: "var(--text-3)" }}>点击上方「新建任务」创建一个</small>
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>名称</th>
              <th>调度</th>
              <th>上次执行</th>
              <th>下次执行</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              editingId === job.id ? (
                <tr key={job.id}>
                  <td colSpan={6} style={{ padding: 0 }}>
                    <div className="card" style={{ margin: 8, padding: 16 }}>
                      <div className="form-group">
                        <label>任务名称</label>
                        <input className="form-input" value={editForm.name}
                          onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
                      </div>
                      <div className="form-group">
                        <label>调度表达式</label>
                        <input className="form-input" value={editForm.schedule}
                          onChange={(e) => setEditForm({ ...editForm, schedule: e.target.value })} />
                      </div>
                      <div className="form-group">
                        <label>执行提示词</label>
                        <textarea className="form-input" value={editForm.prompt} rows={2}
                          onChange={(e) => setEditForm({ ...editForm, prompt: e.target.value })} />
                      </div>
                      <div style={{ display: "flex", gap: 8 }}>
                        <button className="btn btn-primary" onClick={handleSaveEdit}>保存</button>
                        <button className="btn" onClick={() => setEditingId(null)}>取消</button>
                      </div>
                    </div>
                  </td>
                </tr>
              ) : (
                <tr key={job.id}>
                  <td><strong>{job.name}</strong></td>
                  <td><code>{job.schedule}</code></td>
                  <td>
                  {job.last_run_at ? formatTime(job.last_run_at) : "-"}
                  {job.last_session_id && (
                    <button onClick={() => navigate(`/?s=${job.last_session_id}`)}
                       style={{ marginLeft: 6, fontSize: 12, color: "var(--primary)", background: "none", border: "none", cursor: "pointer", textDecoration: "underline", padding: 0 }}
                       title="查看执行结果">
                      查看
                    </button>
                  )}
                </td>
                  <td>{formatTime(job.next_run_at)}</td>
                  <td>
                    <span className={`badge ${job.enabled ? "badge-active" : "badge-inactive"}`}>
                      {job.enabled ? "生效中" : "已停用"}
                    </span>
                  </td>
                  <td>
                    <div className="table-actions">
                      <button className="btn-icon" title="立即执行" disabled={runLoading} onClick={() => handleRun(job.id)}>
                        <IconPlayerPlayFilled size={14} />
                      </button>
                      <button className="btn-icon" title="编辑" onClick={() => startEdit(job)}>
                        <IconEdit size={14} />
                      </button>
                      <button className="btn-icon" title={job.enabled ? "停用" : "启用"}
                        onClick={() => handleToggle(job.id, !job.enabled)}>
                        {job.enabled ? <IconPlayerPause size={14} /> : <IconPlayerPlay size={14} />}
                      </button>
                      <button className="btn-icon" title="删除" onClick={() => handleDelete(job.id)}>
                        <IconTrash size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              )
            ))}
          </tbody>
        </table>
      )}

      <div className="data-table-footer">
        <button className="btn" onClick={loadJobs}><IconRefresh size={14} /> 刷新</button>
        <span style={{ marginLeft: 8, color: "var(--text-3)", fontSize: 12 }}>共 {jobs.length} 个任务</span>
      </div>
    </div>
  );
}
