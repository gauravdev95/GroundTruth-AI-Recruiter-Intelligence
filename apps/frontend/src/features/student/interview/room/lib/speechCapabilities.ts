/**
 * The browser speech seam.
 *
 * ## Why the browser, and not a vendor
 *
 * The live interview was built text-first because no STT/TTS vendor had been
 * chosen, and choosing one is not a frontend decision: every cloud recogniser
 * means an API key, an audio upload path, a per-minute cost and a second
 * provider sitting beside the single-provider rule in `domains/ai/llm.py`. The
 * room needs voice *now*, so it runs on the Web Speech API — which needs no
 * key, no backend route, and no new dependency.
 *
 * Everything vendor-specific is behind this module and the two hooks that use
 * it (`useSpeechRecognition`, `useSpeechSynthesis`). Swapping in Deepgram,
 * Whisper or Gemini Live later means reimplementing those three files against
 * the same interfaces; the room itself never touches a `SpeechRecognition`
 * object.
 *
 * ## What this costs, stated plainly
 *
 * `SpeechRecognition` ships in Chrome, Edge and other Chromium browsers. It
 * does **not** ship in Firefox, and Safari's implementation is unreliable
 * enough that we do not claim it. On those browsers the room stays a room —
 * same video call, same AI interviewer, same voice output — and the candidate
 * types their answers into the composer instead of speaking them. That is a
 * degraded experience, not a broken one, and it is far better than telling
 * somebody their browser cannot run their interview.
 *
 * Chromium's recogniser streams audio to Google for transcription. That is a
 * third party hearing the candidate's voice, so the device-check screen says so
 * before the microphone is ever opened rather than burying it in a policy page.
 */

/** Chromium exposes this unprefixed on newer versions and prefixed on older
 * ones; neither is in TypeScript's DOM lib, hence the local declarations. */
interface SpeechRecognitionAlternativeLike {
  readonly transcript: string;
  readonly confidence: number;
}

interface SpeechRecognitionResultLike {
  readonly isFinal: boolean;
  readonly length: number;
  [index: number]: SpeechRecognitionAlternativeLike;
}

interface SpeechRecognitionResultListLike {
  readonly length: number;
  [index: number]: SpeechRecognitionResultLike;
}

export interface SpeechRecognitionEventLike extends Event {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultListLike;
}

export interface SpeechRecognitionErrorEventLike extends Event {
  readonly error: string;
  readonly message: string;
}

export interface SpeechRecognitionLike extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
  onspeechstart: (() => void) | null;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

interface SpeechCapableWindow {
  SpeechRecognition?: SpeechRecognitionCtor;
  webkitSpeechRecognition?: SpeechRecognitionCtor;
}

export function getSpeechRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const candidate = window as unknown as SpeechCapableWindow;
  return candidate.SpeechRecognition ?? candidate.webkitSpeechRecognition ?? null;
}

export function isSpeechRecognitionSupported(): boolean {
  return getSpeechRecognitionCtor() !== null;
}

export function isSpeechSynthesisSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function isMediaCaptureSupported(): boolean {
  return (
    typeof navigator !== "undefined" &&
    typeof navigator.mediaDevices?.getUserMedia === "function"
  );
}

export interface SpeechSupport {
  /** The candidate can answer by speaking. */
  recognition: boolean;
  /** The interviewer can be heard rather than only read. */
  synthesis: boolean;
  /** Camera and microphone can be opened at all. Without this there is no
   * interview room to enter, only the typed fallback. */
  capture: boolean;
}

export function detectSpeechSupport(): SpeechSupport {
  return {
    recognition: isSpeechRecognitionSupported(),
    synthesis: isSpeechSynthesisSupported(),
    capture: isMediaCaptureSupported(),
  };
}

/**
 * Tokens a recogniser emits that carry no answer.
 *
 * Used to decide whether a pause in speech ended an *answer* or merely a
 * sentence the candidate is still assembling — see `useSpeechRecognition`. Kept
 * deliberately short: this list only has to catch the sounds people make while
 * thinking, and every additional word is a chance to silently delete something
 * a candidate actually said.
 */
export const FILLER_TOKENS: ReadonlySet<string> = new Set([
  "um",
  "umm",
  "uh",
  "uhh",
  "hmm",
  "hm",
  "mmm",
  "mm",
  "er",
  "err",
  "ah",
  "oh",
  "like",
  "so",
  "okay",
  "ok",
  "right",
  "yeah",
  "well",
]);

/** Words that survive filler-stripping. */
export function meaningfulWords(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s'-]/gu, " ")
    .split(/\s+/)
    .filter((word) => word.length > 0 && !FILLER_TOKENS.has(word));
}

/**
 * Is this a finished answer, or a candidate drawing breath?
 *
 * Two words and six characters after fillers are stripped. Both thresholds are
 * low on purpose: "yes, exactly" and "the queue" are real answers to real
 * follow-ups, and the cost of being wrong in the strict direction — swallowing
 * a short true answer and leaving the candidate waiting on an interviewer that
 * never replies — is much worse than the cost of being wrong in the loose one,
 * which is one turn spent on a thin answer that the graph already knows how to
 * probe.
 */
export function isSubstantiveUtterance(text: string): boolean {
  const words = meaningfulWords(text);
  return words.length >= 2 && words.join("").length >= 6;
}
