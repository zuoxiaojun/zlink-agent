import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  CircleCheck,
  CircleAlert,
  Save,
  ToggleLeft,
  ToggleRight,
  Loader2,
} from "lucide-react";
import { api } from "../api/http";

type FieldDef = {
  key: string;
  label: string;
  type: "text" | "password" | "number";
  placeholder?: string;
  secret?: boolean;
};

type ErpMeta = {
  label: string;
  badge: string;
  description: string;
  mcpServerName: string;
  fields: FieldDef[];
};

const ERP_REGISTRY: Record<string, ErpMeta> = {
  yonsuite: {
    label: "YonSuite",
    badge: "内置",
    description: "用友 YonSuite 云 ERP",
    mcpServerName: "yonsuite",
    fields: [
      { key: "tenant_id", label: "Tenant ID", type: "text" },
      { key: "app_key", label: "App Key", type: "password", secret: true },
      { key: "app_secret", label: "App Secret", type: "password", secret: true },
    ],
  },
  nc: {
    label: "NC",
    badge: "内置",
    description: "用友 NC Cloud（Oracle 数据库）",
    mcpServerName: "mcp-nc",
    fields: [
      { key: "host", label: "Host", type: "text" },
      { key: "port", label: "Port", type: "text", placeholder: "默认 1521" },
      { key: "service", label: "Service", type: "text", placeholder: "默认 orcl" },
      { key: "user", label: "User", type: "text" },
      { key: "password", label: "Password", type: "password", secret: true },
      { key: "max_rows", label: "Max Rows", type: "number", placeholder: "默认 200" },
    ],
  },
};

type ErpName = keyof typeof ERP_REGISTRY;

type ErpConfig = Record<string, any>;

type McpStatus = {
  name: string;
  status: "connected" | "disconnected" | "connecting" | "error" | "disabled";
  enabled: boolean;
};

type Toast = { kind: "success" | "error" | "warn"; msg: string };

