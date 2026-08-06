import type { SelectOption } from "@/components";

import type {
  BranchType,
  CodingPlatformType,
  DegreeType,
  EmploymentType,
  SectionCacheKey,
  TargetRoleType,
} from "./api/profileApi";

/**
 * Controlled vocabularies for the filterable fields. Values must stay
 * identical to the backend enums in
 * `apps/backend/src/domains/student/models.py` and `.../auth/models.py` —
 * these are what recruiters will filter on, so they are dropdowns rather
 * than free text on purpose.
 */

export const DEGREE_OPTIONS: SelectOption[] = [
  { value: "btech" satisfies DegreeType, label: "B.Tech" },
  { value: "be" satisfies DegreeType, label: "B.E." },
  { value: "bsc" satisfies DegreeType, label: "B.Sc." },
  { value: "bca" satisfies DegreeType, label: "BCA" },
  { value: "mtech" satisfies DegreeType, label: "M.Tech" },
  { value: "msc" satisfies DegreeType, label: "M.Sc." },
  { value: "mca" satisfies DegreeType, label: "MCA" },
  { value: "mba" satisfies DegreeType, label: "MBA" },
  { value: "phd" satisfies DegreeType, label: "PhD" },
  { value: "other" satisfies DegreeType, label: "Other" },
];

export const BRANCH_OPTIONS: SelectOption[] = [
  { value: "cse" satisfies BranchType, label: "Computer Science" },
  { value: "it" satisfies BranchType, label: "Information Technology" },
  { value: "ece" satisfies BranchType, label: "Electronics & Communication" },
  { value: "eee" satisfies BranchType, label: "Electrical & Electronics" },
  { value: "mechanical" satisfies BranchType, label: "Mechanical" },
  { value: "civil" satisfies BranchType, label: "Civil" },
  { value: "chemical" satisfies BranchType, label: "Chemical" },
  { value: "aiml" satisfies BranchType, label: "AI & Machine Learning" },
  { value: "data_science" satisfies BranchType, label: "Data Science" },
  { value: "other" satisfies BranchType, label: "Other" },
];

export const TARGET_ROLE_OPTIONS: SelectOption[] = [
  { value: "backend" satisfies TargetRoleType, label: "Backend Engineer" },
  { value: "frontend" satisfies TargetRoleType, label: "Frontend Engineer" },
  { value: "fullstack" satisfies TargetRoleType, label: "Full-stack Engineer" },
  { value: "mobile" satisfies TargetRoleType, label: "Mobile Engineer" },
  { value: "data_engineer" satisfies TargetRoleType, label: "Data Engineer" },
  { value: "data_scientist" satisfies TargetRoleType, label: "Data Scientist" },
  { value: "ml_engineer" satisfies TargetRoleType, label: "ML Engineer" },
  { value: "devops" satisfies TargetRoleType, label: "DevOps Engineer" },
  { value: "qa" satisfies TargetRoleType, label: "QA Engineer" },
  { value: "security" satisfies TargetRoleType, label: "Security Engineer" },
  { value: "other" satisfies TargetRoleType, label: "Other" },
];

/** Ordered strongest-evidence-first, so the two platforms that can actually
 * reach `verified` are the ones a student sees at the top of the picker.
 * Everything below Codeforces is checked by URL reachability only and caps at
 * `flagged`; `other` additionally has no URL template, so it asks for the full
 * profile link. */
export const CODING_PLATFORM_OPTIONS: SelectOption[] = [
  { value: "leetcode" satisfies CodingPlatformType, label: "LeetCode" },
  { value: "codeforces" satisfies CodingPlatformType, label: "Codeforces" },
  { value: "codechef" satisfies CodingPlatformType, label: "CodeChef" },
  { value: "hackerrank" satisfies CodingPlatformType, label: "HackerRank" },
  { value: "atcoder" satisfies CodingPlatformType, label: "AtCoder" },
  { value: "geeksforgeeks" satisfies CodingPlatformType, label: "GeeksforGeeks" },
  { value: "other" satisfies CodingPlatformType, label: "Other" },
];

/** Platforms whose live check can return `verified`. The rest can only ever
 * come back `unconfirmed`, and the UI says so rather than implying a check
 * that did not happen — see `live_checks.py`. */
export const API_BACKED_PLATFORMS: CodingPlatformType[] = ["leetcode", "codeforces"];

export const EMPLOYMENT_TYPE_OPTIONS: SelectOption[] = [
  { value: "internship" satisfies EmploymentType, label: "Internship" },
  { value: "full_time" satisfies EmploymentType, label: "Full-time" },
  { value: "part_time" satisfies EmploymentType, label: "Part-time" },
  { value: "freelance" satisfies EmploymentType, label: "Freelance" },
  { value: "research" satisfies EmploymentType, label: "Research" },
  { value: "open_source" satisfies EmploymentType, label: "Open Source" },
];

/** A ten-year window around the current year: wide enough for recent
 * graduates and students a few years out, narrow enough to stay a usable
 * dropdown rather than a free-text year. */
export function graduationYearOptions(now: Date = new Date()): SelectOption[] {
  const current = now.getFullYear();
  const years: SelectOption[] = [];
  for (let year = current - 6; year <= current + 6; year += 1) {
    years.push({ value: String(year), label: String(year) });
  }
  return years;
}

export interface SectionMeta {
  /** Endpoint-shaped, not scoring-shaped: these describe the five *forms*, and
   * `technical` is still one form writing GitHub and coding profiles together
   * even though completeness now scores them as two sections. See
   * `SectionCacheKey` in `api/profileApi.ts`. */
  key: SectionCacheKey;
  title: string;
  description: string;
  isMandatory: boolean;
}

export const SECTIONS: SectionMeta[] = [
  {
    key: "basic",
    title: "Basic Information",
    description: "Who you are and what you are looking for.",
    isMandatory: true,
  },
  {
    key: "technical",
    title: "Technical Verification",
    description: "The accounts we check to prove your work.",
    isMandatory: true,
  },
  {
    key: "projects",
    // Mandatory as of the eight-stage onboarding flow: every downstream
    // artefact — repository verification, the code-grounded interview, the
    // evidence report — starts from a linked repository, so a profile with
    // none is one the pipeline cannot act on.
    title: "Skills & Projects",
    description: "One to three repositories or described projects.",
    isMandatory: true,
  },
  {
    key: "certificates",
    title: "Certificates & Achievements",
    description: "Credentials worth showing, with links where you have them.",
    isMandatory: false,
  },
  {
    key: "experience",
    title: "Experience",
    description: "Internships, freelance and part-time work.",
    isMandatory: false,
  },
];
