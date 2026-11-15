import { ShieldCheck, Wifi, WifiOff } from "lucide-react";

import type { ConnectionState } from "../../hooks/useInterview";

/**
 * The room's header: who is interviewing, how long is left, and whether the
 * connection is up.
 *
 * ## The clock is the server's
 *
 * `timeRemaining` comes from `InterviewStateResponse.time_remaining_seconds`,
 * computed from `Interview.started_at` and `time_limit_seconds`. The client
 * ticks it down between server updates purely so it does not visibly freeze —
 * every state frame overwrites it. There is no second clock here, and nothing
 * in this component can extend an interview: a paused tab or a fiddled system
 * clock changes the display for a second and is corrected on the next turn.
 *
 * ## The last two minutes are marked, not alarmed
 *
 * Under two minutes the clock brightens and gains a label. It does not turn
 * red, and that rule is carried over from the typed interview it replaces: this
 * is a conversation with a person, and a red countdown makes the closing minutes of
 * a professional interview feel like an exam being failed. The graph is heading
 * for a graceful wrap-up at this point anyway — the candidate is not running
 * out of time, the conversation is finishing.
 */

const CLOSING_SECONDS = 120;

function formatClock(seconds: number): string {
  const safe = Math.max(0, seconds);
  const minutes = Math.floor(safe / 60);
  return `${String(minutes).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
}

const CONNECTION_COPY: Record<ConnectionState, { label: string; tone: string } | null> = {
  connecting: { label: "Connecting", tone: "text-[var(--room-slate)]" },
  live: null,
  reconnecting: { label: "Reconnecting", tone: "text-[var(--room-caution)]" },
  unavailable: { label: "Limited connection", tone: "text-[var(--room-caution)]" },
};

export interface RoomTopBarProps {
  title: string;
  timeRemaining: number;
  connection: ConnectionState;
  /** Number of integrity signals recorded so far. Shown to the candidate, not
   * hidden from them: a record kept about somebody that they cannot see is a
   * different and worse thing than one they can. */
  integrityCount: number;
  onOpenIntegrity: () => void;
}

export function RoomTopBar({
  title,
  timeRemaining,
  connection,
  integrityCount,
  onOpenIntegrity,
}: RoomTopBarProps) {
  const closing = timeRemaining > 0 && timeRemaining <= CLOSING_SECONDS;
  const connectionNote = CONNECTION_COPY[connection];

  return (
    <header className="flex items-center justify-between gap-3 border-b border-[var(--room-rule)] bg-[var(--room-panel)] px-4 py-2.5 sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--r-sm)] bg-[var(--room-accent-dim)] font-display text-sm font-bold text-[var(--room-accent)]">
          G
        </span>
        <span className="hidden font-display text-sm font-semibold tracking-tight text-[var(--room-ink)] sm:inline">
          GroundTruth
        </span>
        <span aria-hidden="true" className="hidden h-4 w-px bg-[var(--room-rule-strong)] sm:block" />
        <span className="truncate text-sm text-[var(--room-slate)]">{title}</span>
        {connection === "live" ? (
          <span className="hidden shrink-0 items-center gap-1.5 rounded-full border border-[var(--room-rule-strong)] bg-[var(--room-panel)] px-2.5 py-1 text-[11px] font-medium text-[var(--room-slate)] sm:flex">
            <span aria-hidden="true" className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--room-accent)] opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[var(--room-accent)]" />
            </span>
            Live
          </span>
        ) : null}
      </div>

      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        {connectionNote ? (
          <span className={["flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium", connectionNote.tone].join(" ")}>
            {connection === "reconnecting" || connection === "unavailable" ? (
              <WifiOff size={13} aria-hidden="true" />
            ) : (
              <Wifi size={13} aria-hidden="true" />
            )}
            {connectionNote.label}
          </span>
        ) : null}

        {integrityCount > 0 ? (
          <button
            type="button"
            onClick={onOpenIntegrity}
            className="flex items-center gap-1.5 rounded-full bg-[var(--room-caution-dim)] px-2.5 py-1 text-xs font-medium text-[var(--room-caution)] transition-opacity hover:opacity-80"
          >
            <ShieldCheck size={12} aria-hidden="true" />
            {integrityCount} {integrityCount === 1 ? "event" : "events"}
          </button>
        ) : null}

        <div
          className={[
            "flex items-baseline gap-2 rounded-full px-3 py-1.5",
            closing
              ? "border border-[var(--room-rule-strong)] bg-[var(--room-raised)]"
              : "border border-transparent",
          ].join(" ")}
        >
          <span
            className={[
              "machine tabular text-base font-medium",
              closing ? "text-[var(--room-ink)]" : "text-[var(--room-slate)]",
            ].join(" ")}
            aria-label={`${Math.floor(Math.max(0, timeRemaining) / 60)} minutes remaining`}
          >
            {formatClock(timeRemaining)}
          </span>
          <span className="hidden text-xs text-[var(--room-muted)] sm:inline">
            {closing ? "left — wrapping up" : "remaining"}
          </span>
        </div>
      </div>
    </header>
  );
}
