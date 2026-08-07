import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

import type { DriftDirection } from "../api/pipelineApi";

/**
 * The two scores an application carries, side by side, plus the drift
 * between them.
 *
 * `score_at_apply` is the number the recruiter's shortlisting decision was
 * actually made against and never moves; the live `match_score` keeps
 * changing as either side is re-embedded. Showing only one of them would
 * either hide that a candidate has since got stronger, or quietly rewrite
 * the basis of a decision that has already been made — so both are shown,
 * with the at-apply number given the primary weight because that is the one
 * every other card in the column is ranked on.
 *
 * Emphasis is driven by the server's `is_meaningful` (`abs(points) >= 5.0`,
 * `MEANINGFUL_DRIFT_POINTS`), never re-derived here: one threshold, defined
 * once, in the same place as the score formula it is measured against.
 */

const DIRECTION_ICON: Record<Exclude<DriftDirection, "unknown">, typeof ArrowUpRight> = {
  up: ArrowUpRight,
  down: ArrowDownRight,
  flat: Minus,
};

export function ScoreWithDrift({
  scoreAtApply,
  liveScore,
  driftPoints,
  direction,
  isMeaningful,
  size = "sm",
}: {
  scoreAtApply: number | null;
  liveScore: number | null;
  driftPoints: number | null;
  direction: DriftDirection;
  isMeaningful: boolean;
  size?: "sm" | "lg";
}) {
  // Pre-backfill applications carry no frozen score at all. Rendering a dash
  // is honest; rendering the live score in its place would be a lie about
  // what the recruiter saw when they decided.
  if (scoreAtApply === null) {
    return (
      <span className="text-xs text-[var(--muted)]">
        {liveScore === null ? "No score" : `Live ${liveScore.toFixed(0)} · none at apply`}
      </span>
    );
  }

  const Icon = direction === "unknown" ? null : DIRECTION_ICON[direction];
  const driftTone = !isMeaningful
    ? "text-[var(--muted)]"
    : direction === "up"
      ? "text-[var(--verified)]"
      : "text-[var(--flagged)]";

  return (
    <span className="flex items-baseline gap-2">
      <span
        className={`font-semibold tabular-nums text-[var(--ink)] ${size === "lg" ? "text-2xl" : "text-sm"}`}
        title="Score when this candidate applied — what the shortlisting decision was made against"
      >
        {scoreAtApply.toFixed(0)}
      </span>

      {direction === "unknown" ? (
        // No live row: the pair no longer scores. Deliberately not rendered
        // as "0 change" — that would claim the candidate is unchanged.
        <span className="text-[11px] text-[var(--muted)]" title="This pair no longer has a live match">
          no live match
        </span>
      ) : (
        <span
          className={`inline-flex items-center gap-0.5 text-[11px] tabular-nums ${driftTone}`}
          title={`Live score ${liveScore?.toFixed(0)} — ${
            isMeaningful ? "meaningful drift" : "within the 5-point noise floor"
          }`}
        >
          {Icon ? <Icon size={11} aria-hidden="true" /> : null}
          {driftPoints === 0 ? "no change" : `${driftPoints! > 0 ? "+" : ""}${driftPoints!.toFixed(1)}`}
        </span>
      )}
    </span>
  );
}
