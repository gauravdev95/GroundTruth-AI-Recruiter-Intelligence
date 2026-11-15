import { X } from "lucide-react";
import { useEffect, useRef } from "react";

import type { InterviewTurn } from "../../api/interviewApi";

/**
 * The transcript, behind a button.
 *
 * ## Why it is a drawer and not the interface
 *
 * The old interview *was* this panel — bubbles, a composer, a send button — and
 * the whole point of the rebuild is that a transcript is a record of a
 * conversation, not the conversation itself. Making it the primary surface is
 * what made the previous version feel like a chatbot, so here it is available,
 * closed by default, and never opens itself.
 *
 * It stays available because it is genuinely useful: a candidate who missed a
 * word, or whose speakers failed, or who wants to check they answered what was
 * asked, should not have to ask the interviewer to repeat itself. It is also
 * the honest record of what the room heard — a candidate should be able to see
 * that their speech was transcribed as they said it, since that transcription
 * is what gets scored.
 *
 * `internal_notes` is not here and cannot be: `TurnResponse` on the server
 * omits it deliberately, so the Interviewer's private read on an answer is not
 * available to this component even if someone tried to render it.
 */

export interface TranscriptPanelProps {
  open: boolean;
  transcript: InterviewTurn[];
  /** What the candidate is currently saying, un-submitted. Shown greyed so the
   * difference between "heard" and "sent" is visible. */
  interim: string;
  onClose: () => void;
}

export function TranscriptPanel({ open, transcript, interim, onClose }: TranscriptPanelProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [open, transcript.length, interim]);

  if (!open) return null;

  return (
    <aside
      className={[
        "flex w-full max-w-sm shrink-0 flex-col border-l border-[var(--room-rule)] bg-[var(--room-panel)]",
        // On laptop the panel sits beside the stage; on a tablet it would
        // squeeze the interviewer into a strip, so below `lg` it overlays
        // instead. Same component, same props — only the placement changes.
        "max-lg:absolute max-lg:inset-y-0 max-lg:right-0 max-lg:z-30 max-lg:w-[min(22rem,88vw)] max-lg:border-l max-lg:shadow-[-24px_0_64px_-24px_rgb(0_0_0/0.9)]",
      ].join(" ")}
      aria-label="Interview transcript"
    >
      <div className="flex items-center justify-between border-b border-[var(--room-rule)] px-4 py-3">
        <p className="text-sm font-medium text-[var(--room-ink)]">
          Transcript
          {transcript.length > 0 ? (
            <span className="ml-2 text-xs font-normal tabular-nums text-[var(--room-muted)]">
              {transcript.length} {transcript.length === 1 ? "turn" : "turns"}
            </span>
          ) : null}
        </p>
        <button
          type="button"
          onClick={onClose}
          aria-label="Hide transcript"
          className="rounded-full p-1.5 text-[var(--room-slate)] transition-colors hover:bg-[var(--room-raised)] hover:text-[var(--room-ink)]"
        >
          <X size={16} />
        </button>
      </div>

      <div data-selectable className="flex-1 space-y-5 overflow-y-auto px-4 py-4">
        {transcript.length === 0 ? (
          <div className="flex flex-col items-start gap-1.5 pt-2">
            <p className="text-sm font-medium text-[var(--room-ink)]">Nothing yet</p>
            <p className="text-sm leading-relaxed text-[var(--room-muted)]">
              The conversation will appear here as it happens — what the room hears is what
              gets scored.
            </p>
          </div>
        ) : null}

        {transcript.map((turn) => (
          <div key={turn.id} className="space-y-1">
            <p className="flex flex-wrap items-baseline gap-x-2 text-[11px] font-medium uppercase tracking-wide text-[var(--room-muted)]">
              <span>{turn.role === "interviewer" ? "Interviewer" : "You"}</span>
              <span className="machine normal-case tracking-normal">
                {new Date(turn.spoken_at).toLocaleTimeString()}
              </span>
            </p>
            <p
              className={[
                "text-sm leading-relaxed",
                turn.role === "interviewer" ? "text-[var(--room-ink)]" : "text-[var(--room-slate)]",
              ].join(" ")}
            >
              {turn.text}
            </p>
          </div>
        ))}

        {interim ? (
          <div className="space-y-1 opacity-60">
            <p className="text-[11px] font-medium uppercase tracking-wide text-[var(--room-muted)]">
              You (speaking)
            </p>
            <p className="text-sm italic leading-relaxed text-[var(--room-slate)]">{interim}</p>
          </div>
        ) : null}

        <div ref={endRef} />
      </div>
    </aside>
  );
}
