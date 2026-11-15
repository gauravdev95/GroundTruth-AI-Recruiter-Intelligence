import { Briefcase, SearchX } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Button, EmptyState, ErrorState, Pagination, Skeleton } from "@/components";
import { useMyApplications } from "@/features/student/applications/hooks/useApplications";

import { JobCard } from "../components/JobCard";
import { JobFeedFilters } from "../components/JobFeedFilters";
import { useJobFeed } from "../hooks/useJobFeed";
import {
  DEFAULT_FEED_FILTERS,
  feedFilterOptions,
  filterFeedJobs,
  isDefaultFilters,
  sortFeedJobs,
  type FeedFilterState,
} from "../lib/feedFilters";

/** One screen of cards. The feed is uncapped server-side, so a long ranked
 * list paginates client-side rather than growing without end. */
const PAGE_SIZE = 10;

/**
 * The student side of the same computation the recruiter's matched-
 * candidates list reads (`domains/matching/service.py`) — a personalised
 * ranked job feed, `GET /api/v1/student/matches`. Nothing here is computed
 * client-side; every score and reason is read straight off `match_results`.
 *
 * Search and filters run over the returned rows (`matches/lib/feedFilters`)
 * because the endpoint takes no query parameters. The Tier B interrupt
 * stays on the dashboard (`SmartApplyPrompts`): this page is the full
 * ranked list, and a Tier B card duplicated above it would not obey the
 * same filters — so Tier B jobs carry their `High match` chip here instead.
 */
export function JobFeedPage() {
  const feed = useJobFeed();
  const applications = useMyApplications();
  const [filters, setFilters] = useState<FeedFilterState>(DEFAULT_FEED_FILTERS);
  const [page, setPage] = useState(1);

  const appliedJobIds = new Set((applications.data ?? []).map((item) => item.application.job_posting_id));

  const visible = useMemo(() => {
    if (!feed.data) return [];
    return sortFeedJobs(filterFeedJobs(feed.data, filters), filters.sort);
  }, [feed.data, filters]);

  // A filter change can shrink the list below the current page.
  useEffect(() => {
    setPage(1);
  }, [filters]);

  const totalPages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageItems = visible.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  if (feed.isPending) {
    return (
      <div className="space-y-3" aria-label="Loading job matches">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (feed.isError) {
    return (
      <ErrorState
        title="Could not load your job feed"
        description="Something went wrong while fetching your matches."
        action={
          <Button variant="secondary" onClick={() => void feed.refetch()}>
            Try again
          </Button>
        }
      />
    );
  }

  if (feed.data.length === 0) {
    return (
      <div className="space-y-6">
        <header>
          <h1 className="font-display text-2xl font-semibold text-[var(--ink)]">Job matches</h1>
          <p className="mt-1 text-sm text-[var(--slate)]">
            Ranked for you, from the same computation recruiters use to find candidates.
          </p>
        </header>
        <EmptyState
          icon={Briefcase}
          title="No matched jobs yet"
          description="Complete your profile and verify a repository or coding-platform account — matches appear here once your profile clears the match threshold against a published job."
        />
      </div>
    );
  }

  const jobTypeOptions = feedFilterOptions(feed.data, "job_type");
  const experienceOptions = feedFilterOptions(feed.data, "experience_level");
  const highMatchCount = feed.data.filter((match) => match.tier === "smart_apply_recommended").length;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-semibold text-[var(--ink)]">Job matches</h1>
          <p className="mt-1 text-sm text-[var(--slate)]">
            Ranked for you, from the same computation recruiters use to find candidates.
            {highMatchCount > 0
              ? ` ${highMatchCount} ${highMatchCount === 1 ? "is a high match" : "are high matches"} — worth a Smart Apply.`
              : ""}
          </p>
        </div>
        <Link to="/student/applications" className="text-sm font-medium text-[var(--ink)] hover:underline">
          View my applications →
        </Link>
      </header>

      <JobFeedFilters
        filters={filters}
        onChange={setFilters}
        jobTypeOptions={jobTypeOptions}
        experienceOptions={experienceOptions}
      />

      {visible.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title="No matches for these filters"
          description="Try widening the search or clearing a filter — your full ranked feed is still there."
          action={
            <Button
              variant="secondary"
              onClick={() =>
                setFilters({
                  query: "",
                  jobType: "all",
                  experience: "all",
                  remoteOnly: false,
                  highMatchOnly: false,
                  sort: "best",
                })
              }
            >
              Clear filters
            </Button>
          }
        />
      ) : (
        <>
          <p className="text-sm text-[var(--slate)]" aria-live="polite">
            Showing{" "}
            <span className="tabular font-medium text-[var(--ink)]">{pageItems.length}</span> of{" "}
            <span className="tabular font-medium text-[var(--ink)]">{visible.length}</span>{" "}
            {visible.length === 1 ? "match" : "matches"}
            {!isDefaultFilters(filters) ? ` (from ${feed.data.length} total)` : ""}
          </p>

          <ul className="space-y-3">
            {pageItems.map((match) => (
              <li key={match.job.job_id}>
                <JobCard match={match} alreadyApplied={appliedJobIds.has(match.job.job_id)} />
              </li>
            ))}
          </ul>

          <div className="flex justify-center">
            <Pagination page={currentPage} totalPages={totalPages} onChange={setPage} />
          </div>
        </>
      )}
    </div>
  );
}
