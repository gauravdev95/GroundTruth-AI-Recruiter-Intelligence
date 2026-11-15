/**
 * What the match score is made of — the two components the API returns
 * alongside `match_score` (`matching/schemas.py`): how semantically close
 * the profile is to the posting, and how much of it is backed by verified
 * evidence.
 *
 * Two flat bars, not a chart: the numbers are already percentages, and a
 * bar whose length *is* the number needs no legend. The fill is the same
 * violet→blue gradient as the score ring — a measure, never a status
 * colour (tokens.css rule 1). The percentages are machine-measured, so
 * they are set in mono (the mono rule).
 */
export function MatchScoreBreakdown({
  semanticScore,
  evidenceScore,
}: {
  /** 0-1, from the API. */
  semanticScore: number;
  /** 0-1, from the API. */
  evidenceScore: number;
}) {
  const rows = [
    {
      label: "Semantic fit",
      hint: "How closely your profile reads against this posting",
      value: semanticScore,
    },
    {
      label: "Verified evidence",
      hint: "How much of the fit is backed by verified artefacts",
      value: evidenceScore,
    },
  ];

  return (
    <dl className="space-y-4">
      {rows.map((row) => {
        const percent = Math.round(Math.max(0, Math.min(1, row.value)) * 100);
        return (
          <div key={row.label}>
            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-[13px] font-medium text-[var(--ink)]">
                {row.label}
                <span className="ml-2 text-xs font-normal text-[var(--muted)]">{row.hint}</span>
              </dt>
              <dd className="machine tabular shrink-0 text-[13px] text-[var(--slate)]">
                {percent}%
              </dd>
            </div>
            <div
              className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[var(--rule)]/60"
              role="img"
              aria-label={`${row.label} ${percent} percent`}
            >
              <div
                className="h-full rounded-full transition-[width] duration-500"
                style={{
                  width: `${percent}%`,
                  background: "linear-gradient(90deg, var(--violet), var(--blue))",
                }}
              />
            </div>
          </div>
        );
      })}
    </dl>
  );
}
