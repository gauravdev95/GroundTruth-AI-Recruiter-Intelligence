import { useCallback, useEffect, useRef, useState } from "react";

import { isSpeechSynthesisSupported } from "../lib/speechCapabilities";

/**
 * The interviewer's voice.
 *
 * `speechSynthesis` rather than a cloud TTS vendor, for the reasons in
 * `lib/speechCapabilities.ts`. The interface here is the seam: `speak()`
 * resolves when the utterance finishes, and the room awaits it before it starts
 * listening again. A vendor swap replaces this file and nothing else.
 *
 * ## Voice choice is not cosmetic
 *
 * The default voice on most systems is the flat robotic one, which undoes the
 * work the Interviewer prompt does to sound like a person. `pickVoice` prefers
 * the natural/neural voices browsers ship under recognisable names, falls back
 * to any local en-* voice, and finally to whatever the platform gives — so the
 * interview sounds as good as the machine allows and still works on a machine
 * that allows nothing.
 *
 * ## Two browser bugs are handled here on purpose
 *
 * 1. **`getVoices()` is empty on first call** in Chrome — the list arrives
 *    asynchronously via `voiceschanged`. Reading it once at mount would pin the
 *    robotic default for the whole interview.
 * 2. **Chrome silently stops long utterances** after ~15 seconds. The keep-alive
 *    `pause()`/`resume()` tick is the standard workaround; without it the
 *    interviewer's longer questions cut off mid-sentence, which reads to the
 *    candidate as the AI losing its train of thought.
 */

export interface SpeechSynthesisState {
  supported: boolean;
  /** The interviewer is talking right now. The room reads this to hold the
   * microphone closed — see `useSpeechRecognition`'s note on barge-in. */
  speaking: boolean;
  /** Resolves when the utterance has been spoken, cancelled, or has failed.
   * Never rejects: a voice that will not play must not be able to wedge the
   * interview, and the room recovers by moving on to listening. */
  speak: (text: string) => Promise<void>;
  cancel: () => void;
  /** Muting only silences the interviewer's audio. It does not skip the turn —
   * the text still arrives, and the caption still shows it. */
  muted: boolean;
  setMuted: (muted: boolean) => void;
}

const KEEP_ALIVE_MS = 10_000;

/** Ordered by how natural they sound, best first. Matched case-insensitively
 * against `voice.name`. */
const PREFERRED_VOICE_HINTS = [
  "google us english",
  "microsoft aria",
  "microsoft jenny",
  "microsoft guy",
  "samantha",
  "natural",
  "neural",
];

function pickVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  if (voices.length === 0) return null;
  const english = voices.filter((voice) => voice.lang.toLowerCase().startsWith("en"));
  const pool = english.length > 0 ? english : voices;

  for (const hint of PREFERRED_VOICE_HINTS) {
    const match = pool.find((voice) => voice.name.toLowerCase().includes(hint));
    if (match) return match;
  }
  return pool.find((voice) => voice.localService) ?? pool[0] ?? null;
}

export function useSpeechSynthesis(): SpeechSynthesisState {
  const supported = isSpeechSynthesisSupported();
  const [speaking, setSpeaking] = useState(false);
  const [muted, setMuted] = useState(false);
  const voiceRef = useRef<SpeechSynthesisVoice | null>(null);
  const keepAliveRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mutedRef = useRef(muted);

  useEffect(() => {
    mutedRef.current = muted;
  }, [muted]);

  useEffect(() => {
    if (!supported) return;

    const load = () => {
      voiceRef.current = pickVoice(window.speechSynthesis.getVoices());
    };
    load();
    // See bug (1) above — the list is usually empty until this fires.
    window.speechSynthesis.addEventListener("voiceschanged", load);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", load);
  }, [supported]);

  const stopKeepAlive = useCallback(() => {
    if (keepAliveRef.current !== null) {
      clearInterval(keepAliveRef.current);
      keepAliveRef.current = null;
    }
  }, []);

  const cancel = useCallback(() => {
    stopKeepAlive();
    if (supported) window.speechSynthesis.cancel();
    setSpeaking(false);
  }, [stopKeepAlive, supported]);

  const speak = useCallback(
    (text: string): Promise<void> => {
      const trimmed = text.trim();
      if (!supported || !trimmed || mutedRef.current) return Promise.resolve();

      return new Promise<void>((resolve) => {
        // Anything still queued belongs to a turn that is over. Speaking it now
        // would have the interviewer finish its previous sentence on top of its
        // current one.
        window.speechSynthesis.cancel();

        const utterance = new SpeechSynthesisUtterance(trimmed);
        if (voiceRef.current) utterance.voice = voiceRef.current;
        utterance.lang = voiceRef.current?.lang ?? "en-US";
        // Slightly under default. Interview questions carry technical nouns,
        // and the default rate runs them together.
        utterance.rate = 0.96;
        utterance.pitch = 1;
        utterance.volume = 1;

        let settled = false;
        const finish = () => {
          if (settled) return;
          settled = true;
          stopKeepAlive();
          setSpeaking(false);
          resolve();
        };

        utterance.onstart = () => setSpeaking(true);
        utterance.onend = finish;
        // Resolve rather than reject — see the interface note. A failed voice
        // means the candidate reads the question instead of hearing it, which
        // is a worse interview, not a broken one.
        utterance.onerror = finish;

        stopKeepAlive();
        keepAliveRef.current = setInterval(() => {
          // Bug (2): the pause/resume pair is what keeps Chrome from cutting
          // the utterance at ~15s.
          if (!window.speechSynthesis.speaking) return;
          window.speechSynthesis.pause();
          window.speechSynthesis.resume();
        }, KEEP_ALIVE_MS);

        setSpeaking(true);
        window.speechSynthesis.speak(utterance);
      });
    },
    [stopKeepAlive, supported],
  );

  useEffect(() => {
    return () => {
      stopKeepAlive();
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, [stopKeepAlive]);

  const applyMuted = useCallback(
    (next: boolean) => {
      setMuted(next);
      mutedRef.current = next;
      if (next) cancel();
    },
    [cancel],
  );

  return { supported, speaking, speak, cancel, muted, setMuted: applyMuted };
}
