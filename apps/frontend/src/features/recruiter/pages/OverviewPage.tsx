import { ArrowRight, Briefcase, Clock, Plus, Users } from "lucide-react";
import { Link } from "react-router-dom";

import { ErrorState, Skeleton } from "@/components";
import { Sparkline, type SparkPoint } from "@/components/charts/Sparkline";
import { useCountUp } from "@/design/motion";

import { useRecruiterActivity, useRecruiterFunnel } from "../analytics/hooks/useRecruiterAnalytics";
import { JobStatusBadge } from "../components/JobStatusBadge";
import { useJobs } from "../hooks/useJobs";

/**
 * A stat tile: one number, its label, and the 14-day series behind it.
 *
 * The number counts up on mount (`useCountUp` — the app's shared rAF loop,
 * not a second one) and the sparkline does not animate. That is deliberate:
 * two animations racing on one tile read as a loading glitch, and the number
 * is the thing being reported.
 */
function StatTile({
  icon: Icon,
  label,
  value,
  suffix,
  points,
  caption,
}: {
  icon: typeof Users;
  label: string;
  value: number;
  suffix?: string;
  points?: SparkPoint[];
  caption: string;
}) {
  const display = Math.round(useCountUp(value));

  return (
    <div className="rounded-xl border border-rule bg-white p-4 shadow-[0_1px_3px_rgba(0,0,0,0.08)] transition hover:-translate-y-px hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-slate-400">
            <Icon size={12} aria-hidden="true" />
            {label}
          </p>
          <p className="tabular mt-1.5 font-display text-2xl font-semibold text-ink">
            {display}
            {suffix ? <span className="ml-0.5 text-base text-slate-400">{suffix}</span> : null}
          </p>
        </div>
        {points && points.length > 0 ? (
          <Sparkline
            points={points}
            ariaLabel={`${label} over the last ${points.length} days`}
            className="h-9 w-24 shrink-0"
          />
        ) : null}
      </div>
      {/* Every tile says where its number came from. The product rule is that
          a number a recruiter cannot trace is a number they cannot act on. */}
      <p className="mt-2 text-[11px] leading-snug text-slate-400">{caption}</p>
    </div>
  );
}

function daysRemaining(deadline: string | null): string | null {
  if (!deadline) return null;
  const days = Math.ceil((new Date(deadline).getTime() - Date.now()) / 86_400_000);
  if (days < 0) return "Deadline passed";
  if (days === 0) return "Closes today";
  return `${days} day${days === 1 ? "" : "s"} left`;
}

/**
 * `/recruiter/dashboard` — the overview.
 *
 * This URL used to render `JobsListPage`, which meant a recruiter's landing
 * screen was a list with no summary and the dashboard and the jobs index were
 * literally the same page at two addresses. They answer different questions:
 * this one is "what is happening", `/recruiter/jobs` is "show me all of
 * them".
 *
 * ## Where each number comes from
 *
 * * *Candidates matched* — `match_results` rows across this recruiter's jobs,
 *   summed from the activity series.
 * * *Applications this week* — the last 7 points of the same series.
 * * *Avg. time to first response* — `analytics.py::recruiter_funnel`, derived
 *   from `audit_log`: the first status change on an application minus its
 *   `applied_at`.
 *
 * The brief asked for "Avg. time to shortlist" specifically. That is not what
 * the system measures — the funnel records the first *response* of any kind,
 * which includes a rejection, and re-labelling it "to shortlist" would name a
 * metric this product does not compute. The tile says what the number is.
 */
export function OverviewPage() {
  const jobs = useJobs();
  const funnel = useRecruiterFunnel();
  const activity = useRecruiterActivity();

  if (jobs.isPending || activity.isPending) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (jobs.isError) {
    return <ErrorState title="Could not load your dashboard" description="Something went wrong." />;
  }

  const series = activity.data?.series ?? [];
  const matchPoints: SparkPoint[] = series.map((point) => ({ date: point.date, value: point.matches }));
  const applicationPoints: SparkPoint[] = series.map((point) => ({
    date: point.date,
    value: point.applications,
  }));

  const totalMatched = series.reduce((sum, point) => sum + point.matches, 0);
  const applicationsThisWeek = series.slice(-7).reduce((sum, point) => sum + point.applications, 0);
  const avgResponseHours = funnel.data?.avg_time_to_first_response_hours ?? null;

  const publishedJobs = jobs.data.filter((job) => job.status === "published");

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-ink">Dashboard</h1>
          <p className="mt-1 text-sm text-slate-500">
            {publishedJobs.length === 0
              ? "No published roles yet — post one to start matching."
              : `${publishedJobs.length} active role${publishedJobs.length === 1 ? "" : "s"}, matching against every verified candidate.`}
          </p>
        </div>
        <Link
          to="/recruiter/jobs/new"
          className="inline-flex items-center gap-2 rounded-xl bg-gt-electric px-4 py-2.5 text-sm font-bold text-white transition hover:bg-gt-electric/90"
        >
          <Plus size={15} aria-hidden="true" />
          Post new job
        </Link>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        <StatTile
          icon={Users}
          label="Candidates matched"
          value={totalMatched}
          points={matchPoints}
          caption={`Matches computed across your roles in the last ${series.length} days.`}
        />
        <StatTile
          icon={Briefcase}
          label="Applications this week"
          value={applicationsThisWeek}
          points={applicationPoints}
          caption="Smart Apply submissions in the last 7 days."
        />
        <StatTile
          icon={Clock}
          label="Avg. time to first response"
          value={avgResponseHours ?? 0}
          suffix={avgResponseHours === null ? "" : "h"}
          caption={
            avgResponseHours === null
              ? "No application has been moved yet, so there is nothing to average."
              : "From applied to your first pipeline action, via the audit log."
          }
        />
      </div>

      <section>
        <div className="mb-3 flex items-center justify-between gap-4">
          <h2 className="font-display text-lg font-semibold text-ink">Active roles</h2>
          <Link
            to="/recruiter/jobs"
            className="inline-flex items-center gap-1 text-xs font-medium text-gt-electric hover:underline"
          >
            All job postings
            <ArrowRight size={12} aria-hidden="true" />
          </Link>
        </div>

        {jobs.data.length === 0 ? (
          <p className="rounded-xl border border-dashed border-rule p-8 text-center text-sm text-slate-500">
            No roles yet.{" "}
            <Link to="/recruiter/jobs/new" className="font-medium text-ink hover:underline">
              Post your first job
            </Link>{" "}
            — matching runs automatically once you confirm the requirements.
          </p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {jobs.data.slice(0, 6).map((job) => {
              const remaining = daysRemaining(job.deadline);
              return (
                <li key={job.id}>
                  <Link
                    to={job.status === "published" ? `/recruiter/jobs/${job.id}/pipeline` : `/recruiter/jobs/${job.id}`}
                    className="block h-full rounded-xl border border-rule bg-white p-4 shadow-[0_1px_3px_rgba(0,0,0,0.08)] transition hover:-translate-y-px hover:border-gt-electric/30 hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)]"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="min-w-0 truncate font-medium text-ink">{job.title}</p>
                      <JobStatusBadge status={job.status} />
                    </div>
                    <p className="mt-1 truncate text-xs text-slate-500">
                      {job.is_remote ? "Remote" : (job.location ?? "Location not specified")} ·{" "}
                      {job.job_type.replace(/_/g, " ")}
                    </p>
                    {remaining ? (
                      <p className="mt-2 text-[11px] text-slate-400">{remaining}</p>
                    ) : (
                      <p className="mt-2 text-[11px] text-slate-400">No deadline set</p>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
