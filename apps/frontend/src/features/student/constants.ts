import type { SelectOption } from "@/components";

import type {
  BranchType,
  CodingPlatformType,
  DegreeType,
  EmploymentType,
  SectionKey,
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

export const CODING_PLATFORM_OPTIONS: SelectOption[] = [
  { value: "leetcode" satisfies CodingPlatformType, label: "LeetCode" },
  { value: "codeforces" satisfies CodingPlatformType, label: "Codeforces" },
  { value: "hackerrank" satisfies CodingPlatformType, label: "HackerRank" },
];

export const EMPLOYMENT_TYPE_OPTIONS: SelectOption[] = [
  { value: "internship" satisfies EmploymentType, label: "Internship" },
  { value: "freelance" satisfies EmploymentType, label: "Freelance" },
  { value: "part_time" satisfies EmploymentType, label: "Part-time" },
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
  key: SectionKey;
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
    title: "Skills & Projects",
    description: "Up to three repositories or described projects.",
    isMandatory: false,
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
