import type { WsClientMessage, WsServerMessage } from "../types";

export class ChatWebSocket {
  private ws: WebSocket | null = null;
  private onMessageCb: ((msg: WsServerMessage) => void) | null = null;
  private onCloseCb: (() => void) | null = null;
  private pending: WsClientMessage[] = [];

  connect(sessionId: string) {
    const electron = (window as unknown as Record<string, unknown>).electron as Record<string, string> | undefined;
    const url = electron
      ? `${electron.wsUrl}/ws/chat/${sessionId}`
      : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/chat/${sessionId}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      for (const msg of this.pending) {
        this.ws?.send(JSON.stringify(msg));
      }
      this.pending = [];
    };

    this.ws.onmessage = (event) => {
      try {
        const msg: WsServerMessage = JSON.parse(event.data);
        this.onMessageCb?.(msg);
      } catch {
        // ignore parse errors
      }
    };

    this.ws.onclose = () => {
      this.onCloseCb?.();
    };
  }

  send(msg: WsClientMessage) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    } else {
      this.pending.push(msg);
    }
  }

  onMessage(cb: (msg: WsServerMessage) => void) {
    this.onMessageCb = cb;
  }

  onClose(cb: () => void) {
    this.onCloseCb = cb;
  }

  close() {
    this.ws?.close();
    this.ws = null;
  }
}
