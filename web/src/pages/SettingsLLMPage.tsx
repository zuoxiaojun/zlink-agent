import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, CircleCheck, Pencil, Save } from "lucide-react";
import { api } from "../api/http";
import { useAppState } from "../context/AppContext";
import type { ProviderInfo, LLMConfigPayload } from "../types";

export default function SettingsLLMPage() {
  const navigate = useNavigate();
  const { state, dispatch } = useAppState();
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [edit, setEdit] = useState(false);
  const [form, setForm] = useState<LLMConfigPayload>({
    api_key: "",
    base_url: "https://api.openai.com/v1",
    model: "gpt-4o",
    provider: "OpenAI",
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get<ProviderInfo[]>("/config/providers").then(setProviders);
    if (state.config) {
      setForm({ ...state.config.llm, api_key: "" });
    }
  }, [state.config]);

  const handleProviderChange = (name: string) => {
    const prov = providers.find((p) => p.name === name);
    if (prov) {
      setForm((f) => ({ ...f, provider: name, base_url: prov.base_url, model: prov.models[0] }));
    }
  };

  const provider = providers.find((p) => p.name === form.provider);
  const modelOptions = provider ? [...provider.models, "自定义..."] : [];

  const handleSave = async () => {
    await api.put("/config/llm", form);
    dispatch({ type: "SET_CONFIG", config: { ...state.config!, llm: form } });
    setEdit(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate("/")}><ArrowLeft size={16} /></button>
        <h1 className="page-title">LLM 配置</h1>
      </div>

      {saved && <div className="toast toast-success"><CircleCheck size={14} /> LLM 配置已保存</div>}

      {!edit ? (
        <div className="card">
          <div className="form-group">
            <span className="form-label">模型厂商</span>
            <div className="card-body">{form.provider}</div>
          </div>
          <div className="form-group">
            <span className="form-label">模型</span>
            <div className="card-body">{form.model}</div>
          </div>
          <div className="form-group">
            <span className="form-label">Base URL</span>
            <div className="card-body">{form.base_url}</div>
          </div>
          <div className="form-group">
            <span className="form-label">API Key</span>
            <div className="card-body">{state.config?.llm.api_key || "（未设置）"}</div>
          </div>
          <div className="card-actions">
            <button className="btn btn-secondary" onClick={() => { setEdit(true); setSaved(false); }}><Pencil size={14} /> 编辑</button>
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="form-group">
            <label className="form-label">选择模型厂商</label>
            <select
              className="form-select"
              value={form.provider}
              onChange={(e) => handleProviderChange(e.target.value)}
            >
              {providers.map((p) => (
                <option key={p.name} value={p.name}>{p.name}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">选择模型</label>
            <select
              className="form-select"
              value={modelOptions.includes(form.model) ? form.model : "自定义..."}
              onChange={(e) => {
                if (e.target.value === "自定义...") {
                  setForm((f) => ({ ...f, model: "" }));
                } else {
                  setForm((f) => ({ ...f, model: e.target.value }));
                }
              }}
            >
              {modelOptions.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
            {!modelOptions.includes(form.model) && (
              <input
                className="form-input"
                type="text"
                value={form.model}
                placeholder="输入模型名称"
                onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))}
                style={{ marginTop: "8px" }}
              />
            )}
          </div>

          <div className="form-group">
            <label className="form-label">{provider?.api_key_label || "API Key"}</label>
            <input
              className="form-input"
              type="password"
              value={form.api_key}
              placeholder={provider?.api_key_placeholder || ""}
              onChange={(e) => setForm((f) => ({ ...f, api_key: e.target.value }))}
            />
          </div>

          <details style={{ margin: "12px 0" }}>
            <summary style={{ cursor: "pointer", fontSize: "13px", color: "var(--text-2)", padding: "8px 0" }}>高级选项（自定义 Base URL）</summary>
            <input
              className="form-input"
              type="text"
              value={form.base_url}
              placeholder="API Base URL"
              onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))}
            />
          </details>

          <div className="form-actions">
            <button className="btn btn-primary" onClick={handleSave}><Save size={14} /> 保存</button>
            <button className="btn btn-secondary" onClick={() => setEdit(false)}>取消</button>
          </div>
        </div>
      )}
    </div>
  );
}
