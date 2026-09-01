import { useEffect, useState } from "react";
import {
  IconExternalLink,
  IconFile,
  IconFileText,
  IconFolderOpen,
  IconLayoutSidebarRight,
  IconPackage,
  IconPhoto,
  IconRefresh,
  IconX,
} from "@tabler/icons-react";
import { api, apiUrl } from "../api/http";
import type { ArtifactItem, ArtifactListResponse } from "../types";
import { artifactDownloadUrl, artifactFileUrl } from "../utils/artifactUrl";
import { Markdown } from "./MessageContent";
import CodeBlock from "./CodeBlock";

const MAX_INLINE_BYTES = 5_000_000;

function KindIcon({ kind }: { kind: ArtifactItem["kind"] }) {
  if (kind === "image") return <IconPhoto size={14} />;
  if (kind === "md" || kind === "text") return <IconFileText size={14} />;
  return <IconFile size={14} />;
}

function fmtSize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function FallbackCard({ sid, sel, reason }: { sid: string; sel: ArtifactItem; reason: string }) {
  return (
    <div className="artifacts-fallback">
      <IconFile size={28} />
      <div className="artifacts-fallback-name">{sel.name}</div>
      <div className="text-hint">{reason}</div>
      <a className="btn-secondary" href={artifactFileUrl(sid, sel.rel)} target="_blank" rel="noreferrer">
        在浏览器打开
      </a>
      <a className="btn-secondary" href={artifactDownloadUrl(sid, sel.rel)}>
        下载
      </a>
    </div>
  );
}

interface Props {
  sid: string | null;
  data: ArtifactListResponse | null;
  loading: boolean;
  error: string | null;
  width: number;
  refresh: () => void;
  onCollapse: () => void;
}

interface Doc {
  key: string;
  text: string | null;
}

/**
 * 会话产物栏：列表为主 + 尽力而为的内嵌预览。
 *
 * 只对 md/text 取文本（取不到才退化卡片）；html/pdf/image 直接交给
 * iframe/img 渲染 —— 本后端所有路由对 HEAD 一律 404（只有 GET 可用），
 * 因此不用 HEAD 探测可用性，列表本身就是刚扫过磁盘的结果。
 * 选中项与加载态全部由 selRel 派生，effect 内不做同步 setState
 * （react-hooks v7 的 set-state-in-effect）；切会话由 Layout 的
 * key={sid} 重挂载来清空选中。
 */
