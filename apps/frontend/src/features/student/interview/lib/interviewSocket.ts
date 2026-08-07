import { refreshAccessToken } from "@/lib/apiClient";
import { getAccessToken } from "@/lib/tokenStore";

import type { InterviewState } from "../api/interviewApi";

/**
 * The live interview's WebSocket, one per session
 * (`/api/v1/student/interview/{id}/live`).
 *
 * Deliberately a separate client from `realtime/lib/realtimeClient.ts` rather
 * than a mode of it. That one is a single long-lived notification socket for
 * the whole app: server-to-client only, shared by every feature, and its
 * `connected` frame means "refetch your queries". This one is scoped to one
 * interview, carries the conversation in both directions, and its frames *are*
 * the state. Folding them together would put a candidate's interview inside the
 * socket that reconnects whenever any part of the app does.
 *
 * ## What survives a disconnect
 *
 * Everything. The server holds the transcript, so a reconnect re-sends the
 * whole session in its `connected` frame and the UI redraws from that. Nothing
 * the candidate said is buffered here — a message is only ever displayed once
 * the server has written it, which is why an interrupted send shows as not
 * having happened rather than as maybe-having-happened.
 *
 * Reconnect policy mirrors `RealtimeClient`: exponential backoff with equal
 * jitter, the attempt counter resetting on `connected` rather than `onopen`,
 * and a single token refresh on a 4401 before giving up.
 */

const BASE_RECONNECT_DELAY_MS = 1_000;
const MAX_RECONNECT_DELAY_MS = 15_000;
const PING_INTERVAL_MS = 25_000;

const CLOSE_AUTH_FAILED = 4401;
/** Authenticated fine, but has no business on this interview. Never retried:
 * reconnecting cannot change whose interview it is. */
const CLOSE_FORBIDDEN = 4403;

export type InterviewSocketEvent =
  | { type: "connected"; state: InterviewState }
  | { type: "state"; state: InterviewState }
  | { type: "thinking" }
  | { type: "error"; code: string; message: string }
  | { type: "closed"; permanent: boolean };

function socketUrl(interviewId: string): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? "";
  // `VITE_API_BASE_URL` is an absolute origin in development
  // (`http://localhost:8000/api/v1`) and a same-origin path in the built
  // image, so resolve against the page before swapping the scheme.
  const resolved = new URL(base, window.location.origin);
  resolved.protocol = resolved.protocol === "https:" ? "wss:" : "ws:";
  resolved.pathname = `${resolved.pathname.replace(/\/$/, "")}/student/interview/${interviewId}/live`;
  return resolved.toString();
}

export class InterviewSocket {
  private socket: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private attempt = 0;
  private closedByUs = false;

  constructor(
    private readonly interviewId: string,
    private readonly onEvent: (event: InterviewSocketEvent) => void,
  ) {}

  connect(): void {
    this.closedByUs = false;
    if (this.socket) return;

    const token = getAccessToken();
    if (!token) return;

    const socket = new WebSocket(socketUrl(this.interviewId));
    this.socket = socket;

    socket.onopen = () => {
      // The credential goes in the first frame, never the URL — a query
      // parameter would put a live access token into every access log.
      socket.send(JSON.stringify({ type: "authenticate", token }));
    };

    socket.onmessage = (event) => {
      let frame: { type: string; payload?: unknown };
      try {
        frame = JSON.parse(event.data as string) as { type: string; payload?: unknown };
      } catch {
        return;
      }

      switch (frame.type) {
        case "connected":
          this.attempt = 0;
          this.startPinging();
          this.onEvent({ type: "connected", state: frame.payload as InterviewState });
          return;
        case "state":
          this.onEvent({ type: "state", state: frame.payload as InterviewState });
          return;
        case "thinking":
          this.onEvent({ type: "thinking" });
          return;
        case "error": {
          const payload = (frame.payload ?? {}) as { code?: string; message?: string };
          this.onEvent({
            type: "error",
            code: payload.code ?? "UNKNOWN",
            message: payload.message ?? "Something went wrong.",
          });
          return;
        }
        default:
          return;
      }
    };

    socket.onclose = (event) => {
      this.socket = null;
      this.stopPinging();
      if (this.closedByUs) return;

      if (event.code === CLOSE_FORBIDDEN) {
        this.onEvent({ type: "closed", permanent: true });
        return;
      }
      if (event.code === CLOSE_AUTH_FAILED) {
        void this.reconnectAfterRefresh();
        return;
      }
      this.onEvent({ type: "closed", permanent: false });
      this.scheduleReconnect();
    };

    // `onerror` is always followed by `onclose`, so reconnecting is left to
    // the close handler alone — doing it in both would double every retry.
    socket.onerror = () => {};
  }

  /** True when a message can actually be sent right now. The caller falls back
   * to the REST route when it is not — see `useLiveInterview`. */
  get isOpen(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  send(text: string): boolean {
    if (!this.isOpen) return false;
    this.socket?.send(JSON.stringify({ type: "candidate_message", text }));
    return true;
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

  private async reconnectAfterRefresh(): Promise<void> {
    const token = await refreshAccessToken();
    if (!token || this.closedByUs) {
      this.onEvent({ type: "closed", permanent: true });
      return;
    }
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
