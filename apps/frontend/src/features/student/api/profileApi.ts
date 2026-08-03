import { apiClient } from "@/lib/apiClient";

/**
 * Types mirror `apps/backend/src/domains/student/schemas.py`. The backend is
 * authoritative for validation; these exist so the UI is typed end to end.
 *
 * `profile_strength` and `is_discoverable` appear only in responses — there is
 * deliberately no payload type carrying them, because the server computes both
 * and rejects any request that tries to supply them.
 */

const BASE = "/student/profile";

export type DegreeType =
  | "btech"
  | "be"
  | "bsc"
  | "bca"
  | "mtech"
  | "msc"
  | "mca"
  | "mba"
  | "phd"
  | "other";

export type BranchType =
  | "cse"
  | "it"
  | "ece"
  | "eee"
  | "mechanical"
  | "civil"
  | "chemical"
  | "aiml"
  | "data_science"
  | "other";

export type TargetRoleType =
  | "backend"
  | "frontend"
  | "fullstack"
  | "mobile"
  | "data_engineer"
  | "data_scientist"
  | "ml_engineer"
  | "devops"
  | "qa"
  | "security"
  | "other";

export type CodingPlatformType = "leetcode" | "codeforces" | "hackerrank";
export type ProjectKind = "repository" | "described";
export type EmploymentType = "internship" | "freelance" | "part_time";

/** Mirrors the backend's `VerificationStatus`. Never conflate with "filled".
 * `flagged` means visible-but-unconfirmed — weaker than `rejected` (which
 * means the check actively contradicted the claim), stronger than
 * `unverified` (nothing was found either way). */
export type VerificationStatus = "unverified" | "pending" | "verified" | "rejected" | "flagged";

export type SectionKey = "basic" | "technical" | "projects" | "certificates" | "experience";

export interface SectionStatus {
  key: SectionKey;
  is_complete: boolean;
  is_filled: boolean;
  is_mandatory: boolean;
  filled_count: number;
  required_count: number;
  points_earned: number;
  points_possible: number;
  verification: VerificationStatus | null;
  missing: string[];
}

export type OnboardingChoice = "resume_upload" | "manual_entry";

export interface ProfileCompleteness {
  profile_strength: number;
  /** Sections 1-2 complete. True with `is_discoverable` false means the
   * embedding worker is still running — not that the student owes anything. */
  meets_section_requirements: boolean;
  is_discoverable: boolean;
  sections: SectionStatus[];
  blocking: string[];
  /** `null` until the student answers the onboarding fork. */
  onboarding_choice: OnboardingChoice | null;
}

export interface SectionEnvelope<T> {
  data: T;
  completeness: ProfileCompleteness;
}

// --- Section 1 ---

export interface BasicInfo {
  headline: string | null;
  college: string | null;
  degree: DegreeType | null;
  branch: BranchType | null;
  graduation_year: number | null;
  location: string | null;
  target_role: TargetRoleType | null;
}

export interface BasicInfoPayload {
  headline: string;
  college: string;
  degree: DegreeType;
  branch: BranchType;
  graduation_year: number;
  location: string;
  target_role: TargetRoleType;
}

// --- Section 2 ---

export interface GithubAccount {
  id: string;
  github_username: string;
  profile_url: string;
  verification_status: VerificationStatus;
  verified_at: string | null;
  verification_score?: number | null;
  verification_source?: string | null;
}

export interface CodingPlatformAccount {
  id: string;
  platform: CodingPlatformType;
  handle: string;
  profile_url: string;
  verification_status: VerificationStatus;
  verified_at: string | null;
  verification_score?: number | null;
  verification_source?: string | null;
}

export interface TechnicalSection {
  github_account: GithubAccount | null;
  coding_profiles: CodingPlatformAccount[];
}

export interface TechnicalPayload {
  github_username: string;
  coding_profiles: { platform: CodingPlatformType; handle: string }[];
}

// --- Section 3 ---

/** The seven stages of repository verification, in run order —
 * `domains/student/models.py::VerificationStageKind`. */
export type VerificationStageKind =
  | "repository_selection"
  | "fork_authorship_check"
  | "contribution_analysis"
  | "architecture_code_quality"
  | "technology_detection"
  | "code_grounded_interview"
  | "evidence_report";

/** `skipped` is not `failed`: a stage that never ran because an earlier one
 * failed (or because authorship was rejected, which deliberately suppresses
 * the interview) is not itself a failure, and the timeline must not conflate
 * them. */
export type VerificationStageStatus = "pending" | "running" | "succeeded" | "failed" | "skipped";

