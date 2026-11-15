import { BarChart3, Clock, Filter, TrendingUp } from "lucide-react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, EmptyState, ErrorState, Skeleton } from "@/components";
import { CHART, CHART_TOOLTIP } from "@/components/charts/chartTheme";
import { useCountUp } from "@/design/motion";
import { Surface } from "@/design/Surface";
import { DeadLetterBanner } from "@/features/jobs";

import { useRecruiterActivity, useRecruiterFunnel } from "../hooks/useRecruiterAnalytics";

const STAGE_LABELS: Record<string, string> = {
  applied: "Applied",
  shortlisted: "Shortlisted",
  interview_scheduled: "Interview scheduled",
  hired: "Hired",
  rejected: "Rejected",
};

const CONVERSION_LABELS: Record<string, string> = {
  applied_to_shortlisted: "Applied → Shortlisted",
  shortlisted_to_interview_scheduled: "Shortlisted → Interview",
  interview_scheduled_to_hired: "Interview → Hired",
};

function FunnelBar({ label, count, max, total }: { label: string; count: number; max: number; total: number }) {
  const width = max > 0 ? Math.max((count / max) * 100, count > 0 ? 4 : 0) : 0;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-medium text-[var(--slate)]">{label}</span>
        <span className="tabular-nums text-[var(--slate)]">
          {count}
          {total > 0 ? <span className="text-[var(--muted)]"> · {Math.round((count / total) * 100)}%</span> : null}
        </span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-[var(--panel-raised)]">
        <div className="h-full rounded-full bg-[var(--violet)] transition-[width] duration-500" style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function StatTile({
  icon: Icon,
  label,
  value,
  suffix,
  caption,
}: {
  icon: typeof Clock;
  label: string;
  value: number | null;
  suffix?: string;
  caption: string;
}) {
  const display = Math.round(useCountUp(value ?? 0));
  return (
    <Surface className="p-4">
      <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-[var(--muted)]">
        <Icon size={12} aria-hidden="true" />
        {label}
      </p>
      <p className="tabular mt-1.5 font-display text-2xl font-semibold text-[var(--ink)]">
        {value === null ? (
          "—"
        ) : (
          <>
            {display}
            {suffix ? <span className="ml-0.5 text-base text-[var(--muted)]">{suffix}</span> : null}
          </>
        )}
      </p>
      <p className="mt-2 text-[11px] leading-snug text-[var(--muted)]">{caption}</p>
    </Surface>
  );
}

function formatDay(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** Funnel counts, per-stage conversion, and time-to-first-response — all
 * read straight from `GET /recruiter/analytics/funnel`
 * (`pipeline/analytics.py::recruiter_funnel`), nothing recomputed here —
 * plus the daily matches/applications trend from `GET
 * /recruiter/analytics/activity`. Two things the brief asked for are
 * deliberately absent: interview analytics and candidate verification
 * statistics have no recruiter endpoint, so they are not shown rather than
 * estimated. */
export function AnalyticsPage() {
  const funnel = useRecruiterFunnel();
  const activity = useRecruiterActivity();

  if (funnel.isPending) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (funnel.isError || !funnel.data) {
    return <ErrorState title="Could not load analytics" description="Something went wrong." />;
  }

  const { stage_counts, total_applications, conversion, avg_time_to_first_response_hours } = funnel.data;

  if (total_applications === 0) {
    return (
      <div className="space-y-6">
        <DeadLetterBanner />
        <EmptyState
          icon={BarChart3}
          title="No applications yet"
          description="Analytics appear once candidates start applying to your published jobs."
        />
      </div>
    );
  }

  const stageOrder = ["applied", "shortlisted", "interview_scheduled", "hired", "rejected"];
  const maxCount = Math.max(...stageOrder.map((s) => stage_counts[s] ?? 0), 1);
  const series = activity.data?.series ?? [];
  const appliedToShortlisted = conversion.applied_to_shortlisted ?? null;
  const interviewToHired = conversion.interview_scheduled_to_hired ?? null;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight text-[var(--ink)]">Analytics</h1>
        <p className="mt-1 text-sm text-[var(--slate)]">Across every job posting you've published.</p>
      </header>

      <DeadLetterBanner />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          icon={Filter}
          label="Total applications"
          value={total_applications}
          caption="Every application across your published roles."
        />
        <StatTile
          icon={Clock}
          label="Avg. time to first response"
          value={avg_time_to_first_response_hours}
          suffix={avg_time_to_first_response_hours === null ? "" : "h"}
          caption={
            avg_time_to_first_response_hours === null
              ? "No application has been moved yet, so there is nothing to average."
              : "From applied to your first pipeline action, via the audit log."
          }
        />
        <StatTile
          icon={TrendingUp}
          label="Applied → Shortlisted"
          value={appliedToShortlisted === null ? null : Math.round(appliedToShortlisted * 100)}
          suffix={appliedToShortlisted === null ? "" : "%"}
          caption={
            appliedToShortlisted === null
              ? "No shortlist move has been recorded yet."
              : "Share of applications you shortlisted."
          }
        />
        <StatTile
          icon={TrendingUp}
          label="Interview → Hired"
          value={interviewToHired === null ? null : Math.round(interviewToHired * 100)}
          suffix={interviewToHired === null ? "" : "%"}
          caption={
            interviewToHired === null
              ? "No hire has been recorded yet."
              : "Share of interviewed candidates you hired."
          }
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Hiring funnel" subtitle="Stage counts across all your published roles.">
          <div className="space-y-3">
            {stageOrder.map((stage) => (
              <FunnelBar
                key={stage}
                label={STAGE_LABELS[stage]}
                count={stage_counts[stage] ?? 0}
                max={maxCount}
                total={total_applications}
              />
            ))}
          </div>
        </Card>

        <Card title="Conversion" subtitle="How candidates move between stages.">
          <dl className="space-y-3">
            {Object.entries(CONVERSION_LABELS).map(([key, label]) => {
              const value = conversion[key];
              return (
                <div key={key} className="flex items-center justify-between gap-3 border-b border-[var(--rule-soft)] pb-3 text-sm last:border-0 last:pb-0">
                  <dt className="text-[var(--slate)]">{label}</dt>
                  <dd className="tabular font-semibold text-[var(--ink)]">
                    {value === null || value === undefined ? "—" : `${Math.round(value * 100)}%`}
                  </dd>
                </div>
              );
            })}
          </dl>
          <p className="mt-4 text-xs leading-relaxed text-[var(--muted)]">
            Conversion is measured on the applications that reached each stage — a dash means no
            candidate has reached that step yet, not 0%.
          </p>
        </Card>
      </div>

      <Card
        title="Application trends"
        subtitle={
          activity.data
            ? `Matches and applications per day, last ${activity.data.window_days} days.`
            : "Matches and applications per day."
        }
      >
        {activity.isPending ? (
          <Skeleton className="h-56 w-full" />
        ) : activity.isError || series.length === 0 ? (
          <p className="rounded-[var(--r-lg)] border border-dashed border-[var(--rule)] p-8 text-center text-sm text-[var(--slate)]">
            {activity.isError
              ? "The activity trend could not be loaded — the funnel above is unaffected."
              : "No activity in the window yet."}
          </p>
        ) : (
          <>
            <div className="h-56 w-full" role="img" aria-label="Daily matches and applications">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={series} margin={{ top: 4, right: 8, bottom: 0, left: -8 }}>
                  <CartesianGrid stroke={CHART.grid} strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={formatDay}
                    tick={{ fontSize: 10, fill: CHART.tick }}
                    tickLine={false}
                    axisLine={{ stroke: CHART.grid }}
                    minTickGap={24}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fontSize: 10, fill: CHART.tick }}
                    tickLine={false}
                    axisLine={false}
                    width={32}
                  />
                  <Tooltip
                    {...CHART_TOOLTIP}
                    labelFormatter={(label) =>
                      typeof label === "string"
                        ? new Date(label).toLocaleDateString(undefined, {
                            weekday: "short",
                            day: "numeric",
                            month: "short",
                          })
                        : ""
                    }
                    formatter={(value, name) => [Number(value ?? 0), name === "applications" ? "Applications" : "Matches"]}
                  />
                  <Bar dataKey="applications" fill={CHART.series} radius={[4, 4, 0, 0]} maxBarSize={18} />
                  <Line
                    type="monotone"
                    dataKey="matches"
                    stroke="var(--teal)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, strokeWidth: 2, stroke: CHART.markRing }}
                    isAnimationActive={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <ul className="mt-2 flex items-center justify-center gap-4 text-[11px] text-[var(--muted)]">
              <li className="flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: CHART.series }} />
                Applications (bars)
              </li>
              <li className="flex items-center gap-1.5">
                <span className="inline-block h-0 w-4 border-t-2" style={{ borderColor: "var(--teal)" }} />
                Matches (line)
              </li>
            </ul>
          </>
        )}
      </Card>

      <p className="text-xs leading-relaxed text-[var(--muted)]">
        Interview analytics and candidate verification statistics are not shown: no recruiter
        endpoint returns them, and estimating them from the funnel would misstate what was
        measured.
      </p>
    </div>
  );
}
