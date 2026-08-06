import type { JobDetail, Proficiency, RequirementSkillPayload } from "../api/jobsApi";

/**
 * The state behind Screen 2's editable panel, and the rules for seeding it.
 *
 * Lives apart from the component so it can be tested without a DOM, and so
 * the constants below are importable without dragging a React tree along.
 */

/**
 * How long the confirmation screen must be on screen before Publish enables.
 *
 * This is a friction device, and a deliberately small one. The value of the
 * screen is that a human looked at what a language model wrote before it
 * became the thing every future candidate is ranked against; a screen that
 * can be dismissed in the same motion that opened it provides no such
 * assurance. Three seconds is long enough that clicking through is a decision
 * and short enough that a recruiter posting their fifth role this week does
 * not resent it.
 *
 * It is not a security control — nothing stops a client from calling
 * `POST /confirm` directly. It is an interface that declines to help you skip
 * the step it exists for.
 */
export const REVIEW_DWELL_MS = 3_000;

const DEFAULT_PROFICIENCY: Proficiency = "intermediate";

/** Must-haves carry full weight in rank fusion; nice-to-haves carry half —
 * the same split `RequirementsConfirmForm` has always applied, so a job
 * confirmed through either screen produces identical `job_requirements`. */
const REQUIRED_WEIGHT = 1.0;
const DESIRABLE_WEIGHT = 0.5;

export interface ExtractionDraft {
  mustHave: string[];
  niceToHave: string[];
  seniority: string;
  roleType: string;
  locationConstraint: string;
}

/**
 * Seeds the editable fields.
 *
 * Precedence is `job_requirements` (a re-edit of an already-confirmed job)
 * over `extracted_requirements` (the LLM's first draft) — a recruiter
 * reopening a published job must not have their confirmed list silently
 * reverted to what the model originally guessed.
 *
 * `seedSkills` are the tags typed on the creation screen (see
 * `lib/seedSkills.ts` for why they travel client-side). They are merged into
 * must-haves *last* and de-duplicated case-insensitively, so a skill the
 * recruiter named and the model also found appears once — matching the
 * casefolded comparison the matching engine itself uses.
 */
export function buildExtractionDraft(detail: JobDetail, seedSkills: string[]): ExtractionDraft {
  const extracted = detail.extracted_requirements;
  const confirmed = detail.requirements;

  const mustHave =
    confirmed.length > 0
      ? confirmed.filter((r) => r.is_required).map((r) => r.skill_name)
      : (extracted?.must_have_skills ?? []).map((s) => s.name);
  const niceToHave =
    confirmed.length > 0
      ? confirmed.filter((r) => !r.is_required).map((r) => r.skill_name)
      : (extracted?.desirable_skills ?? []).map((s) => s.name);

  const seen = new Set([...mustHave, ...niceToHave].map((s) => s.toLowerCase()));
  const merged = [...mustHave];
  for (const skill of seedSkills) {
    if (!seen.has(skill.toLowerCase())) {
      merged.push(skill);
      seen.add(skill.toLowerCase());
    }
  }

  return {
    mustHave: merged,
    niceToHave,
    seniority: extracted?.seniority ?? "mid",
    roleType: extracted?.role_type ?? "other",
    // Pulled from Screen 1 by way of the job row, not re-inferred: the
    // recruiter already answered this and the model's opinion does not
    // override theirs.
    locationConstraint:
      detail.job.location ?? extracted?.location_constraints ?? (detail.job.is_remote ? "Remote" : ""),
  };
}

export function toSkillPayloads(draft: ExtractionDraft): RequirementSkillPayload[] {
  return [
    ...draft.mustHave.map((name) => ({
      skill_name: name,
      min_proficiency: DEFAULT_PROFICIENCY,
      is_required: true,
      weight: REQUIRED_WEIGHT,
    })),
    ...draft.niceToHave.map((name) => ({
      skill_name: name,
      min_proficiency: DEFAULT_PROFICIENCY,
      is_required: false,
      weight: DESIRABLE_WEIGHT,
    })),
  ];
}
