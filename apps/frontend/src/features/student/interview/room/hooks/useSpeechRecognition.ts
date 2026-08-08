import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getSpeechRecognitionCtor,
  isSubstantiveUtterance,
  type SpeechRecognitionErrorEventLike,
  type SpeechRecognitionEventLike,
  type SpeechRecognitionLike,
} from "../lib/speechCapabilities";

/**
 * The candidate's microphone, turned into finished answers.
 *
 * ## The one hard problem here is knowing when they have stopped talking
 *
 * A recogniser emits a stream of guesses. It does not know the difference
 * between "I've finished my answer" and "I'm deciding how to phrase the next
 * clause", and getting that wrong is the single thing that would make this feel
 * like a machine rather than an interview: cut in early and the AI talks over a
 * candidate mid-sentence; wait too long and every answer is followed by an
 * awkward hole.
 *
 * So end-of-utterance is decided here, from three signals together:
 *
 * 1. **Silence.** No new speech for `silenceMs` (default 2.2s). This is the
 *    primary signal and roughly matches the pause a person leaves before an
 *    interviewer picks up.
 * 2. **Substance.** The silence only ends the turn if what was said survives
 *    filler-stripping. Someone who says "umm..." and pauses to think has not
 *    finished answering, and a system that replied to that would be replying to
 *    a noise.
 * 3. **A ceiling.** After `maxUtteranceMs` of continuous speech the turn is
 *    submitted regardless. A recogniser that never falls silent — an open
 *    window, a fan, a candidate who genuinely does not pause — must not be able
 *    to hold the interview open forever.
 *
 * ## Barge-in is prevented by not listening
 *
 * `pause()` is called for the whole time the interviewer is speaking, because
 * the alternative is the recogniser transcribing the AI's own voice out of the
 * candidate's speakers and submitting it as their answer. This is why the room
 * shows "Listening…" only after the interviewer has actually stopped: it is not
 * a decorative state, it is the literal truth about whether the microphone is
 * being read.
 *
 * ## Restart, and why the `onend` handler is not a bug
 *
 * Chromium ends a recognition session on its own every so often — after a long
 * silence, or when it decides a phrase is complete. Continuous listening is
 * therefore a loop: whenever the session ends and we still want to be
 * listening, start a new one. `wantsToListenRef` is what distinguishes that
 * from a stop we asked for, and without it the recogniser either dies silently
 * mid-interview or refuses to stop when told.
 */

export interface UseSpeechRecognitionOptions {
  /** Called once per finished answer, with the full text of it. */
  onUtterance: (text: string) => void;
  /** How long a pause ends a turn. */
  silenceMs?: number;
  /** Hard ceiling on one uninterrupted answer. */
  maxUtteranceMs?: number;
  /** Recogniser language tag. */
  lang?: string;
  onError?: (error: string) => void;
}

export interface SpeechRecognitionState {
  supported: boolean;
  /** The microphone is being read right now. */
  listening: boolean;
  /** The candidate is mid-sentence: speech has been detected since the last
   * emitted answer. Drives the "Listening…" indicator's active state. */
  speaking: boolean;
  /** Best-guess text so far, for live captions. Never submitted as-is. */
  interim: string;
  error: string | null;
  start: () => void;
  stop: () => void;
  /** Stop reading the microphone without discarding intent — used while the
   * interviewer speaks, and resumed with `start()` afterwards. */
  pause: () => void;
  /** Submit whatever has been heard so far, immediately. Backs the room's
   * "Done answering" button, for a candidate who would rather not wait out the
   * silence timer. */
  flush: () => void;
}

const DEFAULT_SILENCE_MS = 2_200;
const DEFAULT_MAX_UTTERANCE_MS = 120_000;

