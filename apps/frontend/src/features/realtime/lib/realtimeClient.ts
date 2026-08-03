import { refreshAccessToken } from "@/lib/apiClient";
import { getAccessToken } from "@/lib/tokenStore";

/**
 * A single WebSocket connection to `/api/v1/realtime/ws`, with the handshake
 * and reconnect policy the backend expects (`src/realtime/router.py`).
 *
 * ## Reconnect and backoff
 *
 * Exponential with equal jitter: attempt *n* waits somewhere in
 * `[d/2, d)` where `d = min(30s, 1s · 2ⁿ)`. Jitter matters more than the
 * curve here — an API restart drops every connected client at once, and
 * without it they would all come back in the same millisecond and do it
 * again on the next failure.
 *
 * The attempt counter resets on the server's `connected` frame, not on
 * `onopen`. A socket that opens and is then closed at authentication is not
 * a successful connection, and treating it as one would turn a permanently
 * rejected credential into a 1-second reconnect loop.
 *
 * Three things stop retrying entirely:
 *
 * * `close()` — an intentional teardown (unmount, logout).
 * * A `4401` close whose token refresh also fails: the session is genuinely
 *   over, and reconnecting with the same rejected credential cannot succeed.
 *   (A `4401` *with* a successful refresh reconnects immediately — the
 *   ordinary case of an access token expiring on a long-lived socket.)
 * * No access token at all — there is nothing to authenticate with, so the
 *   client waits to be started again after login rather than dialing.
 *
 * ## What happens to events sent while disconnected
 *
 * Nothing is replayed, and nothing needs to be: notification rows are
 * durable, so the `connected` frame is treated as "refetch everything you
 * care about" (see `useRealtimeEvents`). That recovers whatever was missed
 * regardless of how long the client was away — which a bounded server-side
 * buffer could not.
 */

const BASE_RECONNECT_DELAY_MS = 1_000;
const MAX_RECONNECT_DELAY_MS = 30_000;

/** Client-driven keepalive. Under the 60s idle timeout most proxies and load
 * balancers apply, so a connection that is merely quiet is not culled. The
 * server answers `ping` with `pong` (`realtime/router.py`). */
const PING_INTERVAL_MS = 25_000;

/** Application close codes from the server's private range. */
const CLOSE_AUTH_FAILED = 4401;

export interface RealtimeMessage {
  type: string;
  payload: Record<string, unknown>;
}

function socketUrl(): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? "";
  // `VITE_API_BASE_URL` is an absolute origin in development
  // (`http://localhost:8000/api/v1`) and a same-origin path in the built
  // image, so resolve against the page before swapping the scheme.
  const resolved = new URL(base, window.location.origin);
  resolved.protocol = resolved.protocol === "https:" ? "wss:" : "ws:";
  resolved.pathname = `${resolved.pathname.replace(/\/$/, "")}/realtime/ws`;
  return resolved.toString();
}

export class RealtimeClient {
  private socket: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private attempt = 0;
  private closedByUs = false;

  constructor(private readonly onMessage: (message: RealtimeMessage) => void) {}

  connect(): void {
    this.closedByUs = false;
    if (this.socket) return;

    const token = getAccessToken();
    if (!token) return;

    const socket = new WebSocket(socketUrl());
    this.socket = socket;

    socket.onopen = () => {
      // The credential goes in the first frame, never the URL — a query
      // parameter would put a live access token into every access log,
      // proxy trace and `Referer` header between here and the server.
      socket.send(JSON.stringify({ type: "authenticate", token }));
    };

    socket.onmessage = (event) => {
      let message: RealtimeMessage;
      try {
        message = JSON.parse(event.data as string) as RealtimeMessage;
      } catch {
        return;
      }
      if (message.type === "connected") {
        this.attempt = 0;
        this.startPinging();
      }
      if (message.type === "pong") return;
      this.onMessage(message);
    };

    socket.onclose = (event) => {
      this.socket = null;
      this.stopPinging();
      if (this.closedByUs) return;

      if (event.code === CLOSE_AUTH_FAILED) {
        void this.reconnectAfterRefresh();
        return;
      }
      this.scheduleReconnect();
    };

    // `onerror` is always followed by `onclose`, so reconnecting is left to
    // the close handler alone — doing it in both would double every retry.
    socket.onerror = () => {};
  }

  close(): void {
    this.closedByUs = true;
    this.stopPinging();
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.socket?.close();
    this.socket = null;
  }

  /** An access token that expired while the socket was open is the expected
   * cause of a 4401 on a long-lived connection. One refresh, then retry;
   * if the refresh fails the session is over and retrying is pointless. */
  private async reconnectAfterRefresh(): Promise<void> {
    const token = await refreshAccessToken();
    if (!token || this.closedByUs) return;
    this.attempt = 0;
    this.connect();
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer !== null) return;
    const ceiling = Math.min(MAX_RECONNECT_DELAY_MS, BASE_RECONNECT_DELAY_MS * 2 ** this.attempt);
    const delay = ceiling / 2 + Math.random() * (ceiling / 2);
    this.attempt += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  private startPinging(): void {
    this.stopPinging();
    this.pingTimer = setInterval(() => {
      if (this.socket?.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: "ping" }));
      }
    }, PING_INTERVAL_MS);
  }

  private stopPinging(): void {
    if (this.pingTimer !== null) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }
}
