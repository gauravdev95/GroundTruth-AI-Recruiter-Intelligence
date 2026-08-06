import { describe, expect, it } from "vitest";

import type { JobDetail } from "../api/jobsApi";
import { buildExtractionDraft, toSkillPayloads } from "./extractionDraft";

function detail(overrides: Partial<JobDetail> = {}): JobDetail {
  return {
    job: {
      id: "job-1",
      company_id: "company-1",
      title: "Backend Engineer",
      description: "…",
      job_type: "full_time",
      experience_level: "mid",
      location: "Bangalore, India",
      is_remote: false,
      deadline: null,
      status: "awaiting_confirmation",
      extraction_error: null,
      needs_reembedding: false,
      published_at: null,
      closed_at: null,
      created_at: "2026-08-05T00:00:00Z",
      updated_at: "2026-08-05T00:00:00Z",
    },
    extracted_requirements: {
      must_have_skills: [{ name: "Rust", min_proficiency: "advanced" }],
      desirable_skills: [{ name: "Docker", min_proficiency: "intermediate" }],
      seniority: "mid",
      role_type: "backend",
      is_remote: false,
      location_constraints: "Bangalore",
    },
    requirements: [],
    ...overrides,
  };
}

describe("buildExtractionDraft", () => {
  it("seeds from the LLM extraction on a first confirmation", () => {
    const draft = buildExtractionDraft(detail(), []);
    expect(draft.mustHave).toEqual(["Rust"]);
    expect(draft.niceToHave).toEqual(["Docker"]);
    expect(draft.seniority).toBe("mid");
    expect(draft.roleType).toBe("backend");
  });

  it("prefers confirmed requirements over the original draft on a re-edit", () => {
    // The failure this guards: a recruiter reopens a published job, and the
    // screen silently reverts to what the model first guessed rather than
    // what they approved.
    const draft = buildExtractionDraft(
      detail({
        requirements: [
          { id: "r1", skill_id: "s1", skill_name: "Go", min_proficiency: "advanced", is_required: true, weight: 1 },
          { id: "r2", skill_id: "s2", skill_name: "Redis", min_proficiency: "novice", is_required: false, weight: 0.5 },
        ],
      }),
      [],
    );
    expect(draft.mustHave).toEqual(["Go"]);
    expect(draft.niceToHave).toEqual(["Redis"]);
  });

  it("merges the creation screen's tags into must-haves", () => {
    const draft = buildExtractionDraft(detail(), ["Kafka"]);
    expect(draft.mustHave).toEqual(["Rust", "Kafka"]);
  });

  it("de-duplicates a seed tag the model also found, case-insensitively", () => {
    // The matching engine casefolds every skill comparison, so two chips
    // differing only in case would produce one requirement — showing both
    // would misrepresent what is about to be saved.
    const draft = buildExtractionDraft(detail(), ["rust", "RUST"]);
    expect(draft.mustHave).toEqual(["Rust"]);
  });

  it("does not promote a seed tag the model classified as nice-to-have", () => {
    const draft = buildExtractionDraft(detail(), ["docker"]);
    expect(draft.mustHave).toEqual(["Rust"]);
    expect(draft.niceToHave).toEqual(["Docker"]);
  });

  it("takes the location constraint from the job, not from the extraction", () => {
    // The recruiter already answered this on screen 1; the model's reading of
    // the prose does not override it.
    expect(buildExtractionDraft(detail(), []).locationConstraint).toBe("Bangalore, India");
  });

  it("falls back to 'Remote' when a remote job has no location", () => {
    const remote = detail();
    remote.job.location = null;
    remote.job.is_remote = true;
    remote.extracted_requirements = null;
    expect(buildExtractionDraft(remote, []).locationConstraint).toBe("Remote");
  });

  it("survives an extraction that produced nothing", () => {
    const draft = buildExtractionDraft(detail({ extracted_requirements: null }), ["Rust"]);
    expect(draft.mustHave).toEqual(["Rust"]);
    expect(draft.niceToHave).toEqual([]);
    expect(draft.seniority).toBe("mid");
  });
});

describe("toSkillPayloads", () => {
  it("weights must-haves at 1.0 and nice-to-haves at 0.5", () => {
    const payloads = toSkillPayloads({
      mustHave: ["Rust"],
      niceToHave: ["Docker"],
      seniority: "mid",
      roleType: "backend",
      locationConstraint: "Bangalore",
    });
    expect(payloads).toEqual([
      { skill_name: "Rust", min_proficiency: "intermediate", is_required: true, weight: 1.0 },
      { skill_name: "Docker", min_proficiency: "intermediate", is_required: false, weight: 0.5 },
    ]);
  });
});
