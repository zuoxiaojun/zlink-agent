import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/http";
import type { ArtifactListResponse } from "../types";

interface Payload {
  sid: string;
  data: ArtifactListResponse;
}

/**
 * 会话产物列表。
 *
 * sid / version / nonce 任一变化即重新拉取；`loading` 与"数据是否属于当前
 * 会话"都由 `payload.sid` 派生，effect 内不做同步 setState（react-hooks
 * 的 set-state-in-effect 规则），切会话时也不会串上一个会话的文件。
 */
export function useSessionArtifacts(sid: string | null, version: number) {
  const [payload, setPayload] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const reqIdRef = useRef(0);

  useEffect(() => {
    if (!sid) return;
    const id = ++reqIdRef.current;
    let alive = true;
    api
      .get<ArtifactListResponse>(`/sessions/${sid}/artifacts`)
      .then((next) => {
        if (alive && id === reqIdRef.current) {
          setPayload({ sid, data: next });
          setError(null);
        }
      })
      .catch((e: unknown) => {
        if (!alive || id !== reqIdRef.current) return;
        const msg = e instanceof Error ? e.message : String(e);
        // 会话未落库 / 已被删除都走 404 → 空态而非报错
        if (/404|not found/i.test(msg)) {
          setPayload(null);
          setError(null);
        } else {
          setError(msg);
        }
      });
    return () => {
      alive = false;
    };
  }, [sid, version, nonce]);

  const data = sid && payload?.sid === sid ? payload.data : null;
  const loading = sid != null && data == null && error == null;
  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  return { data, loading, error, refresh };
}