export default function SettingsERPPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = searchParams.get("tab") || "yonsuite";
  const [activeTab, setActiveTab] = useState<ErpName>(
    initialTab in ERP_REGISTRY ? (initialTab as ErpName) : "yonsuite",
  );

  const [configs, setConfigs] = useState<Record<ErpName, ErpConfig | null>>({
    yonsuite: null,
    nc: null,
  });

  const [mcpStatuses, setMcpStatuses] = useState<McpStatus[]>([]);

  const [toast, setToast] = useState<Toast | null>(null);
  const [togglingName, setTogglingName] = useState<ErpName | null>(null);
  const [savingName, setSavingName] = useState<ErpName | null>(null);
  const [testingName, setTestingName] = useState<ErpName | null>(null);
  const [driftWarned, setDriftWarned] = useState<Record<ErpName, boolean>>({
    yonsuite: false,
    nc: false,
  });

  useEffect(() => {
    void loadAll();
  }, []);

  useEffect(() => {
    (Object.keys(ERP_REGISTRY) as ErpName[]).forEach((name) => {
      const cfg = configs[name];
      if (!cfg || mcpStatuses.length === 0) return;
      const meta = ERP_REGISTRY[name];
      const mcp = mcpStatuses.find((s) => s.name === meta.mcpServerName);
      if (!mcp) return;
      const erpEnabled = !!cfg.enabled;
      const mcpEnabled = mcp.enabled && mcp.status === "connected";
      if (erpEnabled !== mcpEnabled && !driftWarned[name]) {
        showToast(
          "warn",
          `${meta.label} 配置与 MCP server 状态不一致（ERP ${erpEnabled ? "启用" : "停用"} ↔ MCP ${mcpEnabled ? "连接中" : "未连接"}），请点上方开关同步`,
        );
        setDriftWarned((d) => ({ ...d, [name]: true }));
      }
    });
  }, [configs, mcpStatuses]);

  const loadAll = async () => {
    const [ys, ncData, mcp] = await Promise.all([
      api.get<ErpConfig>("/config/erp-clients/yonsuite").catch(() => null),
      api.get<ErpConfig>("/config/erp-clients/nc").catch(() => null),
      api.get<McpStatus[]>("/config/mcp-servers").catch(() => []),
    ]);
    setConfigs({ yonsuite: ys, nc: ncData });
    setMcpStatuses(mcp);
  };

  const switchTab = (tab: ErpName) => {
    setActiveTab(tab);
    setSearchParams({ tab }, { replace: true });
  };

  const showToast = (kind: Toast["kind"], msg: string) => {
    setToast({ kind, msg });
    setTimeout(() => setToast(null), 4000);
  };

  const updateField = (name: ErpName, key: string, value: any) => {
    setConfigs((prev) => ({
      ...prev,
      [name]: { ...(prev[name] || {}), [key]: value },
    }));
  };

  const handleToggle = async (name: ErpName) => {
    const cfg = configs[name];
    const meta = ERP_REGISTRY[name];
    if (!cfg) return;
    const newEnabled = !cfg.enabled;

    setTogglingName(name);
    try {
      const updated = await api.put<ErpConfig>(`/config/erp-clients/${name}`, {
        enabled: newEnabled,
      });
      setConfigs((prev) => ({ ...prev, [name]: updated }));

      try {
        await api.post(`/config/mcp-servers/${meta.mcpServerName}/toggle`);
        showToast(
          "success",
          `${meta.label} 已${newEnabled ? "启用" : "停用"}，MCP server 同步成功`,
        );
      } catch (mcpErr: any) {
        const msg = String(mcpErr?.message || "");
        if (msg.includes("404") || msg.includes("not found")) {
          showToast(
            "error",
            `${meta.label} MCP server (${meta.mcpServerName}) 未注册，请先到 MCP 管理页安装`,
          );
        } else {
          showToast("error", `${meta.label} MCP 联动失败：${msg}`);
        }
      }

      const mcp = await api.get<McpStatus[]>("/config/mcp-servers").catch(() => []);
      setMcpStatuses(mcp);
    } catch (e: any) {
      showToast("error", `更新 ${meta.label} 配置失败：${e.message}`);
    } finally {
      setTogglingName(null);
    }
  };

  const handleSave = async (name: ErpName) => {
    const cfg = configs[name];
    const meta = ERP_REGISTRY[name];
    if (!cfg) return;
    setSavingName(name);
    try {
      const updated = await api.put<ErpConfig>(`/config/erp-clients/${name}`, cfg);
      setConfigs((prev) => ({ ...prev, [name]: updated }));
      showToast("success", `${meta.label} 连接信息已保存`);
    } catch (e: any) {
      showToast("error", `保存失败：${e.message}`);
    } finally {
      setSavingName(null);
    }
  };

  const handleTest = async (name: ErpName) => {
    const meta = ERP_REGISTRY[name];
    setTestingName(name);
    try {
      const res = await api.post<{ ok: boolean; error?: string }>(
        `/config/erp-clients/${name}/test`,
      );
      showToast(
        res.ok ? "success" : "error",
        res.ok ? `${meta.label} 连接成功` : `连接失败：${res.error}`,
      );
    } catch (e: any) {
      showToast("error", `测试失败：${e.message}`);
    } finally {
      setTestingName(null);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate("/")}>
          <ArrowLeft size={16} />
        </button>
        <h1 className="page-title">ERP 连接</h1>
      </div>

      {toast && (
        <div
          className={`toast toast-${toast.kind === "warn" ? "error" : toast.kind}`}
          style={{ alignItems: "center" }}
        >
          {toast.kind === "success" ? <CircleCheck size={14} /> : <CircleAlert size={14} />}
          {toast.msg}
        </div>
      )}

      <p
        style={{
          margin: "0 0 20px",
          color: "var(--text-2)",
          lineHeight: 1.6,
          fontSize: 14,
        }}
      >
        ZLink Agent 通过 <strong>ERP 客户端</strong> 接入各业务系统。切换页签管理 YonSuite
        与 NC 的连接信息，启停开关会同步联动对应 MCP server。
      </p>

      <div
        style={{
          display: "inline-flex",
          background: "var(--bg-card)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          padding: 4,
          marginBottom: 20,
          gap: 4,
        }}
      >
        {(Object.keys(ERP_REGISTRY) as ErpName[]).map((name) => {
          const meta = ERP_REGISTRY[name];
          const isActive = activeTab === name;
          return (
            <button
              key={name}
              onClick={() => switchTab(name)}
              style={{
                padding: "6px 16px",
                borderRadius: "calc(var(--radius) - 4px)",
                border: "none",
                background: isActive ? "var(--primary)" : "transparent",
                color: isActive ? "#fff" : "var(--text-2)",
                fontSize: 13,
                fontWeight: isActive ? 500 : 400,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              {meta.label}
              <span
                style={{
                  fontSize: 11,
                  padding: "1px 6px",
                  borderRadius: 10,
                  background: isActive ? "rgba(255,255,255,0.25)" : "var(--bg-hover)",
                  color: isActive ? "#fff" : "var(--text-3)",
                }}
              >
                {meta.badge}
              </span>
            </button>
          );
        })}
      </div>

      {(Object.keys(ERP_REGISTRY) as ErpName[]).map((name) =>
        activeTab === name ? (
          <ErpTabPanel
            key={name}
            meta={ERP_REGISTRY[name]}
            config={configs[name]}
            mcpStatus={mcpStatuses.find((s) => s.name === ERP_REGISTRY[name].mcpServerName)}
            isToggling={togglingName === name}
            isSaving={savingName === name}
            isTesting={testingName === name}
            onUpdateField={(k, v) => updateField(name, k, v)}
            onToggle={() => handleToggle(name)}
            onSave={() => handleSave(name)}
            onTest={() => handleTest(name)}
          />
        ) : null,
      )}
    </div>
  );
}

type TabProps = {
  meta: ErpMeta;
  config: ErpConfig | null;
  mcpStatus?: McpStatus;
  isToggling: boolean;
  isSaving: boolean;
  isTesting: boolean;
  onUpdateField: (key: string, value: any) => void;
  onToggle: () => void;
  onSave: () => void;
  onTest: () => void;
};

function ErpTabPanel({
  meta,
  config,
  mcpStatus,
  isToggling,
  isSaving,
  isTesting,
  onUpdateField,
  onToggle,
  onSave,
  onTest,
}: TabProps) {
  if (!config) {
    return (
      <div className="card">
        <div className="card-body" style={{ padding: 24 }}>
          <div className="skeleton skeleton-title" />
          <div className="skeleton skeleton-text" />
          <div className="skeleton skeleton-text" />
        </div>
      </div>
    );
  }

  const enabled = !!config.enabled;
  const mcpExists = !!mcpStatus;
  const mcpConnected = mcpStatus?.status === "connected";
  const mcpDisabled = mcpStatus?.enabled === false || mcpStatus?.status === "disabled";

  return (
    <div className="card">
      <div
        className="card-header"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div>
          <h2 className="card-title">{meta.label}</h2>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--text-3)" }}>
            {meta.description}
            {mcpExists && (
              <span style={{ marginLeft: 12 }}>
                · MCP{" "}
                <span
                  style={{
                    color: mcpConnected
                      ? "var(--success, #00B42A)"
                      : "var(--text-3)",
                  }}
                >
                  {mcpConnected ? "已连接" : mcpDisabled ? "已停用" : "未连接"}
                </span>
              </span>
            )}
            {!mcpExists && (
              <span style={{ marginLeft: 12, color: "var(--text-3)" }}>
                · MCP server 未注册
              </span>
            )}
          </p>
        </div>

        <button
          onClick={onToggle}
          disabled={isToggling}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "6px 12px",
            background: "transparent",
            border: `1px solid ${
              enabled ? "var(--success, #00B42A)" : "var(--border)"
            }`,
            borderRadius: "var(--radius-sm)",
            color: enabled ? "var(--success, #00B42A)" : "var(--text-2)",
            cursor: isToggling ? "wait" : "pointer",
            fontSize: 13,
            fontWeight: 500,
            opacity: isToggling ? 0.6 : 1,
          }}
          title={enabled ? "点击停用（同时停用 MCP）" : "点击启用（同时启用 MCP）"}
        >
          {isToggling ? (
            <Loader2 size={14} className="spin" />
          ) : enabled ? (
            <ToggleRight size={16} />
          ) : (
            <ToggleLeft size={16} />
          )}
          {enabled ? "已启用" : "已停用"}
        </button>
      </div>

      {meta.fields.map((field) => (
        <div key={field.key} className="form-group">
          <label className="form-label">{field.label}</label>
          <input
            className="form-input"
            type={field.type}
            value={config[field.key] ?? ""}
            placeholder={
              field.placeholder ??
              (field.secret && config[field.key] ? "（已设置，留空保持原值）" : "")
            }
            onChange={(e) =>
              onUpdateField(
                field.key,
                field.type === "number" ? Number(e.target.value) : e.target.value,
              )
            }
          />
        </div>
      ))}

      <div className="card-actions">
        <button className="btn btn-primary" onClick={onSave} disabled={isSaving}>
          {isSaving ? <Loader2 size={14} className="spin" /> : <Save size={14} />}
          保存连接信息
        </button>
        <button className="btn btn-secondary" onClick={onTest} disabled={isTesting}>
          {isTesting ? <Loader2 size={14} className="spin" /> : null}
          测试连接
        </button>
      </div>
    </div>
  );
}