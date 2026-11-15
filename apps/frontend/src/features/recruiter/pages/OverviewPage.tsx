import { ArrowRight, Briefcase, ClipboardList, Clock, Plus, Users } from "lucide-react";
import { Link } from "react-router-dom";

import { Card, EmptyState, ErrorState, Skeleton } from "@/components";
import { Sparkline, type SparkPoint } from "@/components/charts/Sparkline";
import { Surface } from "@/design/Surface";
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
 *
 * `value` is `null` while its source is still loading or failed, and the tile
 * says so with an em dash rather than a zero — a zero would claim "none
 * happened", which a failed request has not established.
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
  value: number | null;
  suffix?: string;
  points?: SparkPoint[];
  caption: string;
}) {
  const display = Math.round(useCountUp(value ?? 0));

  return (
    <Surface className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
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
      <p className="mt-2 text-[11px] leading-snug text-[var(--muted)]">{caption}</p>
    </Surface>
  );
}

function daysRemaining(deadline: string | null): string | null {
  if (!deadline) return null;
  const days = Math.ceil((new Date(deadline).getTime() - Date.now()) / 86_400_000);
  if (days < 0) return "Deadline passed";
  if (days === 0) return "Closes today";
  return `${days} day${days === 1 ? "" : "s"} left`;
}

