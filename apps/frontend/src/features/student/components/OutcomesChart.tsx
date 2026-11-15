import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { CHART, CHART_TOOLTIP } from "@/components/charts/chartTheme";
import { Card } from "@/components";

/**
 * Application outcomes, as a bar chart over the counts the analytics
 * endpoint actually returned (`student/analytics/summary`).
 *
 * Nothing here is derived or smoothed: one bar per outcome the server
 * reported, labelled with its exact count. The caller renders this only when
 * at least one outcome is non-zero, so an empty chart can never imply "no
 * applications" — the empty state lives beside it instead.
 */
export function OutcomesChart({ outcomes }: { outcomes: Record<string, number> }) {
  const data = Object.entries(outcomes)
    .filter(([, count]) => count > 0)
    .map(([status, count]) => ({
      status: status.replace(/_/g, " "),
      count,
    }));

  if (data.length === 0) return null;

  return (
    <Card
      title="Application outcomes"
      subtitle="Where your applications stand, from the latest analytics snapshot."
    >
      <div className="h-56 w-full" role="img" aria-label={`Application outcomes: ${data.map((d) => `${d.status} ${d.count}`).join(", ")}`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={CHART.grid} strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: CHART.tick }} />
            <YAxis
              type="category"
              dataKey="status"
              width={110}
              tick={{ fontSize: 11, fill: CHART.tick }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              {...CHART_TOOLTIP}
              formatter={(value) => [value, "Applications"]}
              cursor={{ fill: "var(--rule-soft)" }}
            />
            <Bar dataKey="count" fill={CHART.series} radius={[0, 4, 4, 0]} maxBarSize={24} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-3 flex flex-wrap gap-2">
        {data.map((d) => (
          <li key={d.status} className="text-xs text-[var(--slate)]">
            <span className="capitalize text-[var(--ink)]">{d.status}</span>{" "}
            <span className="font-mono tabular-nums">{d.count}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
