import { BarChart3, Clock } from "lucide-react";

import { EmptyState, ErrorState, Skeleton } from "@/components";
import { DeadLetterBanner } from "@/features/jobs";

import { useRecruiterFunnel } from "../hooks/useRecruiterAnalytics";

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

function FunnelBar({ label, count, max }: { label: string; count: number; max: number }) {
  const width = max > 0 ? Math.max((count / max) * 100, count > 0 ? 4 : 0) : 0;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-medium text-slate-700">{label}</span>
        <span className="tabular-nums text-slate-500">{count}</span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-ink transition-[width] duration-500" style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

/** Funnel counts, per-stage conversion, and time-to-first-response — all
 * read straight from `GET /recruiter/analytics/funnel`
 * (`pipeline/analytics.py::recruiter_funnel`), nothing recomputed here. */
export function AnalyticsPage() {
  const funnel = useRecruiterFunnel();

  if (funnel.isPending) {
    return <Skeleton className="h-96 w-full" />;
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

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold text-ink">Analytics</h1>
        <p className="mt-1 text-sm text-slate-500">Across every job posting you've published.</p>
      </header>

      <DeadLetterBanner />

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-rule bg-white p-5">
          <h2 className="mb-4 font-display text-lg font-semibold text-ink">Funnel</h2>
          <div className="space-y-3">
            {stageOrder.map((stage) => (
              <FunnelBar key={stage} label={STAGE_LABELS[stage]} count={stage_counts[stage] ?? 0} max={maxCount} />
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-rule bg-white p-5">
            <h2 className="mb-3 font-display text-lg font-semibold text-ink">Conversion</h2>
            <dl className="space-y-2">
              {Object.entries(CONVERSION_LABELS).map(([key, label]) => {
                const value = conversion[key];
                return (
                  <div key={key} className="flex items-center justify-between text-sm">
                    <dt className="text-slate-600">{label}</dt>
                    <dd className="font-semibold tabular-nums text-ink">
                      {value === null || value === undefined ? "—" : `${Math.round(value * 100)}%`}
                    </dd>
                  </div>
                );
              })}
            </dl>
          </div>

          <div className="flex items-center gap-3 rounded-2xl border border-rule bg-white p-5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink/5 text-ink">
              <Clock size={16} aria-hidden="true" />
            </div>
            <div>
              <p className="text-lg font-semibold tabular-nums text-ink">
                {avg_time_to_first_response_hours === null ? "—" : `${avg_time_to_first_response_hours}h`}
              </p>
              <p className="text-xs text-slate-500">Avg. time to first response</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
