/**
 * The two timestamps a `match_results` row carries, in the words a person
 * reads rather than the words the columns are named.
 *
 * Shared rather than owned by either feature: the student's job feed and the
 * recruiter's matched-candidate list read the *same two columns of the same
 * row*, so the two sides of one match must not be able to describe the same
 * instant differently.
 *
 * * `computed_at` → **"Matched {when}"** — when this pair first matched.
 * * `updated_at` → **"Score updated {when}"** — when the number last moved.
 *
 * "Computed" and "recomputed" are the names of the mechanism; a student
 * being told when they matched should not have to learn our scheduler to
 * read a date.
 *
 * The second line appears only when the two genuinely differ. A pair that
 * has never been rescored carries the same instant in both columns (the
 * backend writes one timestamp for both on insert), so showing it twice
 * under two labels would invent an event that did not happen. The one-minute
 * tolerance below absorbs clock and serialisation noise rather than trusting
 * exact equality across a wire.
 */

const RESCORE_TOLERANCE_MS = 60_000;

const RELATIVE = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 60 * 60 * 1000],
  ["month", 30 * 24 * 60 * 60 * 1000],
  ["day", 24 * 60 * 60 * 1000],
  ["hour", 60 * 60 * 1000],
  ["minute", 60 * 1000],
];

function relativeTime(iso: string): string {
  const elapsed = Date.now() - new Date(iso).getTime();
  for (const [unit, ms] of UNITS) {
    if (elapsed >= ms) return RELATIVE.format(-Math.floor(elapsed / ms), unit);
  }
  return "just now";
}

export function MatchTimestamps({
  computedAt,
  updatedAt,
  className = "",
}: {
  computedAt: string;
  updatedAt: string;
  className?: string;
}) {
  const rescored =
    new Date(updatedAt).getTime() - new Date(computedAt).getTime() > RESCORE_TOLERANCE_MS;

  return (
    <span className={`text-xs text-slate-400 ${className}`}>
      Matched {relativeTime(computedAt)}
      {rescored ? <> · Score updated {relativeTime(updatedAt)}</> : null}
    </span>
  );
}
