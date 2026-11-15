import { describe, expect, it } from "vitest";

import type { MatchedJob } from "../api/matchesApi";
import {
  DEFAULT_FEED_FILTERS,
  feedFilterOptions,
  filterFeedJobs,
  formatJobLabel,
  isDefaultFilters,
  sortFeedJobs,
} from "./feedFilters";

function makeMatch(overrides: Partial<MatchedJob["job"]> & { score?: number } = {}): MatchedJob {
  const { score = 70, ...job } = overrides;
  return {
    match_score: score,
    semantic_score: 0.7,
    evidence_score: 0.7,
    matched_required_skills: [{ skill_name: "Python", candidate_has_skill: true, candidate_proficiency: null, evidence_weight: 0.8, evidence_sources: [] }],
    matched_desirable_skills: [],
    computed_at: "2026-11-10T10:00:00Z",
    updated_at: "2026-11-10T10:00:00Z",
    tier: null,
    reasoning: "Matches your profile.",
    job: {
      job_id: job.job_id ?? "job-1",
      title: job.title ?? "Backend Engineer",
      company_name: job.company_name ?? "Acme",
      job_type: job.job_type ?? "full_time",
      experience_level: job.experience_level ?? "entry",
      location: job.location ?? "Bengaluru",
      is_remote: job.is_remote ?? false,
      deadline: job.deadline ?? null,
      description: "A role.",
    },
  };
}

describe("formatJobLabel", () => {
  it("title-cases underscore values", () => {
    expect(formatJobLabel("full_time")).toBe("Full Time");
    expect(formatJobLabel("entry")).toBe("Entry");
  });
});

describe("filterFeedJobs", () => {
  const jobs = [
    makeMatch({ job_id: "a", title: "Backend Engineer", job_type: "full_time", experience_level: "entry", is_remote: false }),
    makeMatch({ job_id: "b", title: "Frontend Intern", job_type: "internship", experience_level: "entry", is_remote: true, company_name: "Beta" }),
    makeMatch({ job_id: "c", title: "Data Scientist", job_type: "contract", experience_level: "senior", is_remote: false }),
  ];

  it("returns everything with default filters", () => {
    expect(filterFeedJobs(jobs, DEFAULT_FEED_FILTERS)).toHaveLength(3);
  });

  it("searches title, company and skill names", () => {
    expect(filterFeedJobs(jobs, { ...DEFAULT_FEED_FILTERS, query: "beta" })).toHaveLength(1);
    expect(filterFeedJobs(jobs, { ...DEFAULT_FEED_FILTERS, query: "python" })).toHaveLength(3);
    expect(filterFeedJobs(jobs, { ...DEFAULT_FEED_FILTERS, query: "rust" })).toHaveLength(0);
  });

  it("filters by job type and experience level", () => {
    expect(filterFeedJobs(jobs, { ...DEFAULT_FEED_FILTERS, jobType: "internship" })).toHaveLength(1);
    expect(filterFeedJobs(jobs, { ...DEFAULT_FEED_FILTERS, experience: "senior" })).toHaveLength(1);
  });

  it("filters to remote-only and to high matches", () => {
    const tiered = [
      ...jobs,
      { ...makeMatch({ job_id: "d" }), tier: "smart_apply_recommended" as const },
    ];
    expect(filterFeedJobs(tiered, { ...DEFAULT_FEED_FILTERS, remoteOnly: true })).toHaveLength(1);
    expect(filterFeedJobs(tiered, { ...DEFAULT_FEED_FILTERS, highMatchOnly: true })).toHaveLength(1);
  });
});

describe("sortFeedJobs", () => {
  it("leaves the server order untouched for 'best'", () => {
    const jobs = [makeMatch({ job_id: "a" }), makeMatch({ job_id: "b" })];
    expect(sortFeedJobs(jobs, "best")).toBe(jobs);
  });

  it("sorts by deadline with missing deadlines last", () => {
    const jobs = [
      makeMatch({ job_id: "a", deadline: null }),
      makeMatch({ job_id: "b", deadline: "2026-11-20T00:00:00Z" }),
      makeMatch({ job_id: "c", deadline: "2026-11-16T00:00:00Z" }),
    ];
    expect(sortFeedJobs(jobs, "closing").map((m) => m.job.job_id)).toEqual(["c", "b", "a"]);
  });
});

describe("feedFilterOptions", () => {
  it("returns distinct values present in the feed", () => {
    const jobs = [
      makeMatch({ job_type: "full_time" }),
      makeMatch({ job_type: "internship" }),
      makeMatch({ job_type: "full_time" }),
    ];
    expect(feedFilterOptions(jobs, "job_type")).toEqual([
      { value: "full_time", label: "Full Time" },
      { value: "internship", label: "Internship" },
    ]);
  });
});

describe("isDefaultFilters", () => {
  it("detects a changed filter", () => {
    expect(isDefaultFilters(DEFAULT_FEED_FILTERS)).toBe(true);
    expect(isDefaultFilters({ ...DEFAULT_FEED_FILTERS, query: "x" })).toBe(false);
  });
});
