import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Full screen, requested once and never fought over.
 *
 * The room asks for full screen when the interview opens. If the browser
 * refuses — and it will, whenever the request is not tied to a user gesture, or
 * on iOS where the API barely exists — the room lays out to the viewport
 * anyway and the interview proceeds. Full screen is a nicety here, not a
 * dependency: `position: fixed; inset: 0` is what actually makes the room fill
 * the screen, and this only removes the browser chrome above it.
 *
 * **It never re-requests automatically.** A re-request on every
 * `fullscreenchange` produces a room that a candidate cannot leave — pressing
 * Escape puts it straight back — and a browser that is being fought is a
 * browser that starts blocking the request entirely. Exiting is recorded as an
 * integrity signal and offered back as a button, and that is the whole policy.
 */

interface LegacyFullscreenElement extends HTMLElement {
  webkitRequestFullscreen?: () => Promise<void> | void;
}

interface LegacyDocument extends Document {
  webkitFullscreenElement?: Element | null;
  webkitExitFullscreen?: () => Promise<void> | void;
}

export interface FullscreenState {
  supported: boolean;
  active: boolean;
  /** Resolves either way. A refusal is a normal outcome, not an error the
   * caller has to catch. */
  enter: () => Promise<void>;
  exit: () => Promise<void>;
}

export function useFullscreen(targetRef: React.RefObject<HTMLElement | null>): FullscreenState {
  const [active, setActive] = useState(false);
  const supportedRef = useRef(
    typeof document !== "undefined" &&
      (document.fullscreenEnabled || "webkitFullscreenElement" in document),
  );

  useEffect(() => {
    const sync = () => {
      const legacy = document as LegacyDocument;
      setActive((document.fullscreenElement ?? legacy.webkitFullscreenElement ?? null) !== null);
    };
    sync();
    document.addEventListener("fullscreenchange", sync);
    document.addEventListener("webkitfullscreenchange", sync);
    return () => {
      document.removeEventListener("fullscreenchange", sync);
      document.removeEventListener("webkitfullscreenchange", sync);
    };
  }, []);

  const enter = useCallback(async () => {
    const element = targetRef.current;
    if (!element) return;
    try {
      const legacy = element as LegacyFullscreenElement;
      if (element.requestFullscreen) {
        await element.requestFullscreen({ navigationUI: "hide" });
      } else if (legacy.webkitRequestFullscreen) {
        await legacy.webkitRequestFullscreen();
      }
    } catch {
      // Refused — usually because the call was not tied to a gesture. The room
      // is already laid out to fill the viewport, so there is nothing to undo.
    }
  }, [targetRef]);

  const exit = useCallback(async () => {
    try {
      const legacy = document as LegacyDocument;
      if (document.fullscreenElement && document.exitFullscreen) {
        await document.exitFullscreen();
      } else if (legacy.webkitFullscreenElement && legacy.webkitExitFullscreen) {
        await legacy.webkitExitFullscreen();
      }
    } catch {
      // Already out, or never in.
    }
  }, []);

  return { supported: supportedRef.current, active, enter, exit };
}
