import { motion } from "framer-motion";
import { useId } from "react";

import { DURATION, EASE, useCountUp, useReducedMotionSafe } from "@/design/motion";

/**
 * The match score, as a ring.
 *
 * The arc fill *is* the banding: a fuller ring is a stronger match, and the
 * number inside is the score the API returned — nothing is re-bucketed into
 * invented thresholds. The sweep is the same violet→blue gradient as the
 * profile-strength ring (`design/primitives.tsx`): a score is a *measure*,
 * not a verification, so it is never green (tokens.css rule 1) and never
 * `gt-electric` (the student flow's accent is `--blue`, not the recruiter's).
 *
 * The gradient id is per-instance (`useId`) because a feed renders one ring
 * per card — the shared `gt-ring` id in `ProgressRing` is fine for a single
 * dashboard ring, but duplicated ids across a list are not.
 */
export function MatchScoreRing({
  value,
  size = 64,
  strokeWidth = 6,
  label,
}: {
  /** 0-100, straight from `match_score`. */
  value: number;
  size?: number;
  strokeWidth?: number;
  /** Accessible name, e.g. "Match score 82 percent". */
  label?: string;
}) {
  const reduced = useReducedMotionSafe();
  const gradientId = `match-ring-${useId().replace(/:/g, "")}`;
  const displayScore = Math.round(useCountUp(value));

  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, value));
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <div
      className="relative inline-flex shrink-0 items-center justify-center"
      role="img"
      aria-label={label ?? `Match score ${Math.round(clamped)} percent`}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--violet)" />
            <stop offset="100%" stopColor="var(--blue)" />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--rule)"
          strokeWidth={strokeWidth}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={reduced ? false : { strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: reduced ? 0 : DURATION.cinematic, ease: EASE.entrance }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="tabular text-base font-semibold leading-none text-[var(--ink)]">
          {displayScore}
          <span className="text-[11px]">%</span>
        </span>
        <span className="mt-0.5 text-[9px] font-medium uppercase tracking-wide text-[var(--muted)]">
          match
        </span>
      </div>
    </div>
  );
}
