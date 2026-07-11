import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, CircleCheck, Pencil, Save } from "lucide-react";
import { api } from "../api/http";
import { useAppState } from "../context/AppContext";

export default function SettingsAgentPage() {
  const navigate = useNavigate();
  const { state, dispatch } = useAppState();
  const cfg = state.config?.agent;
  const [edit, setEdit] = useState(false);
  const [maxIter, setMaxIter] = useState(cfg?.max_iterations || 30);
  const [compactionEnabled, setCompactionEnabled] = useState(cfg?.compaction_enabled ?? true);
  const [ctxAuto, setCtxAuto] = useState(cfg?.max_context_tokens_auto ?? true);
  const [maxContextTokens, setMaxContextTokens] = useState(cfg?.max_context_tokens || 128000);
  const [reserveTokens, setReserveTokens] = useState(cfg?.reserve_tokens || 4000);
  const [keepRecentTokens, setKeepRecentTokens] = useState(cfg?.keep_recent_tokens || 8000);
  const [approvalMode, setApprovalMode] = useState(cfg?.approval_mode || "allow_all");
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    const payload = {
      max_iterations: maxIter,
      compaction_enabled: compactionEnabled,
      max_context_tokens: ctxAuto ? 0 : maxContextTokens,
      max_context_tokens_auto: ctxAuto,
      reserve_tokens: reserveTokens,
      keep_recent_tokens: keepRecentTokens,
      approval_mode: approvalMode,
    };
    await api.put("/config/agent", payload);
    dispatch({ type: "SET_CONFIG", config: { ...state.config!, agent: payload } });
    setEdit(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const fmt = (n: number) => (n >= 1000 ? `${Math.round(n / 1000)}K` : String(n));

  return (
    <div className="page-container">
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate("/")}><ArrowLeft size={16} /></button>
        <h1 className="page-title">Agent 设置</h1>
      </div>

      {saved && <div className="toast toast-success"><CircleCheck size={14} /> Agent 设置已保存</div>}

      {!edit ? (
        <div className="card">
          <div className="form-group">
            <span className="form-label">最大迭代轮次</span>
            <div className="card-body">{cfg?.max_iterations || 30}</div>
          </div>
          <div className="form-group">
            <span className="form-label">上下文自动压缩</span>
            <div className="card-body">{cfg?.compaction_enabled !== false ? "已启用" : "已关闭"}</div>
          </div>
          <div className="form-group">
            <span className="form-label">模型上下文窗口上限</span>
            <div className="card-body">
              {cfg?.max_context_tokens_auto !== false ? (
                <span>自动检测 <span style={{ color: "var(--text-3)" }}>({fmt(cfg?.max_context_tokens || 128000)} tokens)</span></span>
              ) : (
                <span>{fmt(cfg?.max_context_tokens || 128000)} tokens</span>
              )}
            </div>
          </div>
          <div className="form-group">
            <span className="form-label">预留输出空间</span>
            <div className="card-body">{fmt(cfg?.reserve_tokens || 4000)} tokens</div>
          </div>
          <div className="form-group">
            <span className="form-label">保留最近对话量</span>
            <div className="card-body">{fmt(cfg?.keep_recent_tokens || 8000)} tokens</div>
          </div>
          <div className="form-group">
            <span className="form-label">命令审批模式</span>
            <div className="card-body">
              {cfg?.approval_mode === "allow_all" && "自动放行"}
              {cfg?.approval_mode === "approve" && "高风险需审批"}
              {cfg?.approval_mode === "reject_all" && "全部拒绝"}
              {!cfg?.approval_mode && "自动放行"}
            </div>
          </div>
          <div className="card-actions">
            <button className="btn btn-secondary" onClick={() => { setEdit(true); setSaved(false); }}><Pencil size={14} /> 编辑</button>
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="form-group">
            <label className="form-label">最大迭代轮次</label>
            <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
              <input
                className="form-slider"
                type="range"
                min={5}
                max={50}
                value={maxIter}
                onChange={(e) => setMaxIter(Number(e.target.value))}
              />
              <span style={{ fontSize: "14px", fontWeight: 600, color: "var(--text-1)", minWidth: "24px" }}>{maxIter}</span>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">上下文自动压缩</label>
            <div style={{ display: "flex", gap: "12px" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer", fontSize: "14px" }}>
                <input
                  type="radio"
                  name="compaction"
                  checked={compactionEnabled}
                  onChange={() => setCompactionEnabled(true)}
                />
                启用
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer", fontSize: "14px" }}>
                <input
                  type="radio"
                  name="compaction"
                  checked={!compactionEnabled}
                  onChange={() => setCompactionEnabled(false)}
                />
                关闭
              </label>
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-3)", marginTop: "4px" }}>
              对话接近上下文窗口上限时自动压缩历史消息
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">模型上下文窗口上限</label>
            <div style={{ display: "flex", gap: "12px", marginBottom: "8px" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer", fontSize: "14px" }}>
                <input
                  type="radio"
                  name="ctxAuto"
                  checked={ctxAuto}
                  onChange={() => setCtxAuto(true)}
                />
                自动检测
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer", fontSize: "14px" }}>
                <input
                  type="radio"
                  name="ctxAuto"
                  checked={!ctxAuto}
                  onChange={() => setCtxAuto(false)}
                />
                手动设置
              </label>
            </div>
            {!ctxAuto && (
              <>
                <input
                  className="form-slider"
                  type="range"
                  min={16000}
                  max={2000000}
                  step={8000}
                  value={maxContextTokens}
                  onChange={(e) => setMaxContextTokens(Number(e.target.value))}
                />
                <span style={{ fontSize: "13px", fontWeight: 600, marginLeft: "8px" }}>{fmt(maxContextTokens)} tokens</span>
              </>
            )}
            <div style={{ fontSize: "12px", color: "var(--text-3)", marginTop: "4px" }}>
              自动检测根据当前使用的模型自动匹配上下文窗口大小
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">预留输出空间 ({fmt(reserveTokens)} tokens)</label>
            <input
              className="form-slider"
              type="range"
              min={1000}
              max={32000}
              step={1000}
              value={reserveTokens}
              onChange={(e) => setReserveTokens(Number(e.target.value))}
            />
            <div style={{ fontSize: "12px", color: "var(--text-3)" }}>为模型回复预留的 token 空间，压缩阈值 = 窗口上限 - 预留空间</div>
          </div>

          <div className="form-group">
            <label className="form-label">保留最近对话 ({fmt(keepRecentTokens)} tokens)</label>
            <input
              className="form-slider"
              type="range"
              min={2000}
              max={64000}
              step={2000}
              value={keepRecentTokens}
              onChange={(e) => setKeepRecentTokens(Number(e.target.value))}
            />
            <div style={{ fontSize: "12px", color: "var(--text-3)" }}>压缩时保留最近多少 tokens 的对话不被压缩</div>
          </div>

          <div className="form-group">
            <label className="form-label">命令审批模式</label>
            <div style={{ display: "flex", gap: "12px" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer", fontSize: "14px" }}>
                <input
                  type="radio"
                  name="approvalMode"
                  value="allow_all"
                  checked={approvalMode === "allow_all"}
                  onChange={(e) => setApprovalMode(e.target.value)}
                />
                自动放行
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer", fontSize: "14px" }}>
                <input
                  type="radio"
                  name="approvalMode"
                  value="approve"
                  checked={approvalMode === "approve"}
                  onChange={(e) => setApprovalMode(e.target.value)}
                />
                高风险需审批
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer", fontSize: "14px" }}>
                <input
                  type="radio"
                  name="approvalMode"
                  value="reject_all"
                  checked={approvalMode === "reject_all"}
                  onChange={(e) => setApprovalMode(e.target.value)}
                />
                全部拒绝
              </label>
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-3)", marginTop: "4px" }}>
              {approvalMode === "allow_all" && "所有工具直接执行，无需审批（默认）"}
              {approvalMode === "approve" && "高风险操作（终端命令、文件删除等）需要用户批准后才能执行"}
              {approvalMode === "reject_all" && "拒绝所有中高风险操作，仅允许低风险工具执行"}
            </div>
          </div>

          <div className="form-actions">
            <button className="btn btn-primary" onClick={handleSave}><Save size={14} /> 保存</button>
            <button className="btn btn-secondary" onClick={() => setEdit(false)}>取消</button>
          </div>
        </div>
      )}
    </div>
  );
}
