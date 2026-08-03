import { Briefcase, MapPin } from "lucide-react";
import { Link } from "react-router-dom";

import { Skeleton } from "@/components";

import { useJobFeed } from "../hooks/useJobFeed";

/** How many of the ranked matches the dashboard shows before deferring to the
 * full feed. Enough to be a real feed rather than a teaser, short enough that
 * it does not push the rest of the dashboard below the fold. */
const PREVIEW_COUNT = 5;

/**
 * The ranked job feed, inline on the student dashboard.
 *
 * Reads the same `match_results` rows as `/student/matches` through the same
 * `useJobFeed` hook and query key — so the two views share one cache entry and
 * cannot disagree, and opening the dashboard costs no extra request once the
 * feed has been fetched. Ordering is the server's; nothing is re-sorted here.
 */
export function JobFeedPreview() {
  const feed = useJobFeed();

  if (feed.isPending) {
    return <Skeleton className="h-40 w-full" />;
  }

  // A failed feed must not take the whole dashboard down with it — the rest of
  // the page is independently useful, so this section just stands down.
  if (feed.isError) {
    return (
      <p className="rounded-2xl border border-dashed border-rule p-6 text-center text-sm text-slate-500">
        Could not load your job matches right now.{" "}
        <Link to="/student/matches" className="font-medium text-ink hover:underline">
          Try the full feed
        </Link>
        .
      </p>
    );
  }

  if (feed.data.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-rule p-6 text-center text-sm text-slate-500">
        No matched jobs yet. Matches appear once your profile is indexed and clears the threshold
        against a published job.
      </p>
    );
  }

  const preview = feed.data.slice(0, PREVIEW_COUNT);

  return (
    <div className="space-y-2">
      <ul className="space-y-2">
        {preview.map((match) => (
          <li key={match.job.job_id}>
            <Link
              to="/student/matches"
              className="flex items-center justify-between gap-4 rounded-2xl border border-rule bg-white p-3.5 transition hover:border-ink"
            >
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-ink">{match.job.title}</span>
                <span className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  {match.job.company_name}
                  <span className="flex items-center gap-1">
                    <MapPin size={11} aria-hidden="true" />
                    {match.job.is_remote ? "Remote" : (match.job.location ?? "Not specified")}
                  </span>
                </span>
              </span>
              <span className="shrink-0 text-right">
                <span className="block text-lg font-semibold tabular-nums text-ink">
                  {match.match_score.toFixed(0)}
                </span>
                <span className="block text-[11px] text-slate-400">match</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>

      {feed.data.length > preview.length ? (
        <Link
          to="/student/matches"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-ink hover:underline"
        >
          <Briefcase size={14} aria-hidden="true" />
          View all {feed.data.length} matches →
        </Link>
      ) : null}
    </div>
  );
}
