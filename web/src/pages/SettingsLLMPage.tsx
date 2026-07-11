import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, CircleCheck, Database, Pencil, Save } from "lucide-react";
import { api } from "../api/http";
import { useAppState } from "../context/AppContext";
import type { ProviderInfo, LLMConfigPayload } from "../types";

function formatCtx(n: number): string {
  if (n >= 1_000_000) return `${n / 1_000_000}M`;
  if (n >= 1_000) return `${n / 1_000}K`;
  return String(n);
}

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
  }, []);

  const handleProviderChange = (name: string) => {
    const prov = providers.find((p) => p.name === name);
    if (prov) {
      setForm((f) => ({
        ...f,
        provider: name,
        base_url: prov.base_url,
        model: prov.models.length > 0 ? prov.models[0].id : "",
      }));
    }
  };

  const provider = providers.find((p) => p.name === form.provider);
  const modelOptions = provider?.models ?? [];
  const isCustomProvider = form.provider === "自定义";

  const handleSave = async () => {
    await api.put("/config/llm", form);
    dispatch({ type: "SET_CONFIG", config: { ...state.config!, llm: form } });
    setEdit(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleEdit = () => {
    if (state.config) {
      setForm({ ...state.config.llm, api_key: "" });
    }
    setEdit(true);
    setSaved(false);
  };

  const currentConfig = state.config?.llm;
  const selectedModelInfo = isCustomProvider
    ? null
    : (modelOptions.find((m) => m.id === form.model) ?? null);

  return (
    <div className="page-container">
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate("/")}>
          <ArrowLeft size={16} />
        </button>
        <h1 className="page-title">大模型配置</h1>
      </div>

      {saved && (
        <div className="toast toast-success">
          <CircleCheck size={14} /> 大模型配置已保存
        </div>
      )}

      {!edit ? (
        <div className="card">
          <div className="form-group">
            <span className="form-label">模型厂商</span>
            <div className="card-body">{currentConfig?.provider || "（未配置）"}</div>
          </div>
          <div className="form-group">
            <span className="form-label">模型</span>
            <div className="card-body">{currentConfig?.model || "（未配置）"}</div>
          </div>
          <div className="form-group">
            <span className="form-label">API Key</span>
            <div className="card-body">
              {currentConfig?.api_key || "（未设置）"}
            </div>
          </div>
          <div className="card-actions">
            <button className="btn btn-secondary" onClick={handleEdit}>
              <Pencil size={14} /> 编辑
            </button>
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
                <option key={p.name} value={p.name}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {isCustomProvider ? (
            <>
              <div className="form-group">
                <label className="form-label">模型名称</label>
                <input
                  className="form-input"
                  type="text"
                  value={form.model}
                  placeholder="输入模型 ID，如 gpt-4o"
                  onChange={(e) =>
                    setForm((f) => ({ ...f, model: e.target.value }))
                  }
                />
              </div>
              <div className="form-group">
                <label className="form-label">API Base URL</label>
                <input
                  className="form-input"
                  type="text"
                  value={form.base_url}
                  placeholder="https://api.example.com/v1"
                  onChange={(e) =>
                    setForm((f) => ({ ...f, base_url: e.target.value }))
                  }
                />
              </div>
            </>
          ) : (
            <div className="form-group">
              <label className="form-label">选择模型</label>
              <select
                className="form-select"
                value={modelOptions.some((m) => m.id === form.model) ? form.model : ""}
                onChange={(e) =>
                  setForm((f) => ({ ...f, model: e.target.value }))
                }
              >
                {modelOptions.length === 0 && (
                  <option value="">该厂商暂无预设模型</option>
                )}
                {modelOptions.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.id}
                  </option>
                ))}
              </select>
              {selectedModelInfo && (
                <div style={{ marginTop: 8, fontSize: 13, color: "var(--text-2)" }}>
                  <Database size={13} style={{ verticalAlign: "middle", marginRight: 4 }} />
                  上下文窗口：{formatCtx(selectedModelInfo.context_length)}
                  {selectedModelInfo.max_output != null && (
                    <> · 最大输出：{formatCtx(selectedModelInfo.max_output)}</>
                  )}
                  tokens
                </div>
              )}
            </div>
          )}

          <div className="form-group">
            <label className="form-label">
              {provider?.api_key_label || "API Key"}
            </label>
            <input
              className="form-input"
              type="password"
              value={form.api_key}
              placeholder={provider?.api_key_placeholder || ""}
              onChange={(e) =>
                setForm((f) => ({ ...f, api_key: e.target.value }))
              }
            />
          </div>

          <div className="form-actions">
            <button className="btn btn-primary" onClick={handleSave}>
              <Save size={14} /> 保存
            </button>
            <button className="btn btn-secondary" onClick={() => setEdit(false)}>
              取消
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
