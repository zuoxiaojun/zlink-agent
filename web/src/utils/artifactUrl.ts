import { apiUrl } from "../api/http";

/**
 * 产物内容 URL —— 与后端 `GET /api/session-files/{sid}/{rel}` 一一对应。
 *
 * SAFETY: 只接受我们自己的后端源（`apiUrl` 已封好 `/api` 前缀与 Electron
 * 绝对地址），`sid` 来自会话状态、`rel` 来自后端列表响应，均非用户输入的
 * 任意主机名，因此不存在 SSRF 面。
 */
export function artifactFileUrl(sid: string, rel: string): string {
  const enc = rel
    .split("/")
    .map(encodeURIComponent)
    .join("/");
  return apiUrl(`/session-files/${sid}/${enc}`);
}

export function artifactDownloadUrl(sid: string, rel: string): string {
  return `${artifactFileUrl(sid, rel)}?download=1`;
}
