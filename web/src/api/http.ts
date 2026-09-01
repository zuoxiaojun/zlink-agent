// In Electron, API calls go to the local Python backend.
// In browser (dev), they use same-origin proxy via Vite.
// SAFETY: window.electron 由 electron/preload 注入，形状固定为 { backendUrl: string }；
// 非 Electron 环境（纯浏览器 dev）该键不存在，走同源相对路径。
const API_BASE = (window as unknown as Record<string, unknown>).electron
  ? `${((window as unknown as Record<string, unknown>).electron as Record<string, string>).backendUrl}/api`
  : "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

// 产物预览要用绝对 URL：Electron 下页面可能不是后端源，iframe/下载链接必须自洽。
export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}
