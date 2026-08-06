import { useEffect, useState } from "react";

import { Button, Modal } from "@/components";
import { cn } from "@/lib/utils";

import type { CloseReason } from "../api/pipelineApi";

const NOTE_MAX = 200;

const REASONS: { value: CloseReason; label: string }[] = [
  { value: "skills_gap", label: "Skills gap" },
  { value: "experience_mismatch", label: "Experience level mismatch" },
  { value: "role_filled", label: "Role filled" },
  { value: "other", label: "Other" },
];

export interface RejectionReasonModalProps {
  open: boolean;
  /** The card being closed, for the title. */
  candidateLabel: string;
  isSaving: boolean;
  /** Both handlers close the application. `Skip` passes nothing. */
  onSubmit: (feedback: { closeReason?: CloseReason; closeNote?: string }) => void;
  onCancel: () => void;
}

/**
 * The structured-feedback prompt shown when a candidate is closed.
 *
 * **Nothing here is required, and the design has to keep proving that.** Skip
 * is a real button that closes immediately, sits at the same visual weight as
 * Submit, and is what Escape and the backdrop resolve to. A required reason
 * is a reason recruiters learn to click past — after which the field contains
 * whichever option is first in the list, which is worse than no data at all
 * because it looks like data.
 *
 * The stakes are also worth being honest about in the copy: the reason
 * reaches the candidate and the matching engine, so the sentence says so.
 */
export function RejectionReasonModal({
  open,
  candidateLabel,
  isSaving,
  onSubmit,
  onCancel,
}: RejectionReasonModalProps) {
  const [reason, setReason] = useState<CloseReason | null>(null);
  const [note, setNote] = useState("");

  // Reset per opening. Without this, the previous candidate's reason is
  // pre-selected for the next one — an answer nobody gave, about someone
  // else.
  useEffect(() => {
    if (open) {
      setReason(null);
      setNote("");
    }
  }, [open]);

  const skip = () => onSubmit({});

  return (
    <Modal
      open={open}
      // Escape and backdrop resolve to *cancel*, not to skip: dismissing a
      // dialog is not a decision to close a candidate. The move only happens
      // through one of the two buttons.
      onClose={onCancel}
      title={`Close ${candidateLabel}`}
      className="max-w-md"
    >
      <div className="space-y-4">
        <p className="text-sm leading-relaxed text-slate-600">
          Reason for closing{" "}
          <span className="text-slate-400">(optional — helps the candidate and improves matching)</span>
        </p>

        <div className="space-y-1.5">
          {REASONS.map((option) => (
            <label
              key={option.value}
              className={cn(
                "flex cursor-pointer items-center gap-2.5 rounded border px-3 py-2 text-sm transition",
                reason === option.value
                  ? "border-ink bg-ink/5 font-medium text-ink"
                  : "border-slate-200 text-slate-600 hover:border-ink/30",
              )}
            >
              <input
                type="radio"
                name="close-reason"
                value={option.value}
                checked={reason === option.value}
                onChange={() => setReason(option.value)}
                className="h-3.5 w-3.5 accent-gt-electric"
              />
              {option.label}
            </label>
          ))}
        </div>

        <div className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between">
            <label htmlFor="close-note" className="text-sm font-medium text-slate-700">
              Note
            </label>
            <span className="tabular text-xs text-slate-400">
              {note.length}/{NOTE_MAX}
            </span>
          </div>
          <textarea
            id="close-note"
            rows={3}
            maxLength={NOTE_MAX}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Anything specific worth passing on."
            className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-ink focus:ring-2 focus:ring-verified/25"
          />
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-rule pt-4">
          <Button type="button" variant="ghost" onClick={skip} disabled={isSaving}>
            Skip
          </Button>
          <Button
            type="button"
            variant="destructive"
            isLoading={isSaving}
            onClick={() =>
              onSubmit({
                closeReason: reason ?? undefined,
                closeNote: note.trim() || undefined,
              })
            }
          >
            Submit &amp; close
          </Button>
        </div>
      </div>
    </Modal>
  );
}