export default function ArtifactsPanel({ sid, data, loading, error, width, refresh, onCollapse }: Props) {
  const [selRel, setSelRel] = useState<string | null>(null);
  const [doc, setDoc] = useState<Doc | null>(null);

  const items = data?.items ?? [];
  const external = data?.external ?? [];
  const active = selRel ? (items.find((i) => i.rel === selRel) ?? null) : null;
  const key = active && sid ? `${sid}:${active.rel}` : null;

  const tooBig = !!active && active.size > MAX_INLINE_BYTES;
  const needsDoc = !!active && !tooBig && (active.kind === "md" || active.kind === "text");
  const isFrame = !!active && (active.kind === "html" || active.kind === "pdf" || active.kind === "image");
  const docReady = key != null && doc?.key === key;
  const ready = !active || !needsDoc || docReady;
  const missing = needsDoc && docReady && doc?.text == null;

  useEffect(() => {
    if (!sid || !active || !key || !needsDoc || docReady) return;
    const url = artifactFileUrl(sid, active.rel);
    let alive = true;
    fetch(url)
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
      .then((t) => {
        if (alive) setDoc({ key, text: t });
      })
      .catch(() => {
        if (alive) setDoc({ key, text: null });
      });
    return () => {
      alive = false;
    };
  }, [sid, active, key, needsDoc, docReady]);

  const revealRel = (rel: string) => {
    if (!sid) return;
    void api.post(`/sessions/${sid}/artifacts/reveal`, { rel }).catch(() => undefined);
  };
  const revealAbs = (abs_path: string) => {
    if (!sid) return;
    void api.post(`/sessions/${sid}/artifacts/reveal`, { abs_path }).catch(() => undefined);
  };
  const copyPath = (p: string) => {
    void navigator.clipboard.writeText(p).catch(() => undefined);
  };

  // width 是用户拖拽得到的动态值，按仓库约定保留内联样式（见 CHANGELOG v1.9.0 C-2）
  return (
    <aside className="artifacts-panel" style={{ width }}>
      <div className="artifacts-head">
        <IconPackage size={15} />
        <span className="artifacts-title">会话产物</span>
        <span className="text-hint">{data?.count ?? 0}</span>
        <span className="artifacts-head-spacer" />
        <button type="button" className="artifacts-icon-btn" title="刷新" onClick={refresh}>
          <IconRefresh size={14} className={loading ? "spin" : undefined} />
        </button>
        <button type="button" className="artifacts-icon-btn" title="收起 (⌘B)" onClick={onCollapse}>
          <IconLayoutSidebarRight size={14} />
        </button>
      </div>

      {error && (
        <div className="artifacts-error">
          产物读取失败：{error}
          <button type="button" className="artifacts-link-btn" onClick={refresh}>
            重试
          </button>
        </div>
      )}

      <div className="artifacts-list">
        {!sid && <div className="artifacts-empty">还没有会话，发出一条消息后产物会归集到这里。</div>}
        {sid && items.length === 0 && !loading && (
          <div className="artifacts-empty">开始对话后，这次会话的产物会出现在这里。</div>
        )}
        {items.map((it) => (
          <div
            key={it.rel}
            className={`artifacts-row${selRel === it.rel ? " active" : ""}`}
            onClick={() => setSelRel(it.rel)}
            title={`${it.rel} · ${fmtSize(it.size)}`}
          >
            <KindIcon kind={it.kind} />
            <span className="artifacts-row-name">{it.name}</span>
            <span className="artifacts-row-meta">{fmtSize(it.size)}</span>
            <span className="artifacts-row-actions">
              <a
                className="artifacts-icon-btn"
                href={sid ? artifactFileUrl(sid, it.rel) : undefined}
                target="_blank"
                rel="noreferrer"
                title="在浏览器打开"
                onClick={(e) => e.stopPropagation()}
              >
                <IconExternalLink size={14} />
              </a>
              <a
                className="artifacts-icon-btn"
                href={sid ? artifactDownloadUrl(sid, it.rel) : undefined}
                title="下载"
                onClick={(e) => e.stopPropagation()}
              >
                <IconPackage size={14} />
              </a>
              <button
                type="button"
                className="artifacts-icon-btn"
                title="在 Finder 显示"
                onClick={(e) => {
                  e.stopPropagation();
                  revealRel(it.rel);
                }}
              >
                <IconFolderOpen size={14} />
              </button>
            </span>
          </div>
        ))}
        {data?.truncated && (
          <div className="text-hint artifacts-hint">产物较多，仅显示前 {items.length} 项，其余请到 Finder 查看。</div>
        )}
      </div>

      {external.length > 0 && (
        <details className="artifacts-external">
          <summary>会话外文件 · {external.length}</summary>
          {external.map((e) => (
            <div key={e.abs_path} className={`artifacts-row${e.exists ? "" : " stale"}`} title={e.abs_path}>
              <IconFile size={14} />
              <span className="artifacts-row-name">{e.abs_path.split(/[\\/]/).pop()}</span>
              <span className="artifacts-row-meta">{e.exists ? e.tool : "已失效"}</span>
              <span className="artifacts-row-actions">
                <button
                  type="button"
                  className="artifacts-icon-btn"
                  title="在 Finder 显示"
                  disabled={!e.exists}
                  onClick={() => revealAbs(e.abs_path)}
                >
                  <IconFolderOpen size={14} />
                </button>
                <button type="button" className="artifacts-icon-btn" title="复制路径" onClick={() => copyPath(e.abs_path)}>
                  <IconFileText size={14} />
                </button>
              </span>
            </div>
          ))}
        </details>
      )}

      {active && sid && (
        <div className="artifacts-preview">
          <div className="artifacts-preview-head">
            <span className="artifacts-row-name">{active.name}</span>
            <span className="text-hint">{fmtSize(active.size)}</span>
            <a className="artifacts-link-btn" href={artifactFileUrl(sid, active.rel)} target="_blank" rel="noreferrer">
              在浏览器打开
            </a>
            <button type="button" className="artifacts-icon-btn" title="关闭预览" onClick={() => setSelRel(null)}>
              <IconX size={14} />
            </button>
          </div>
          <div className="artifacts-preview-body">
            {!ready ? (
              <div className="artifacts-empty">加载中…</div>
            ) : missing || (!needsDoc && !isFrame) ? (
              <FallbackCard
                sid={sid}
                sel={active}
                reason={
                  missing
                    ? "文件已不可读或已被删除。"
                    : tooBig
                      ? "文件较大（>5MB），不提供内嵌预览。"
                      : "该类型不支持内嵌预览。"
                }
              />
            ) : isFrame && active.kind === "image" ? (
              <img className="artifacts-img" src={artifactFileUrl(sid, active.rel)} alt={active.name} />
            ) : isFrame ? (
              <iframe
                className="artifacts-frame"
                sandbox="allow-scripts"
                src={artifactFileUrl(sid, active.rel)}
                title={active.name}
              />
            ) : active.kind === "md" ? (
              <div className="artifacts-md">
                <Markdown text={doc?.text ?? ""} />
              </div>
            ) : (
              <CodeBlock>
                <code>{doc?.text ?? ""}</code>
              </CodeBlock>
            )}
          </div>
        </div>
      )}

      <div className="artifacts-foot">
        {sid ? (
          <a className="artifacts-link-btn" href={apiUrl(`/sessions/${sid}/artifacts/zip`)}>
            打包下载全部产物 (zip)
          </a>
        ) : (
          <span className="text-hint">尚无会话</span>
        )}
      </div>
    </aside>
  );
}