function formatDay(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

const STAGE_LABELS: Record<string, string> = {
  applied: "Applied",
  shortlisted: "Shortlisted",
  interview_scheduled: "Interview scheduled",
  hired: "Hired",
  rejected: "Rejected",
};

const STAGE_ORDER = ["applied", "shortlisted", "interview_scheduled", "hired", "rejected"];

const CONVERSION_LABELS: Record<string, string> = {
  applied_to_shortlisted: "Applied → Shortlisted",
  shortlisted_to_interview_scheduled: "Shortlisted → Interview",
  interview_scheduled_to_hired: "Interview → Hired",
};

/** One funnel bar. Violet, like the analytics page — the funnel is a reading
 * aid, not a status, so it never spends `--verified`/`--flagged` (rule 1). */
function FunnelBar({ label, count, max }: { label: string; count: number; max: number }) {
  const width = max > 0 ? Math.max((count / max) * 100, count > 0 ? 4 : 0) : 0;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-medium text-[var(--slate)]">{label}</span>
        <span className="tabular-nums text-[var(--slate)]">{count}</span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-[var(--panel-raised)]">
        <div
          className="h-full rounded-full bg-[var(--violet)] transition-[width] duration-500"
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
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
 * * *Active roles* — jobs with `status === "published"`, from `GET
 *   /recruiter/jobs`.
 * * *Candidates matched* — `match_results` rows across this recruiter's jobs,
 *   summed from the activity series.
 * * *Total applications* — `recruiter_funnel.total_applications`, from `GET
 *   /recruiter/analytics/funnel`.
 * * *Avg. time to first response* — `analytics.py::recruiter_funnel`, derived
 *   from `audit_log`: the first status change on an application minus its
 *   `applied_at`.
 * * *Hiring funnel* — the same funnel response: `stage_counts` and
 *   `conversion`. Interview activity is the `interview_scheduled` stage.
 * * *Recent activity* — the dense daily series from `GET
 *   /recruiter/analytics/activity` (matches + applications per day).
 *
 * The brief asked for "Avg. time to shortlist" specifically. That is not what
 * the system measures — the funnel records the first *response* of any kind,
 * which includes a rejection, and re-labelling it "to shortlist" would name a
 * metric this product does not compute. The tile says what the number is.
 *
 * There is no "verified candidates" number: no recruiter endpoint returns a
 * verified-candidate count, and a count derived from match rows would
 * conflate "matched" with "verified". It is not shown rather than invented.
 * Likewise there is no per-application recent list — the activity series is
 * the only recent-applications data the API exposes, so recent activity is
 * shown per day, not per applicant.
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
  const funnelData = funnel.data ?? null;
  const funnelMax = funnelData
    ? Math.max(...STAGE_ORDER.map((s) => funnelData.stage_counts[s] ?? 0), 1)
    : 1;
  const recentDays = [...series].slice(-14).reverse();

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-[var(--ink)]">Dashboard</h1>
          <p className="mt-1 text-sm text-[var(--slate)]">
            {publishedJobs.length === 0
              ? "No published roles yet — post one to start matching."
              : `${publishedJobs.length} active role${publishedJobs.length === 1 ? "" : "s"}, matching against every verified candidate.`}
          </p>
        </div>
        <Link
          to="/recruiter/jobs/new"
          className="inline-flex items-center gap-2 rounded-[var(--r-sm)] bg-gt-electric px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-gt-electric/90"
        >
          <Plus size={15} aria-hidden="true" />
          Post new job
        </Link>
      </header>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatTile
          icon={Briefcase}
          label="Active roles"
          value={publishedJobs.length}
          caption="Published roles currently matching against verified candidates."
        />
        <StatTile
          icon={Users}
          label="Candidates matched"
          value={activity.isError ? null : totalMatched}
          points={matchPoints}
          caption={
            activity.isError
              ? "Activity could not be loaded, so there is no match count to show."
              : `Matches computed across your roles in the last ${series.length} days.`
          }
        />
        <StatTile
          icon={ClipboardList}
          label="Total applications"
          value={funnel.isPending || funnel.isError ? null : funnelData?.total_applications ?? null}
          points={applicationPoints}
          caption={
            funnel.isError
              ? "The hiring funnel could not be loaded."
              : `${applicationsThisWeek} in the last 7 days, across all your published roles.`
          }
        />
        <StatTile
          icon={Clock}
          label="Avg. time to first response"
          value={funnel.isPending || funnel.isError ? null : avgResponseHours}
          suffix={avgResponseHours === null ? "" : "h"}
          caption={
            funnel.isError
              ? "The hiring funnel could not be loaded."
              : avgResponseHours === null
                ? "No application has been moved yet, so there is nothing to average."
                : "From applied to your first pipeline action, via the audit log."
          }
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card
          title="Hiring funnel"
          subtitle="Across every job posting you've published."
          actions={
            <Link
              to="/recruiter/analytics"
              className="inline-flex items-center gap-1 text-xs font-medium text-gt-electric hover:underline"
            >
              Full analytics
              <ArrowRight size={12} aria-hidden="true" />
            </Link>
          }
        >
          {funnel.isPending ? (
            <Skeleton className="h-40 w-full" />
          ) : funnel.isError || !funnelData ? (
            <p className="py-6 text-center text-sm text-[var(--slate)]">
              The hiring funnel could not be loaded.
            </p>
          ) : funnelData.total_applications === 0 ? (
            <EmptyState
              icon={ClipboardList}
              title="No applications yet"
              description="The funnel fills in once candidates start applying to your published jobs."
            />
          ) : (
            <div className="space-y-3">
              {STAGE_ORDER.map((stage) => (
                <FunnelBar
                  key={stage}
                  label={STAGE_LABELS[stage]}
                  count={funnelData.stage_counts[stage] ?? 0}
                  max={funnelMax}
                />
              ))}
              <dl className="space-y-2 border-t border-[var(--rule-soft)] pt-3">
                {Object.entries(CONVERSION_LABELS).map(([key, label]) => {
                  const value = funnelData.conversion[key];
                  return (
                    <div key={key} className="flex items-center justify-between text-sm">
                      <dt className="text-[var(--slate)]">{label}</dt>
                      <dd className="font-semibold tabular-nums text-[var(--ink)]">
                        {value === null || value === undefined ? "—" : `${Math.round(value * 100)}%`}
                      </dd>
                    </div>
                  );
                })}
              </dl>
            </div>
          )}
        </Card>

        <Card
          title="Recent activity"
          subtitle={
            series.length > 0
              ? `Matches and applications per day, last ${Math.min(series.length, 14)} days.`
              : "Matches and applications per day."
          }
        >
          {activity.isError ? (
            <p className="py-6 text-center text-sm text-[var(--slate)]">
              Recent activity could not be loaded.
            </p>
          ) : recentDays.length === 0 ? (
            <p className="rounded-[var(--r-lg)] border border-dashed border-[var(--rule)] p-8 text-center text-sm text-[var(--slate)]">
              No activity in the last {series.length} days.
            </p>
          ) : (
            <ul className="divide-y divide-[var(--rule-soft)]">
              {recentDays.map((point) => (
                <li key={point.date} className="flex items-center justify-between gap-3 py-2 text-sm first:pt-0 last:pb-0">
                  <span className="machine text-[var(--slate)]">{formatDay(point.date)}</span>
                  <span className="flex items-center gap-4 text-[var(--slate)]">
                    <span>
                      <span className="tabular font-medium text-[var(--ink)]">{point.matches}</span>{" "}
                      matched
                    </span>
                    <span>
                      <span className="tabular font-medium text-[var(--ink)]">{point.applications}</span>{" "}
                      applied
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <section>
        <div className="mb-3 flex items-center justify-between gap-4">
          <h2 className="font-display text-lg font-semibold text-[var(--ink)]">Active roles</h2>
          <Link
            to="/recruiter/jobs"
            className="inline-flex items-center gap-1 text-xs font-medium text-gt-electric hover:underline"
          >
            All job postings
            <ArrowRight size={12} aria-hidden="true" />
          </Link>
        </div>

        {jobs.data.length === 0 ? (
          <p className="rounded-[var(--r-lg)] border border-dashed border-[var(--rule)] p-8 text-center text-sm text-[var(--slate)]">
            No roles yet.{" "}
            <Link to="/recruiter/jobs/new" className="font-medium text-[var(--ink)] hover:underline">
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
                    className="block h-full rounded-[var(--r-lg)] border border-[var(--rule)] bg-[var(--panel)] p-4 transition hover:-translate-y-px hover:border-gt-electric/30 hover:shadow-[var(--shadow-panel)]"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="min-w-0 truncate font-medium text-[var(--ink)]">{job.title}</p>
                      <JobStatusBadge status={job.status} />
                    </div>
                    <p className="mt-1 truncate text-xs text-[var(--slate)]">
                      {job.is_remote ? "Remote" : (job.location ?? "Location not specified")} ·{" "}
                      {job.job_type.replace(/_/g, " ")}
                    </p>
                    {remaining ? (
                      <p className="mt-2 text-[11px] text-[var(--muted)]">{remaining}</p>
                    ) : (
                      <p className="mt-2 text-[11px] text-[var(--muted)]">No deadline set</p>
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