/**
 * What each recogniser failure actually means to the person it happened to.
 *
 * The raw `event.error` codes were being surfaced verbatim, which meant a
 * candidate whose speech service was unreachable saw the word "network" and
 * nothing else. Every one of these is recoverable and the candidate is the only
 * person who can recover it, so each says what to do.
 *
 * `network` is first because it is the common one: Chromium's recogniser is a
 * *cloud* service, so an offline machine — or a firewall, or a VPN — produces a
 * room that looks like it is listening and can never hear anything.
 */
const SPEECH_ERROR_COPY: Record<string, string> = {
  network:
    "Speech recognition can't reach your browser's speech service. Check your internet connection — you can type your answers meanwhile.",
  "not-allowed":
    "Microphone access was blocked. Allow it from the icon in your browser's address bar, then reload.",
  "service-not-allowed":
    "Your browser blocked its speech service. Type your answers, or try Chrome.",
  "audio-capture":
    "No microphone could be captured. Another application may be using it — close it and try again.",
  "bad-grammar": "The recogniser rejected its configuration. Please type your answer.",
  "language-not-supported": "This language isn't supported by your browser's recogniser.",
};

export function useSpeechRecognition({
  onUtterance,
  silenceMs = DEFAULT_SILENCE_MS,
  maxUtteranceMs = DEFAULT_MAX_UTTERANCE_MS,
  lang = "en-US",
  onError,
}: UseSpeechRecognitionOptions): SpeechRecognitionState {
  const ctor = useMemo(() => getSpeechRecognitionCtor(), []);
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const wantsToListenRef = useRef(false);
  const finalTextRef = useRef("");
  /** Mirrors the `interim` state. The silence timer reads this rather than the
   * state value because it is created inside a `useCallback` whose closure
   * would otherwise capture whatever `interim` was when the timer was armed. */
  const interimRef = useRef("");
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ceilingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Held in refs so the recogniser's event handlers — bound once, for the life
  // of the session — always call the current render's callbacks rather than the
  // ones that existed when the session started.
  const onUtteranceRef = useRef(onUtterance);
  const onErrorRef = useRef(onError);
  useEffect(() => {
    onUtteranceRef.current = onUtterance;
    onErrorRef.current = onError;
  }, [onUtterance, onError]);

  const clearTimers = useCallback(() => {
    if (silenceTimerRef.current !== null) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (ceilingTimerRef.current !== null) {
      clearTimeout(ceilingTimerRef.current);
      ceilingTimerRef.current = null;
    }
  }, []);

  /** Hand off whatever has accumulated, if it is worth handing off. */
  const emit = useCallback(() => {
    clearTimers();
    const text = finalTextRef.current.trim();
    finalTextRef.current = "";
    interimRef.current = "";
    setInterim("");
    setSpeaking(false);
    if (!text) return;
    onUtteranceRef.current(text);
  }, [clearTimers]);

  const scheduleSilenceCheck = useCallback(() => {
    if (silenceTimerRef.current !== null) clearTimeout(silenceTimerRef.current);
    silenceTimerRef.current = setTimeout(() => {
      silenceTimerRef.current = null;

      // Promote interim text before judging it.
      //
      // This was a hang. Chrome under `continuous: true` will happily emit
      // interim results and then go quiet without ever marking a result
      // `isFinal` — especially on a short answer. The gate only ever read
      // `finalTextRef`, so in that case it saw an empty string, declined to
      // emit, and *did not reschedule itself* (the timer is only re-armed by
      // the next `onresult`). The candidate had spoken, the words were on
      // screen as interim captions, and the turn never submitted. Nothing in
      // the UI could show this — it looked exactly like the interviewer
      // ignoring them.
      //
      // Two seconds of silence means they have stopped talking, so the best
      // guess the recogniser has is the answer.
      if (!finalTextRef.current.trim() && interimRef.current.trim()) {
        finalTextRef.current = interimRef.current.trim();
      }

      // Substance gate. A pause after "umm" is thinking, not an answer, so the
      // recogniser keeps running and the candidate keeps their turn.
      if (isSubstantiveUtterance(finalTextRef.current)) emit();
    }, silenceMs);
  }, [emit, silenceMs]);

  const startCeiling = useCallback(() => {
    if (ceilingTimerRef.current !== null) return;
    ceilingTimerRef.current = setTimeout(() => {
      ceilingTimerRef.current = null;
      if (finalTextRef.current.trim()) emit();
    }, maxUtteranceMs);
  }, [emit, maxUtteranceMs]);

  const buildRecognition = useCallback((): SpeechRecognitionLike | null => {
    if (!ctor) return null;
    const recognition = new ctor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = lang;
    recognition.maxAlternatives = 1;

    recognition.onspeechstart = () => {
      setSpeaking(true);
      startCeiling();
    };

    recognition.onresult = (event: SpeechRecognitionEventLike) => {
      let pendingInterim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const alternative = result[0];
        if (!alternative) continue;
        if (result.isFinal) {
          finalTextRef.current = `${finalTextRef.current} ${alternative.transcript}`.trim();
        } else {
          pendingInterim += alternative.transcript;
        }
      }
      interimRef.current = pendingInterim;
      setInterim(pendingInterim);
      setSpeaking(true);
      setError(null);
      startCeiling();
      scheduleSilenceCheck();
    };

    recognition.onerror = (event: SpeechRecognitionErrorEventLike) => {
      // `no-speech` and `aborted` are the recogniser reporting normal life —
      // a quiet stretch, or our own `stop()` landing — and surfacing them
      // would put an error banner in front of a candidate who is simply
      // thinking. Everything else is real and worth showing.
      if (event.error === "no-speech" || event.error === "aborted") return;
      setError(SPEECH_ERROR_COPY[event.error] ?? `Speech recognition failed (${event.error}).`);
      onErrorRef.current?.(event.error);
    };

    recognition.onend = () => {
      // See the module docstring: Chromium ends sessions unprompted, so a loop
      // is the only way to listen continuously.
      if (!wantsToListenRef.current) {
        setListening(false);
        return;
      }
      try {
        recognition.start();
      } catch {
        // `start()` throws if the previous session has not fully torn down.
        // The next `onend` will come around; dropping this one is correct.
        setListening(false);
      }
    };

    return recognition;
  }, [ctor, lang, scheduleSilenceCheck, startCeiling]);

  const start = useCallback(() => {
    if (!ctor) return;
    wantsToListenRef.current = true;
    if (!recognitionRef.current) recognitionRef.current = buildRecognition();
    try {
      recognitionRef.current?.start();
      setListening(true);
    } catch {
      // Already running. That is exactly the state `start()` was asking for.
      setListening(true);
    }
  }, [buildRecognition, ctor]);

  const pause = useCallback(() => {
    wantsToListenRef.current = false;
    clearTimers();
    setSpeaking(false);
    interimRef.current = "";
    setInterim("");
    // `abort()`, not `stop()`: `stop()` finalises what it has heard so far and
    // fires one last `onresult`, which — when the reason we are pausing is that
    // the interviewer started speaking — would be the AI's own first words
    // arriving as the candidate's answer.
    recognitionRef.current?.abort();
    setListening(false);
  }, [clearTimers]);

  const stop = useCallback(() => {
    wantsToListenRef.current = false;
    clearTimers();
    finalTextRef.current = "";
    interimRef.current = "";
    setInterim("");
    setSpeaking(false);
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    setListening(false);
  }, [clearTimers]);

  const flush = useCallback(() => {
    const text = `${finalTextRef.current} ${interimRef.current}`.trim();
    finalTextRef.current = text;
    // No substance gate here. The candidate pressed a button that says they are
    // finished; second-guessing that is the room telling them they are wrong
    // about their own answer.
    emit();
  }, [emit]);

  useEffect(() => {
    return () => {
      wantsToListenRef.current = false;
      clearTimers();
      recognitionRef.current?.abort();
      recognitionRef.current = null;
    };
  }, [clearTimers]);

  return {
    supported: ctor !== null,
    listening,
    speaking,
    interim,
    error,
    start,
    stop,
    pause,
    flush,
  };
}
