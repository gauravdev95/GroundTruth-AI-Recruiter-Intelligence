import { Line, LineChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";

import { CHART, CHART_TOOLTIP } from "./chartTheme";

export interface SparkPoint {
  date: string;
  value: number;
}

/**
 * A 14-day trend line for a stat tile.
 *
 * ## What it is allowed to plot
 *
 * Only a real series. This takes `points` and draws them; it has no default,
 * no smoothing toward a shape, and no behaviour when the series is missing
 * other than rendering nothing. That is the whole reason
 * `pipeline/analytics.py::recruiter_activity` exists — a sparkline is a claim
 * about history, and the funnel endpoint it sits next to only knows current
 * totals.
 *
 * ## Why there is no axis, grid, or legend
 *
 * A sparkline answers "which way, and how steadily" at a glance beside a
 * number that already says "how much". Axes would double its height to add
 * precision nobody reads at 120×32. The tooltip carries the exact value for
 * anyone who wants it, which is the honest trade: recessive by default,
 * precise on demand.
 *
 * A single series needs no legend — the tile's own label names it.
 */
export function Sparkline({
  points,
  ariaLabel,
  className,
}: {
  points: SparkPoint[];
  ariaLabel: string;
  className?: string;
}) {
  if (points.length === 0) return null;

  // An all-zero series is a real answer ("nothing happened for two weeks"),
  // but Recharts would centre a flat line vertically and make it read like a
  // mid-range plateau. Pinning the domain to [0, 1] in that case puts the
  // line on the floor, where a zero belongs.
  const max = Math.max(...points.map((point) => point.value));

  return (
    <div className={className} role="img" aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <YAxis hide domain={[0, max === 0 ? 1 : "dataMax"]} />
          <Tooltip
            cursor={{ stroke: CHART.grid, strokeWidth: 1 }}
            {...CHART_TOOLTIP}
            // Recharts types both callbacks against its own `ValueType` /
            // `ReactNode` unions, which are wider than what this chart can
            // actually receive (a date string and a count). Narrowing at the
            // boundary rather than asserting keeps the runtime honest if that
            // ever stops being true.
            labelFormatter={(label) =>
              typeof label === "string"
                ? new Date(label).toLocaleDateString(undefined, { month: "short", day: "numeric" })
                : ""
            }
            formatter={(value) => [Number(value ?? 0), ""]}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke={CHART.series}
            strokeWidth={2}
            dot={false}
            // 8px hit target, per the interaction spec — bigger than the 2px
            // mark so the tooltip is reachable without pixel-hunting.
            //
            // The ring is the surface colour, not white: its job is to hold a
            // 2px gap between the dot and the line it sits on, and a white pip
            // on a dark panel is a mark in its own right rather than a gap.
            activeDot={{ r: 4, strokeWidth: 2, stroke: CHART.markRing }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
