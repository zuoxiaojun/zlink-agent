import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, CircleCheck, Pencil, Save } from "lucide-react";
import { api } from "../api/http";
import { useAppState } from "../context/AppContext";

export default function SettingsAgentPage() {
  const navigate = useNavigate();
  const { state, dispatch } = useAppState();
  const [edit, setEdit] = useState(false);
  const [maxIter, setMaxIter] = useState(state.config?.agent.max_iterations || 30);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    await api.put("/config/agent", { max_iterations: maxIter });
    dispatch({ type: "SET_CONFIG", config: { ...state.config!, agent: { max_iterations: maxIter } } });
    setEdit(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

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
            <div className="card-body">{state.config?.agent.max_iterations || 30}</div>
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
          <div className="form-actions">
            <button className="btn btn-primary" onClick={handleSave}><Save size={14} /> 保存</button>
            <button className="btn btn-secondary" onClick={() => setEdit(false)}>取消</button>
          </div>
        </div>
      )}
    </div>
  );
}
