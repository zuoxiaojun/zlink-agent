import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, CircleCheck } from "lucide-react";
import { api } from "../api/http";

interface YonSuiteConfig {
  enabled: boolean;
  tenant_id: string;
  app_key: string;
  app_secret: string;
  base_url: string;
}

interface NCConfig {
  enabled: boolean;
  host: string;
  port: string;
  service: string;
  user: string;
  password: string;
  max_rows: number;
}

const defaultYonsuite: YonSuiteConfig = {
  enabled: false,
  tenant_id: "",
  app_key: "",
  app_secret: "",
  base_url: "",
};

const defaultNc: NCConfig = {
  enabled: false,
  host: "",
  port: "",
  service: "",
  user: "",
  password: "",
  max_rows: 200,
};

export default function SettingsERPPage() {
  const navigate = useNavigate();

  const [yonsuite, setYonsuite] = useState<YonSuiteConfig>(defaultYonsuite);
  const [nc, setNc] = useState<NCConfig>(defaultNc);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<YonSuiteConfig>("/config/erp-clients/yonsuite").catch(() => null),
      api.get<NCConfig>("/config/erp-clients/nc").catch(() => null),
    ]).then(([ys, ncData]) => {
      if (ys) setYonsuite(ys);
      if (ncData) setNc(ncData);
    });
  }, []);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const saveYonsuite = async () => {
    await api.put("/config/erp-clients/yonsuite", yonsuite);
    showToast("YonSuite 配置已保存");
  };

  const testYonsuite = async () => {
    const res = await api.post<{ ok: boolean; error?: string }>("/config/erp-clients/yonsuite/test");
    alert(res.ok ? "连接成功" : `连接失败: ${res.error}`);
  };

  const saveNc = async () => {
    await api.put("/config/erp-clients/nc", nc);
    showToast("NC 配置已保存");
  };

  const testNc = async () => {
    const res = await api.post<{ ok: boolean; error?: string }>("/config/erp-clients/nc/test");
    alert(res.ok ? "连接成功" : `连接失败: ${res.error}`);
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <button className="back-btn" onClick={() => navigate("/")}><ArrowLeft size={16} /></button>
        <h1 className="page-title">ERP 客户端</h1>
      </div>

      {toast && <div className="toast toast-success"><CircleCheck size={14} /> {toast}</div>}

      <p style={{ margin: "0 0 20px", color: "#555", lineHeight: 1.6, fontSize: 14 }}>
        ZLink Agent 支持连接多个 ERP 系统。当前已注册: YonSuite（内置）、NC（需安装 nc-mcp-server）。启用后 AI 自动从对应系统取数。
      </p>

      {/* YonSuite card */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <h2 className="card-title">YonSuite（内置）</h2>
        </div>

        <div className="form-group">
          <label className="form-label">
            <input
              type="checkbox"
              checked={yonsuite.enabled}
              onChange={(e) => setYonsuite((f) => ({ ...f, enabled: e.target.checked }))}
              style={{ marginRight: 8 }}
            />
            启用
          </label>
        </div>

        <div className="form-group">
          <label className="form-label">Tenant ID</label>
          <input className="form-input" type="text" value={yonsuite.tenant_id} onChange={(e) => setYonsuite((f) => ({ ...f, tenant_id: e.target.value }))} />
        </div>

        <div className="form-group">
          <label className="form-label">App Key</label>
          <input className="form-input" type="password" value={yonsuite.app_key} onChange={(e) => setYonsuite((f) => ({ ...f, app_key: e.target.value }))} />
        </div>

        <div className="form-group">
          <label className="form-label">App Secret</label>
          <input className="form-input" type="password" value={yonsuite.app_secret} onChange={(e) => setYonsuite((f) => ({ ...f, app_secret: e.target.value }))} />
        </div>

        <div className="form-group">
          <label className="form-label">Base URL</label>
          <input className="form-input" type="text" value={yonsuite.base_url} onChange={(e) => setYonsuite((f) => ({ ...f, base_url: e.target.value }))} />
        </div>

        <div className="card-actions">
          <button className="btn btn-primary" onClick={saveYonsuite}>保存</button>
          <button className="btn btn-secondary" onClick={testYonsuite}>测试连接</button>
        </div>
      </div>

      {/* NC card */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">NC（需安装 nc-mcp-server）</h2>
        </div>

        <div className="form-group">
          <label className="form-label">
            <input
              type="checkbox"
              checked={nc.enabled}
              onChange={(e) => setNc((f) => ({ ...f, enabled: e.target.checked }))}
              style={{ marginRight: 8 }}
            />
            启用
          </label>
        </div>

        <div className="form-group">
          <label className="form-label">Host</label>
          <input className="form-input" type="text" value={nc.host} onChange={(e) => setNc((f) => ({ ...f, host: e.target.value }))} />
        </div>

        <div className="form-group">
          <label className="form-label">Port</label>
          <input className="form-input" type="text" value={nc.port} placeholder="默认 1521" onChange={(e) => setNc((f) => ({ ...f, port: e.target.value }))} />
        </div>

        <div className="form-group">
          <label className="form-label">Service</label>
          <input className="form-input" type="text" value={nc.service} placeholder="默认 orcl" onChange={(e) => setNc((f) => ({ ...f, service: e.target.value }))} />
        </div>

        <div className="form-group">
          <label className="form-label">User</label>
          <input className="form-input" type="text" value={nc.user} onChange={(e) => setNc((f) => ({ ...f, user: e.target.value }))} />
        </div>

        <div className="form-group">
          <label className="form-label">Password</label>
          <input className="form-input" type="password" value={nc.password} onChange={(e) => setNc((f) => ({ ...f, password: e.target.value }))} />
        </div>

        <div className="form-group">
          <label className="form-label">Max Rows</label>
          <input className="form-input" type="number" value={nc.max_rows} placeholder="默认 200" onChange={(e) => setNc((f) => ({ ...f, max_rows: Number(e.target.value) }))} />
        </div>

        <div className="card-actions">
          <button className="btn btn-primary" onClick={saveNc}>保存</button>
          <button className="btn btn-secondary" onClick={testNc}>测试连接</button>
        </div>
      </div>
    </div>
  );
}