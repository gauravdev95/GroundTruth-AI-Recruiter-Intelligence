import type { RoomPhase } from "../hooks/useInterviewRoom";
import { InterviewerPortrait } from "./InterviewerPortrait";

/**
 * The interviewer's tile — the primary visual element of the room.
 *
 * ## Three states, and only three
 *
 * SPEAKING, LISTENING, THINKING. Each has one visual carrier and one line of
 * text, and they are mutually exclusive by construction rather than by three
 * booleans that could all be true at once.
 *
 * The states are not decoration. A candidate cannot see whether their
 * microphone is being read, and the whole turn-taking contract of this room
 * depends on them knowing: "Listening" appears exactly when
 * `useSpeechRecognition` has actually opened the microphone, and disappears
 * exactly when it closes. Getting that indicator wrong is worse than not having
 * one, because a candidate who trusts it and talks into a closed microphone
 * loses the answer.
 *
 * ## The waveform is decorative, and says so
 *
 * The bars during SPEAKING are a fixed animation, not an analysis of the
 * synthesised audio. `speechSynthesis` gives no output stream to measure — the
 * audio goes straight to the device — so a "real" waveform here would mean
 * routing TTS through an audio graph the API does not expose. Fixed bars that
 * clearly mean "audio is playing" are honest; a fake spectrum drawn from a
 * random walk would be pretending to measure something.
 *
 * The candidate's own level meter is different and *is* real — see `SelfView`,
 * which reads an actual analyser node.
 */

const BAR_COUNT = 5;
/** Deliberately irregular. Five bars on the same duration read as a machine
 * ticking; five on prime-ish offsets read as a voice. */
const BAR_TIMINGS = [
  { height: 14, delay: 0, duration: 780 },
  { height: 26, delay: 120, duration: 940 },
  { height: 34, delay: 60, duration: 700 },
  { height: 22, delay: 200, duration: 880 },
  { height: 16, delay: 90, duration: 820 },
];

