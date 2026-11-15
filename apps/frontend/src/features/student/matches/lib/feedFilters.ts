import type { MatchedJob } from "../api/matchesApi";

/**
 * Client-side search, filter and sort for the job feed.
 *
 * The feed endpoint (`GET /api/v1/student/matches`) takes no query
 * parameters — it returns every match row, already ranked by `match_score`
 * desc. So search and filtering happen here, over the returned rows, and
 * every filter dimension is one the payload actually carries: `job_type`,
 * `experience_level`, `is_remote`, `tier`, the job's own text, and the
 * matched skill names. Nothing here invents a dimension the backend does
 * not have, and nothing re-scores anything: the server's order is the
 * default sort, preserved exactly.
 */

export type FeedSort = "best" | "closing" | "newest";

export interface FeedFilterState {
  query: string;
  jobType: string;
  experience: string;
  remoteOnly: boolean;
  highMatchOnly: boolean;
  sort: FeedSort;
}

export const DEFAULT_FEED_FILTERS: FeedFilterState = {
  query: "",
  jobType: "all",
  experience: "all",
  remoteOnly: false,
  highMatchOnly: false,
  sort: "best",
};

/** `"full_time"` → `"Full Time"`, `"entry"` → `"Entry"`. */
export function formatJobLabel(value: string): string {
  const words = value.replace(/_/g, " ").split(" ");
  return words.map((word) => (word ? word[0].toUpperCase() + word.slice(1) : word)).join(" ");
}

export function filterFeedJobs(jobs: MatchedJob[], filters: FeedFilterState): MatchedJob[] {
  const query = filters.query.trim().toLowerCase();
  return jobs.filter((match) => {
    if (filters.jobType !== "all" && match.job.job_type !== filters.jobType) return false;
    if (filters.experience !== "all" && match.job.experience_level !== filters.experience)
      return false;
    if (filters.remoteOnly && !match.job.is_remote) return false;
    if (filters.highMatchOnly && match.tier !== "smart_apply_recommended") return false;
    if (query) {
      const haystack = [
        match.job.title,
        match.job.company_name,
        match.job.location ?? "",
        ...match.matched_required_skills.map((skill) => skill.skill_name),
        ...match.matched_desirable_skills.map((skill) => skill.skill_name),
      ]
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(query)) return false;
    }
    return true;
  });
}

export function sortFeedJobs(jobs: MatchedJob[], sort: FeedSort): MatchedJob[] {
  // "best" is the server's ranking — returned untouched, never re-sorted.
  if (sort === "best") return jobs;
  const copy = [...jobs];
  if (sort === "closing") {
    // No deadline sorts last: a missing deadline is not an imminent one.
    copy.sort((a, b) => {
      const aTime = a.job.deadline ? new Date(a.job.deadline).getTime() : Number.POSITIVE_INFINITY;
      const bTime = b.job.deadline ? new Date(b.job.deadline).getTime() : Number.POSITIVE_INFINITY;
      return aTime - bTime;
    });
  } else {
    copy.sort(
      (a, b) => new Date(b.computed_at).getTime() - new Date(a.computed_at).getTime(),
    );
  }
  return copy;
}

/** Distinct values actually present in this feed, as select options. */
export function feedFilterOptions(
  jobs: MatchedJob[],
  key: "job_type" | "experience_level",
): { value: string; label: string }[] {
  const seen = new Set<string>();
  for (const match of jobs) {
    const value = match.job[key];
    if (value) seen.add(value);
  }
  return [...seen]
    .sort()
    .map((value) => ({ value, label: formatJobLabel(value) }));
}

export function isDefaultFilters(filters: FeedFilterState): boolean {
  return (
    filters.query.trim() === "" &&
    filters.jobType === "all" &&
    filters.experience === "all" &&
    !filters.remoteOnly &&
    !filters.highMatchOnly &&
    filters.sort === "best"
  );
}
