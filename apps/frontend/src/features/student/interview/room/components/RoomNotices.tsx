import { AlertTriangle, Info, X } from "lucide-react";
import { useEffect, useState } from "react";

import type { IntegrityEventType } from "../../api/interviewApi";
import type { IntegrityWarning } from "../hooks/useIntegrityMonitor";

/**
 * The room's two ways of telling a candidate something, and the line between
 * them.
 *
 * `IntegrityNotice` is for things about their session that have been recorded.
 * It is stated once, plainly, and it auto-dismisses — a warning that stays on
 * screen turns into an accusation the candidate has to keep looking at while
 * they are trying to answer a question about their code. Nothing here ends an
 * interview and nothing here says "cheating".
 *
 * `RoomNotice` is for things that are wrong with the room itself: a lost
 * connection, a device that stopped, a browser that cannot do voice. Those
 * persist, because they need an action.
 */

const AUTO_DISMISS_MS = 7_000;

export interface IntegrityNoticeProps {
  warning: IntegrityWarning | null;
  onDismiss: () => void;
}

export function IntegrityNotice({ warning, onDismiss }: IntegrityNoticeProps) {
  useEffect(() => {
    if (!warning) return;
    const timer = setTimeout(onDismiss, AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [warning, onDismiss]);

  if (!warning) return null;

  return (
    <div
      role="status"
      className="pointer-events-auto flex items-start gap-3 rounded-[var(--r-md)] border border-[rgb(255_180_84/0.3)] bg-[var(--room-caution-dim)] px-4 py-3 text-sm text-[var(--room-ink)] shadow-[0_16px_48px_-24px_rgb(0_0_0/0.9)] backdrop-blur-sm"
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0 text-[var(--room-caution)]" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="leading-snug">{warning.message}</p>
        {warning.count > 1 ? (
          <p className="mt-1 text-xs text-[var(--room-slate)]">
            Recorded {warning.count} times this session.
          </p>
        ) : null}
      </div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="shrink-0 rounded-full p-0.5 text-[var(--room-slate)] transition-colors hover:text-[var(--room-ink)]"
      >
        <X size={14} />
      </button>
    </div>
  );
}

export interface RoomNoticeProps {
  tone: "info" | "warning";
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
}

export function RoomNotice({ tone, title, description, action }: RoomNoticeProps) {
  const accent = tone === "warning" ? "var(--room-caution)" : "var(--room-accent)";
  return (
    <div
      role={tone === "warning" ? "alert" : "status"}
      className="pointer-events-auto flex items-start gap-3 rounded-[var(--r-md)] border border-[var(--room-rule-strong)] bg-[rgb(14_20_36/0.94)] px-4 py-3 shadow-[0_16px_48px_-24px_rgb(0_0_0/0.9)] backdrop-blur-sm"
    >
      {tone === "warning" ? (
        <AlertTriangle size={16} className="mt-0.5 shrink-0" style={{ color: accent }} aria-hidden="true" />
      ) : (
        <Info size={16} className="mt-0.5 shrink-0" style={{ color: accent }} aria-hidden="true" />
      )}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-[var(--room-ink)]">{title}</p>
        <p className="mt-0.5 text-xs leading-relaxed text-[var(--room-slate)]">{description}</p>
      </div>
      {action ? (
        <button
          type="button"
          onClick={action.onClick}
          className="shrink-0 rounded-full bg-[var(--room-raised)] px-3 py-1.5 text-xs font-medium text-[var(--room-ink)] transition-colors hover:bg-[rgb(30_40_64/1)]"
        >
          {action.label}
        </button>
      ) : null}
    </div>
  );
}

/**
 * The integrity record, on demand.
 *
 * Opened from the count in the top bar. It shows the candidate exactly what has
 * been written about their session, in the same words the recruiter will
 * eventually see — there is no version of this record that they are not allowed
 * to read.
 */
const EVENT_LABELS: Record<IntegrityEventType, string> = {
  tab_hidden: "Left the interview tab",
  window_blur: "Interview window lost focus",
  fullscreen_exit: "Exited full screen",
  camera_disabled: "Camera turned off",
  camera_unavailable: "Camera unavailable",
  camera_obscured: "Camera showed no image",
  microphone_disabled: "Microphone muted",
  microphone_unavailable: "Microphone unavailable",
  no_speech_detected: "No speech detected for a while",
  inactivity: "Extended inactivity",
  connection_lost: "Connection dropped",
};

export interface IntegrityLogProps {
  open: boolean;
  counts: Partial<Record<IntegrityEventType, number>>;
  onClose: () => void;
}

export function IntegrityLog({ open, counts, onClose }: IntegrityLogProps) {
  if (!open) return null;
  const entries = Object.entries(counts).filter(([, count]) => (count ?? 0) > 0);

  return (
    <div className="pointer-events-auto w-full max-w-sm rounded-[var(--r-md)] border border-[var(--room-rule-strong)] bg-[rgb(14_20_36/0.97)] p-4 shadow-[0_16px_48px_-24px_rgb(0_0_0/0.9)] backdrop-blur-sm">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-[var(--room-ink)]">Session events</p>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="rounded-full p-0.5 text-[var(--room-slate)] transition-colors hover:text-[var(--room-ink)]"
        >
          <X size={14} />
        </button>
      </div>

      <ul className="mt-3 space-y-1.5">
        {entries.map(([type, count]) => (
          <li key={type} className="flex items-baseline justify-between gap-3 text-xs">
            <span className="text-[var(--room-slate)]">
              {EVENT_LABELS[type as IntegrityEventType] ?? type}
            </span>
            <span className="machine tabular text-[var(--room-ink)]">{count}</span>
          </li>
        ))}
      </ul>

      <p className="mt-3 border-t border-[var(--room-rule)] pt-3 text-[11px] leading-relaxed text-[var(--room-muted)]">
        These describe the conditions of your session, not your answers. They are stored separately
        from the interview and are not part of your score.
      </p>
    </div>
  );
}

/**
 * The typed answer path.
 *
 * Shown when the browser has no speech recogniser, or when the candidate has
 * muted their own microphone. Deliberately a single line pinned to the bottom
 * of the room rather than a chat composer with a scrollback: the room is still
 * a room, and this is one control inside it, not a different product.
 */
export interface TypedAnswerBarProps {
  enabled: boolean;
  placeholder: string;
  onSubmit: (text: string) => void;
}

export function TypedAnswerBar({ enabled, placeholder, onSubmit }: TypedAnswerBarProps) {
  const [draft, setDraft] = useState("");

  const submit = () => {
    const trimmed = draft.trim();
    if (!trimmed || !enabled) return;
    onSubmit(trimmed);
    setDraft("");
  };

  return (
    <div className="pointer-events-auto flex w-full max-w-2xl items-end gap-2">
      <textarea
        data-selectable
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          // Enter sends, Shift+Enter breaks the line — the same contract the
          // typed interview used, because a technical answer runs to
          // paragraphs and the newline has to stay reachable without a mouse.
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
        disabled={!enabled}
        rows={1}
        placeholder={placeholder}
        aria-label="Type your answer"
        className="min-h-[44px] flex-1 resize-none rounded-[var(--r-md)] border border-[var(--room-rule-strong)] bg-[var(--room-raised)] px-3 py-2.5 text-sm text-[var(--room-ink)] placeholder:text-[var(--room-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--room-accent)]/40 disabled:opacity-50"
      />
      <button
        type="button"
        onClick={submit}
        disabled={!enabled || draft.trim().length === 0}
        className="h-11 rounded-[var(--r-md)] bg-[var(--room-accent-dim)] px-4 text-sm font-medium text-[var(--room-accent)] transition-colors hover:bg-[rgb(74_158_255/0.24)] disabled:cursor-not-allowed disabled:opacity-40"
      >
        Send
      </button>
    </div>
  );
}