export interface VerificationStage {
  stage: VerificationStageKind;
  status: VerificationStageStatus;
  sequence: number;
  result?: Record<string, unknown> | null;
  error?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface Project {
  id: string;
  kind: ProjectKind;
  title: string;
  description: string | null;
  repo_url: string | null;
  technologies: string[];
  verification_status: VerificationStatus;
  verified_at: string | null;
  verification_score?: number | null;
  verification_source?: string | null;
  /** Contribution analysis etc., written by `verify_repository_task`. */
  verification_payload?: { contribution_share?: number; is_fork?: boolean } | null;
  /** Per-stage progress. `verification_status` says only where a repository
   * ended up; these say how far it got and which stage stopped it — the
   * difference between "unverified" and "unverified because the authorship
   * check rejected it". */
  verification_stages?: VerificationStage[];
}

export interface ProjectsSection {
  projects: Project[];
}

export interface ProjectsPayload {
  projects: {
    kind: ProjectKind;
    title: string;
    description?: string | null;
    repo_url?: string | null;
    technologies: string[];
  }[];
}

// --- Section 4 ---

export interface Certificate {
  id: string;
  title: string;
  issuer: string;
  issued_at: string | null;
  credential_url: string | null;
  verification_status: VerificationStatus;
  verified_at: string | null;
  verification_score?: number | null;
  verification_source?: string | null;
}

export interface CertificatesSection {
  certificates: Certificate[];
}

export interface CertificatesPayload {
  certificates: {
    title: string;
    issuer: string;
    issued_at?: string | null;
    credential_url?: string | null;
  }[];
}

// --- Section 5 ---

export interface Experience {
  id: string;
  company_name: string;
  title: string;
  employment_type: EmploymentType;
  start_date: string;
  end_date: string | null;
  description: string | null;
  technologies: string[];
  verification_status: VerificationStatus;
  verified_at: string | null;
  verification_score?: number | null;
  verification_source?: string | null;
}

export interface ExperiencesSection {
  experiences: Experience[];
}

export interface ExperiencesPayload {
  experiences: {
    company_name: string;
    title: string;
    employment_type: EmploymentType;
    start_date: string;
    end_date?: string | null;
    description?: string | null;
    technologies: string[];
  }[];
}

export const profileApi = {
  completeness: async (): Promise<ProfileCompleteness> => {
    const res = await apiClient.get<ProfileCompleteness>(`${BASE}/completeness`);
    return res.data;
  },

  chooseOnboarding: async (choice: OnboardingChoice): Promise<ProfileCompleteness> => {
    const res = await apiClient.post<ProfileCompleteness>(`${BASE}/onboarding`, { choice });
    return res.data;
  },

  getBasic: async (): Promise<SectionEnvelope<BasicInfo>> => {
    const res = await apiClient.get<SectionEnvelope<BasicInfo>>(`${BASE}/sections/basic`);
    return res.data;
  },
  saveBasic: async (payload: BasicInfoPayload): Promise<SectionEnvelope<BasicInfo>> => {
    const res = await apiClient.put<SectionEnvelope<BasicInfo>>(`${BASE}/sections/basic`, payload);
    return res.data;
  },

  getTechnical: async (): Promise<SectionEnvelope<TechnicalSection>> => {
    const res = await apiClient.get<SectionEnvelope<TechnicalSection>>(`${BASE}/sections/technical`);
    return res.data;
  },
  saveTechnical: async (payload: TechnicalPayload): Promise<SectionEnvelope<TechnicalSection>> => {
    const res = await apiClient.put<SectionEnvelope<TechnicalSection>>(`${BASE}/sections/technical`, payload);
    return res.data;
  },

  getProjects: async (): Promise<SectionEnvelope<ProjectsSection>> => {
    const res = await apiClient.get<SectionEnvelope<ProjectsSection>>(`${BASE}/sections/projects`);
    return res.data;
  },
  saveProjects: async (payload: ProjectsPayload): Promise<SectionEnvelope<ProjectsSection>> => {
    const res = await apiClient.put<SectionEnvelope<ProjectsSection>>(`${BASE}/sections/projects`, payload);
    return res.data;
  },

  getCertificates: async (): Promise<SectionEnvelope<CertificatesSection>> => {
    const res = await apiClient.get<SectionEnvelope<CertificatesSection>>(`${BASE}/sections/certificates`);
    return res.data;
  },
  saveCertificates: async (payload: CertificatesPayload): Promise<SectionEnvelope<CertificatesSection>> => {
    const res = await apiClient.put<SectionEnvelope<CertificatesSection>>(
      `${BASE}/sections/certificates`,
      payload,
    );
    return res.data;
  },

  getExperiences: async (): Promise<SectionEnvelope<ExperiencesSection>> => {
    const res = await apiClient.get<SectionEnvelope<ExperiencesSection>>(`${BASE}/sections/experience`);
    return res.data;
  },
  saveExperiences: async (payload: ExperiencesPayload): Promise<SectionEnvelope<ExperiencesSection>> => {
    const res = await apiClient.put<SectionEnvelope<ExperiencesSection>>(
      `${BASE}/sections/experience`,
      payload,
    );
    return res.data;
  },
};
