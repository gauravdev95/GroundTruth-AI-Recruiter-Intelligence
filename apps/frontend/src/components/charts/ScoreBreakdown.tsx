export interface ScoreDimension {
  /** Human label, already de-snake-cased by the caller. */
  label: string;
  /** Points earned on this dimension. */
  earned: number;
  /** Points available — the rubric weight, scaled. */
  possible: number;
}

/**
 * The interview rubric breakdown, as horizontal bars.
 *
 * Plain divs rather than Recharts: this is four to five rows of
 * `earned/possible` where every row is directly labelled with both numbers.
 * A chart library here would add a runtime and an SVG viewport to draw
 * rectangles that CSS already draws, and would make the labels harder to keep
 * aligned with the text around them, not easier. The rule is that the form
 * follows the data's job — and this data's job is "read four exact values",
 * which is a table with a magnitude cue, not a plot.
 *
 * ## The dimensions are whatever the interview was scored on
 *
 * Nothing here hardcodes a rubric. `interview/models.py` versions its weights
 * and an evidence report is written once and never re-judged, so a report
 * from rubric v1 has four dimensions and one from v2 has five. The caller
 * passes what the stored report actually contains; inventing a fixed axis
 * list would silently drop a dimension or invent an empty one.
 */
export function ScoreBreakdown({ dimensions }: { dimensions: ScoreDimension[] }) {
  if (dimensions.length === 0) return null;

  return (
    <ul className="space-y-2.5">
      {dimensions.map((dimension) => {
        const ratio = dimension.possible > 0 ? dimension.earned / dimension.possible : 0;
        const percent = Math.max(0, Math.min(100, ratio * 100));

        return (
          <li key={dimension.label} className="space-y-1">
            <div className="flex items-baseline justify-between gap-3">
              <span className="truncate text-[13px] text-ink">{dimension.label}</span>
              <span className="tabular shrink-0 text-xs text-slate-500">
                {Math.round(dimension.earned)}/{Math.round(dimension.possible)}
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-slate-100">
              {/* `gt-electric`, not `verified`. An interview score is a
                  measurement of performance, not a verification outcome —
                  green here would claim the dimension had been proven by an
                  artefact, which is what green means everywhere else in this
                  product. */}
              <div
                className="h-1.5 rounded-full bg-gt-electric"
                style={{ width: `${percent}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
