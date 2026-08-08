import { useCallback, useEffect, useRef, useState } from "react";

import { getAccessToken } from "@/lib/tokenStore";

import { interviewApi, type IntegrityEvent, type IntegrityEventType } from "../../api/interviewApi";

/**
 * What the room noticed about the conditions the interview was taken in.
 *
 * ## The rule this hook is written against
 *
 * **Observe, record, and say so. Never conclude, and never punish.**
 *
 * A browser can tell you that a tab lost visibility. It cannot tell you whether
 * that was a candidate looking something up, a calendar notification stealing
 * focus, a screen reader opening a menu, or a laptop going to sleep. Every
 * signal here is recorded as the thing the browser actually reported, the
 * candidate is told it was recorded, and no threshold in this file ends an
 * interview. What a recruiter does with a count of two is a policy question,
 * and policy does not belong in a hook.
 *
 * That also sets what this deliberately does **not** do: no face detection, no
 * gaze tracking, no second-person-in-frame detection, no keystroke analysis, no
 * screen capture. Those are the surveillance features the brief explicitly ruled
 * out, and none of them can be done honestly from a browser anyway — a webcam
 * that cannot see a face has as likely been covered as abandoned.
 *
 * ## Delivery
 *
 * Events queue locally and flush on a timer, plus immediately when the page is
 * hidden and on unload — the two moments most likely to be followed by the tab
 * never running JavaScript again. Unload uses `fetch(keepalive)` rather than
 * `sendBeacon` because the endpoint is authenticated and `sendBeacon` cannot
 * carry an `Authorization` header.
 *
 * Delivery is therefore at-least-once, which is why every event carries a
 * `client_sequence` the server dedupes on. A dropped batch is a lost signal, not
 * a corrupted record; a doubled batch is neither.
 */

export interface IntegrityMonitorOptions {
  interviewId: string | null;
  /** Only monitor while the interview is actually live. Recording tab switches
   * on the report screen would be recording somebody reading their results. */
  active: boolean;
  /** Seconds into the session, from the server's clock. Stamped on each event. */
  elapsedSeconds: () => number;
}

export interface IntegrityMonitorState {
  counts: Partial<Record<IntegrityEventType, number>>;
  /** The most recent thing worth telling the candidate about, or null. Cleared
   * by `dismissWarning`. */
  warning: IntegrityWarning | null;
  dismissWarning: () => void;
  /** Report something the room observed. Idempotent per call, not per
   * condition — the caller decides when a condition is new. */
  record: (
    eventType: IntegrityEventType,
    options?: { durationSeconds?: number; detail?: Record<string, string> },
  ) => void;
  flush: () => void;
}

export interface IntegrityWarning {
  eventType: IntegrityEventType;
  message: string;
  /** How many times this kind of thing has now happened. Shown because a
   * candidate has a right to know what their own record says. */
  count: number;
}

const FLUSH_INTERVAL_MS = 15_000;

/**
 * What the candidate is told, per signal.
 *
 * Written to be true and non-accusatory. "Switching tabs is recorded" is a
 * fact; "don't cheat" is an accusation aimed at the many people who did nothing
 * wrong. Signals with no entry are recorded silently — a camera the candidate
 * turned off themselves does not need a banner telling them they turned their
 * camera off.
 */
const WARNING_COPY: Partial<Record<IntegrityEventType, string>> = {
  tab_hidden:
    "Please stay on the interview screen. Leaving it is recorded as an interview integrity event.",
  window_blur:
    "The interview window lost focus. Please keep it in front while you're answering.",
  fullscreen_exit: "You've left full screen. Rejoin to keep the interview room in view.",
  camera_unavailable: "Your camera stopped. Check that nothing else is using it.",
  microphone_unavailable:
    "Your microphone stopped. Check that nothing else is using it, then reconnect.",
  no_speech_detected: "We haven't heard anything for a while — check your microphone is unmuted.",
  connection_lost: "The connection dropped. Nothing you've said is lost.",
};