function SpeakingWaveform() {
  return (
    <div className="flex items-end gap-1.5" aria-hidden="true">
      {Array.from({ length: BAR_COUNT }, (_, index) => {
        const bar = BAR_TIMINGS[index];
        return (
          <span
            key={index}
            className="room-speak-bar w-1 rounded-full bg-[var(--room-accent)]"
            style={{
              height: `${bar.height}px`,
              animationDelay: `${bar.delay}ms`,
              animationDuration: `${bar.duration}ms`,
            }}
          />
        );
      })}
    </div>
  );
}

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1.5" aria-hidden="true">
      {[0, 200, 400].map((delay) => (
        <span
          key={delay}
          className="room-thinking-dot h-1.5 w-1.5 rounded-full bg-[var(--room-slate)]"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </div>
  );
}

/** What each phase puts under the interviewer, as one label and one carrier.
 *
 * `PROCESSING` and `THINKING` deliberately share copy. The candidate does not
 * need to know whether their words are in flight or the graph is running, and
 * "Analyzing your response" describes both truthfully without narrating the
 * machinery — which is the same reason the typed interview showed three dots
 * rather than "AI is thinking". */
const PHASE_LABEL: Record<RoomPhase, { label: string; tone: "accent" | "muted" | "caution" } | null> =
  {
    joining: { label: "Connecting to your interviewer", tone: "muted" },
    interviewer_speaking: { label: "Interviewer is speaking", tone: "accent" },
    listening: { label: "Listening", tone: "accent" },
    closing: { label: "Listening", tone: "accent" },
    processing: { label: "Analyzing your response", tone: "muted" },
    thinking: { label: "Analyzing your response", tone: "muted" },
    reconnecting: { label: "Reconnecting", tone: "caution" },
    completed: { label: "Interview complete", tone: "muted" },
    error: { label: "Connection problem", tone: "caution" },
  };

export interface AiInterviewerStageProps {
  phase: RoomPhase;
  speaking: boolean;
  /** The interviewer's current line, shown as a caption beneath the tile. */
  caption: string | null;
  /** True while the candidate is mid-sentence — drives the listening ring's
   * active intensity so the room visibly reacts to their voice. */
  candidateSpeaking: boolean;
  /** Shown when the interviewer's voice is muted, because a silent tile is
   * otherwise indistinguishable from a broken one. */
  muted: boolean;
}

export function AiInterviewerStage({
  phase,
  speaking,
  caption,
  candidateSpeaking,
  muted,
}: AiInterviewerStageProps) {
  const status = PHASE_LABEL[phase];
  const listening = phase === "listening" || phase === "closing";
  const thinking = phase === "thinking" || phase === "processing";

  const toneClass =
    status?.tone === "accent"
      ? "text-[var(--room-accent)]"
      : status?.tone === "caution"
        ? "text-[var(--room-caution)]"
        : "text-[var(--room-slate)]";

  return (
    <div className="relative flex h-full w-full flex-col items-center justify-center overflow-hidden">
      {/* The key light. A radial wash behind the subject rather than a gradient
          on the panel — the palette's rule 3, carried into the room. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(60% 55% at 50% 38%, var(--room-key-light) 0%, transparent 70%)",
        }}
      />

      <div className="relative flex flex-col items-center gap-5 px-6">
        <div className="relative">
          {/* The listening ring. Rendered only while listening so there is no
              chance of a stale ring implying an open microphone. */}
          {listening ? (
            <>
              <span
                aria-hidden="true"
                className="room-listen-pulse absolute inset-0 rounded-full border-2 border-[var(--room-accent)]"
              />
              <span
                aria-hidden="true"
                className="absolute inset-0 rounded-full border transition-colors duration-300"
                style={{
                  borderColor: candidateSpeaking
                    ? "var(--room-accent)"
                    : "var(--room-rule-strong)",
                }}
              />
            </>
          ) : null}

          <div
            className={[
              "relative h-[clamp(180px,26vh,300px)] w-[clamp(180px,26vh,300px)] overflow-hidden rounded-full",
              "border border-[var(--room-rule-strong)] bg-[var(--room-stage)]",
              "shadow-[0_24px_80px_-32px_rgb(0_0_0/0.9)]",
              speaking || listening ? "" : "room-breathe",
            ].join(" ")}
          >
            <InterviewerPortrait speaking={speaking} />
          </div>
        </div>

        <div className="flex flex-col items-center gap-3">
          <p className="font-display text-base font-semibold text-[var(--room-ink)]">
            AI Interviewer
          </p>

          {/* One status row. `aria-live` so a screen-reader user is told the
              microphone opened — they have no ring to look at, and the ring is
              the only other place that information exists. */}
          <div className="flex h-8 items-center gap-2.5" aria-live="polite">
            {speaking ? <SpeakingWaveform /> : null}
            {thinking ? <ThinkingDots /> : null}
            {listening ? (
              <span
                aria-hidden="true"
                className="h-2 w-2 rounded-full bg-[var(--room-accent)]"
                style={{ opacity: candidateSpeaking ? 1 : 0.5 }}
              />
            ) : null}
            {status ? (
              <span className={["text-sm font-medium", toneClass].join(" ")}>{status.label}</span>
            ) : null}
          </div>
        </div>
      </div>

      {/* The caption. Supporting information, deliberately: the interview is
          spoken, and this is here for a noisy room, a hard-of-hearing candidate
          or a word that did not survive the synthesiser — not as the primary
          channel. Two lines maximum, so it never becomes a chat log. */}
      {caption ? (
        <div className="pointer-events-none absolute inset-x-0 bottom-6 flex justify-center px-6">
          <p
            data-selectable
            className={[
              "pointer-events-auto max-w-2xl rounded-[var(--r-md)] px-4 py-2.5 text-center",
              "bg-[rgb(4_6_15/0.72)] text-[15px] leading-relaxed text-[var(--room-ink)]",
              "border border-[var(--room-rule)] backdrop-blur-sm",
              "line-clamp-3",
            ].join(" ")}
          >
            {caption}
            {muted ? (
              <span className="ml-2 text-xs text-[var(--room-caution)]">(voice muted)</span>
            ) : null}
          </p>
        </div>
      ) : null}
    </div>
  );
}
