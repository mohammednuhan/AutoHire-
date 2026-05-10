export type WebSocketCallback = (data: any) => void;

const DEFAULT_WS_URL =
  typeof window === "undefined"
    ? "ws://localhost:8000/ws"
    : `${window.location.protocol === "https:" ? "wss" : "ws"}://localhost:8000/ws`;

export const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? DEFAULT_WS_URL;

class AutoHireWebSocket {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private listeners: Map<string, WebSocketCallback[]> = new Map();
  private heartbeatId: ReturnType<typeof setInterval> | null = null;
  private reconnectId: ReturnType<typeof setTimeout> | null = null;
  private url = WS_URL;
  private manuallyClosed = false;

  connect(url: string = WS_URL) {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      return;
    }

    this.url = url;
    this.manuallyClosed = false;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      if (event.data === "pong") return;
      const data = JSON.parse(event.data);
      this.emit(data.event, data);
    };

    this.ws.onclose = () => {
      this.stopHeartbeat();
      if (!this.manuallyClosed) this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  disconnect() {
    this.manuallyClosed = true;
    this.stopHeartbeat();
    if (this.reconnectId) clearTimeout(this.reconnectId);
    this.ws?.close();
    this.ws = null;
  }

  private scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectId = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect(this.url);
    }, delay);
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatId = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send("ping");
      }
    }, 30000);
  }

  private stopHeartbeat() {
    if (this.heartbeatId) clearInterval(this.heartbeatId);
    this.heartbeatId = null;
  }

  on(event: string, callback: WebSocketCallback) {
    if (!this.listeners.has(event)) this.listeners.set(event, []);
    this.listeners.get(event)!.push(callback);
    return () => this.off(event, callback);
  }

  off(event: string, callback: WebSocketCallback) {
    const callbacks = this.listeners.get(event);
    if (!callbacks) return;
    this.listeners.set(
      event,
      callbacks.filter((registered) => registered !== callback),
    );
  }

  private emit(event: string, data: any) {
    this.listeners.get(event)?.forEach((callback) => callback(data));
    this.listeners.get("*")?.forEach((callback) => callback(data));
  }
}

export const wsClient = new AutoHireWebSocket();