export function useIntegrityMonitor({
  interviewId,
  active,
  elapsedSeconds,
}: IntegrityMonitorOptions): IntegrityMonitorState {
  const [counts, setCounts] = useState<Partial<Record<IntegrityEventType, number>>>({});
  const [warning, setWarning] = useState<IntegrityWarning | null>(null);

  const queueRef = useRef<IntegrityEvent[]>([]);
  const sequenceRef = useRef(0);
  const interviewIdRef = useRef(interviewId);
  const activeRef = useRef(active);
  const elapsedRef = useRef(elapsedSeconds);

  useEffect(() => {
    interviewIdRef.current = interviewId;
    activeRef.current = active;
    elapsedRef.current = elapsedSeconds;
  }, [interviewId, active, elapsedSeconds]);

  const flush = useCallback(() => {
    const id = interviewIdRef.current;
    if (!id || queueRef.current.length === 0) return;
    // Taken out of the queue before the request, so a slow flush cannot send
    // the same events twice. If it fails they are gone — see the delivery note:
    // losing a signal is acceptable, corrupting the record is not.
    const batch = queueRef.current.splice(0, queueRef.current.length);
    void interviewApi.recordIntegrity(id, batch).catch(() => undefined);
  }, []);

  /** The unload path. `fetch` with `keepalive` survives the document going
   * away; axios does not, and `sendBeacon` cannot carry the bearer token. */
  const flushBeacon = useCallback(() => {
    const id = interviewIdRef.current;
    const token = getAccessToken();
    if (!id || !token || queueRef.current.length === 0) return;
    const batch = queueRef.current.splice(0, queueRef.current.length);
    const base = import.meta.env.VITE_API_BASE_URL ?? "";
    try {
      void fetch(`${base}/student/interview/${id}/integrity`, {
        method: "POST",
        keepalive: true,
        credentials: "include",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ events: batch }),
      }).catch(() => undefined);
    } catch {
      // A page being torn down is not a place to handle errors.
    }
  }, []);

  const record = useCallback<IntegrityMonitorState["record"]>((eventType, options) => {
    if (!activeRef.current || !interviewIdRef.current) return;

    sequenceRef.current += 1;
    queueRef.current.push({
      client_sequence: sequenceRef.current,
      event_type: eventType,
      elapsed_seconds: Math.max(0, Math.floor(elapsedRef.current())),
      duration_seconds: options?.durationSeconds ?? null,
      detail: options?.detail ?? null,
    });

    setCounts((current) => {
      const next = { ...current, [eventType]: (current[eventType] ?? 0) + 1 };
      const message = WARNING_COPY[eventType];
      if (message) {
        setWarning({ eventType, message, count: next[eventType] ?? 1 });
      }
      return next;
    });
  }, []);

  // -- browser-observable signals -----------------------------------------
  //
  // Visibility and focus are two different questions and both are asked.
  // `visibilitychange` catches a tab switch or a minimised window; `blur` also
  // catches a second window taking focus while this one stays visible, which is
  // the case a candidate on two monitors produces and the one a visibility-only
  // implementation misses entirely.
  useEffect(() => {
    if (!active || !interviewId) return;

    let hiddenSince: number | null = null;

    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        hiddenSince = performance.now();
        flushBeacon();
        return;
      }
      const durationSeconds =
        hiddenSince === null ? undefined : Math.round((performance.now() - hiddenSince) / 1000);
      hiddenSince = null;
      // Recorded on *return*, not on leaving, so the event carries how long
      // they were away — a two-second notification and a four-minute absence
      // are different facts and should not collapse into one count.
      record("tab_hidden", { durationSeconds });
    };

    const onBlur = () => {
      // Only when the page is still visible; otherwise `visibilitychange` has
      // already covered it and this would double-count one alt-tab.
      if (document.visibilityState === "visible") record("window_blur");
    };

    const onFullscreenChange = () => {
      if (document.fullscreenElement === null) record("fullscreen_exit");
    };

    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("blur", onBlur);
    document.addEventListener("fullscreenchange", onFullscreenChange);
    window.addEventListener("pagehide", flushBeacon);

    const timer = setInterval(flush, FLUSH_INTERVAL_MS);

    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("blur", onBlur);
      document.removeEventListener("fullscreenchange", onFullscreenChange);
      window.removeEventListener("pagehide", flushBeacon);
      clearInterval(timer);
      flush();
    };
  }, [active, interviewId, record, flush, flushBeacon]);

  const dismissWarning = useCallback(() => setWarning(null), []);

  return { counts, warning, dismissWarning, record, flush };
}
