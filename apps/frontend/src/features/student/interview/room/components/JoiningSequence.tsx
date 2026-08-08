import { Check, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

/**
 * The moment between pressing Join and the interviewer speaking.
 *
 * There is real work happening behind this — a WebSocket handshake, the opening
 * turn's round-trip through LangGraph and the Interviewer agent — and it takes
 * a few seconds. A spinner would make those seconds feel like a bug. A checklist
 * that ticks makes them feel like joining a call, which is what they are.
 *
 * **The steps are real, not theatre.** Camera and microphone reflect the actual
 * permission state, and the last step resolves when the server's first turn
 * arrives. The only concession to pacing is the minimum dwell time on each
 * line: with a warm connection the whole sequence resolves faster than a person
 * can read it, and three lines flashing past is more disorienting than three
 * lines that land.
 */

const STEP_DWELL_MS = 550;

export interface JoiningSequenceProps {
  cameraReady: boolean;
  microphoneReady: boolean;
  /** True once the interviewer's first turn has arrived from the server. */
  interviewerReady: boolean;
}

export function JoiningSequence({
  cameraReady,
  microphoneReady,
  interviewerReady,
}: JoiningSequenceProps) {
  const [revealed, setRevealed] = useState(0);

  useEffect(() => {
    if (revealed >= 3) return;
    const timer = setTimeout(() => setRevealed((current) => current + 1), STEP_DWELL_MS);
    return () => clearTimeout(timer);
  }, [revealed]);

  const steps = [
    { label: "Checking your microphone", done: microphoneReady },
    { label: "Checking your camera", done: cameraReady },
    { label: "Connecting to your interviewer", done: interviewerReady },
  ];

  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-8 px-6">
      <div className="flex flex-col items-center gap-3">
        <div className="relative">
          <span
            aria-hidden="true"
            className="room-listen-pulse absolute inset-0 rounded-full border border-[var(--room-accent)]"
          />
          <div className="h-16 w-16 rounded-full border border-[var(--room-rule-strong)] bg-[var(--room-panel)]" />
        </div>
        <p className="font-display text-lg font-semibold text-[var(--room-ink)]">
          Preparing your interview
        </p>
      </div>

      <ul className="w-full max-w-xs space-y-3" aria-live="polite">
        {steps.slice(0, Math.max(1, revealed)).map((step) => (
          <li key={step.label} className="flex items-center gap-3 text-sm">
            {step.done ? (
              <Check size={15} className="shrink-0 text-[var(--room-accent)]" aria-hidden="true" />
            ) : (
              <Loader2
                size={15}
                className="shrink-0 animate-spin text-[var(--room-slate)]"
                aria-hidden="true"
              />
            )}
            <span className={step.done ? "text-[var(--room-slate)]" : "text-[var(--room-ink)]"}>
              {step.label}
              {step.done ? "" : "…"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
