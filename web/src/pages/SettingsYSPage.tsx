import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, CircleCheck, Pencil, Save } from "lucide-react";
import { api } from "../api/http";
import { useAppState } from "../context/AppContext";
import type { YonSuiteConfigPayload } from "../types";

export default function SettingsYSPage() {
  const navigate = useNavigate();
  const { state, dispatch } = useAppState();
  const [edit, setEdit] = useState(false);
  const [form, setForm] = useState<YonSuiteConfigPayload>({
    app_key: "",
    app_secret: "",
    tenant_id: "",
    gateway_url: "https://c2.yonyoucloud.com/iuap-api-gateway",
  });
  const [saved, setSaved] = useState(false);

  React.useEffect(() => {
    if (state.config) {
      setForm({ ...state.config.yonsuite, app_key: "", app_secret: "" });
    }
  }, [state.config]);

  const handleSave = async () => {
    await api.put("/config/yonsuite", form);
    dispatch({ type: "SET_CONFIG", config: { ...state.config!, yonsuite: form } });
    setEdit(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const SECRET_KEYS = new Set(["app_key", "app_secret"]);

  const fields = [
    { key: "app_key" as const, label: "App Key", type: "password" },
    { key: "app_secret" as const, label: "App Secret", type: "password" },
    { key: "tenant_id" as const, label: "Tenant ID", type: "text" },
    { key: "gateway_url" as const, label: "Gateway URL", type: "text" },
  ];

  const maskSecret = (value: string) => value ? "••••••••" : "";

  return (
    <div className="page-container">
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate("/")}><ArrowLeft size={16} /></button>
        <h1 className="page-title">YonSuite 配置</h1>
      </div>

      {saved && <div className="toast toast-success"><CircleCheck size={14} /> YonSuite 配置已保存</div>}

      {!edit ? (
        <div className="card">
          {fields.map(({ key, label }) => (
            <div key={key} className="form-group">
              <span className="form-label">{label}</span>
              <div className="card-body">{SECRET_KEYS.has(key) ? maskSecret(state.config?.yonsuite[key]) || "（未设置）" : state.config?.yonsuite[key] || "（未设置）"}</div>
            </div>
          ))}
          <div className="card-actions">
            <button className="btn btn-secondary" onClick={() => { setEdit(true); setSaved(false); }}><Pencil size={14} /> 编辑</button>
          </div>
        </div>
      ) : (
        <div className="card">
          {fields.map(({ key, label, type }) => (
            <div key={key} className="form-group">
              <label className="form-label">{label}</label>
              <input
                className="form-input"
                type={type}
                value={form[key]}
                placeholder={SECRET_KEYS.has(key) ? "••••••••" : undefined}
                onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
              />
            </div>
          ))}
          <div className="form-actions">
            <button className="btn btn-primary" onClick={handleSave}><Save size={14} /> 保存</button>
            <button className="btn btn-secondary" onClick={() => setEdit(false)}>取消</button>
          </div>
        </div>
      )}
    </div>
  );
}
