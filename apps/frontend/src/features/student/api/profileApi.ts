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

/** Mirrors the backend's `CodingPlatform`. Only `codeforces` and `leetcode`
 * can reach `verified` — every other platform exposes no usable public API and
 * is checked by URL reachability alone, so they cap at `flagged` and
 * contribute no verified competencies.
 *
 * `other` is the escape hatch: no URL template and no checker, so the student
 * supplies both a display name and the full profile URL. */
export type CodingPlatformType =
  | "leetcode"
  | "codeforces"
  | "hackerrank"
  | "codechef"
  | "atcoder"
  | "geeksforgeeks"
  | "other";
export type ProjectKind = "repository" | "described";
export type EmploymentType =
  | "internship"
  | "full_time"
  | "freelance"
  | "part_time"
  | "research"
  | "open_source";

/** Mirrors the backend's `VerificationStatus`. Never conflate with "filled".
 * `flagged` means visible-but-unconfirmed — weaker than `rejected` (which
 * means the check actively contradicted the claim), stronger than
 * `unverified` (nothing was found either way). */
export type VerificationStatus = "unverified" | "pending" | "verified" | "rejected" | "flagged";

/**
 * The keys the server scores and returns in `completeness.sections`.
 *
 * `github` and `coding` are separate sections, not the one `technical` they
 * used to be: GitHub is mandatory and starts the evidence pipeline, while a
 * coding-platform handle is a supporting signal the student may skip. See
 * `backend/src/domains/student/completeness.py`.
 */
export type SectionKey = "basic" | "github" | "projects" | "coding" | "certificates" | "experience";

/**
 * The keys the *endpoints* are shaped around, which is deliberately not the
 * same list.
 *
 * `GET/PUT /sections/technical` still returns and writes the GitHub account and
 * the coding profiles together — they are one resource on the wire even though
 * they are two scored sections — so one cache entry backs both. Splitting the
 * cache to match the scoring split would give two entries holding overlapping
 * copies of the same payload, and a save through either one would leave the
 * other stale.
 */
export type SectionCacheKey = "basic" | "technical" | "projects" | "certificates" | "experience";

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
  /** The student pressed Submit on the review step. **This**, not
   * `meets_section_requirements`, is what opens the dashboard. */
  is_onboarding_submitted: boolean;
}

export interface SectionEnvelope<T> {
  data: T;
  completeness: ProfileCompleteness;
}

// --- Section 1 ---

export interface BasicInfo {
  /** NULL between signup and the first save of this section. */
  full_name: string | null;
  phone_number: string | null;
  headline: string | null;
  college: string | null;
  degree: DegreeType | null;
  branch: BranchType | null;
  graduation_year: number | null;
  location: string | null;
  /** The primary role — always `target_roles[0]`. Present because the
   * recruiter-facing surfaces read this one; a UI showing a single role should
   * show the same one the matcher used. */
  target_role: TargetRoleType | null;
  /** All one to three roles, in the student's stated order of preference.
   * `null` (not `[]`) for a profile that has never saved this section. */
  target_roles: TargetRoleType[] | null;
  about: string | null;
  /** The image itself comes from `GET /student/profile/photo`, which mints a
   * short-lived link — an object key never reaches the client. */
  has_profile_photo: boolean;
}

export interface BasicInfoPayload {
  /** Collected here rather than at signup, which is email + password only.
   * Writes through to the account (`User.full_name`), not the profile. */
  full_name: string;
  /** Optional. `""` clears it; omitting it leaves any existing number alone. */
  phone_number?: string;
  headline: string;
  college: string;
  degree: DegreeType;
  branch: BranchType;
  graduation_year: number;
  location: string;
  /** One to three, order significant — the first becomes the primary role.
   * The scalar `target_role` is derived server-side and is rejected here. */
  target_roles: TargetRoleType[];
  /** Optional, unlike every other field here: `about` earns no completeness
   * points, and a field that cannot affect whether the section is complete
   * must not be able to block the save. It does reach the profile embedding,
   * so filling it in still improves match quality. */
  about?: string | null;
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
  /** Set only for `platform: "other"` — the name the student typed. */
  custom_platform_name?: string | null;
  verification_status: VerificationStatus;
  verified_at: string | null;
  verification_score?: number | null;
  verification_source?: string | null;
}

export interface TechnicalSection {
  github_account: GithubAccount | null;
  coding_profiles: CodingPlatformAccount[];
}

export interface CodingProfilePayloadItem {
  platform: CodingPlatformType;
  handle: string;
  /** Required for `other`, rejected for every other platform — the backend
   * derives the URL from its own template otherwise. */
  custom_platform_name?: string | null;
  profile_url?: string | null;
}

export interface TechnicalPayload {
  github_username: string;
  /** May be empty. GitHub and coding profiles are separate sections now and
   * only GitHub is required, so a profile with no handles is a valid save. */
  coding_profiles: CodingProfilePayloadItem[];
}

/** The onboarding coding stage's payload. Carries no `github_username`, which
 * is what keeps saving the optional section from disturbing the mandatory one.
 * An empty list is what "Skip for now" sends. */
export interface CodingProfilesPayload {
  coding_profiles: CodingProfilePayloadItem[];
}

/** `url` is null when no photo is stored — an ordinary answer the avatar
 * renders initials for, not an error. */
export interface ProfilePhoto {
  url: string | null;
  content_type: string | null;
  expires_in_seconds: number | null;
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
  live_demo_url: string | null;
  /** The student's nominated best project. At most one per profile. */
  is_primary: boolean;
  /** Read-only. Detected from the repository's own dependency manifests by
   * `verify_repository_task` — never typed by the candidate, which is why the
   * payload sends `claimed_technologies` instead. A described project has no
   * manifest to analyse and so stays empty. */
  technologies: string[];
  /** What the student typed. Kept apart from `technologies` so the UI can show
   * the difference between a claim and a detection. */
  claimed_technologies: string[];
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
    live_demo_url?: string | null;
    is_primary: boolean;
    // Named `claimed_`, and it is not the same field as `Project.technologies`
    // above. The backend's `ProjectItem` forbids unknown keys, so sending
    // plain `technologies` is a 422 — that column is worker-owned.
    claimed_technologies: string[];
  }[];
}

// --- Section 4 ---

export interface Certificate {
  id: string;
  title: string;
  issuer: string;
  issued_at: string | null;
  credential_url: string | null;
  /** Present when a file is attached. The object key is deliberately never
   * returned — `GET /certificates/{id}/file` mints a short-lived link. */
  file_name: string | null;
  file_size_bytes: number | null;
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
    /** Only sent for a *newly* uploaded file. Omitting it preserves whatever
     * is already attached — the key is never returned, so an unchanged
     * certificate always re-saves without one, and treating that as a delete
     * would wipe the file on every edit. `remove_file` is the explicit
     * detach. */
    file_object_key?: string | null;
    file_name?: string | null;
    file_content_type?: string | null;
    file_size_bytes?: number | null;
    remove_file?: boolean;
  }[];
}

/** What `POST /certificates/uploads` hands back, to be echoed on the next
 * section save. */
export interface CertificateUpload {
  file_object_key: string;
  file_name: string;
  file_content_type: string;
  file_size_bytes: number;
}

export interface CertificateFileUrl {
  url: string;
  file_name: string;
  expires_in_seconds: number;
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

  /** Onboarding stage 4. Returns the whole technical envelope, not just the
   * coding half, so one cache entry stays consistent from either writer. */
  saveCodingProfiles: async (payload: CodingProfilesPayload): Promise<SectionEnvelope<TechnicalSection>> => {
    const res = await apiClient.put<SectionEnvelope<TechnicalSection>>(`${BASE}/sections/coding`, payload);
    return res.data;
  },

  profilePhoto: async (): Promise<ProfilePhoto> => {
    const res = await apiClient.get<ProfilePhoto>(`${BASE}/photo`);
    return res.data;
  },

  uploadProfilePhoto: async (file: File): Promise<SectionEnvelope<BasicInfo>> => {
    const body = new FormData();
    body.append("file", file);
    // Content-Type left unset so the browser supplies the multipart boundary —
    // same reason as `uploadCertificateFile`.
    const res = await apiClient.post<SectionEnvelope<BasicInfo>>(`${BASE}/photo`, body);
    return res.data;
  },

  deleteProfilePhoto: async (): Promise<SectionEnvelope<BasicInfo>> => {
    const res = await apiClient.delete<SectionEnvelope<BasicInfo>>(`${BASE}/photo`);
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

  uploadCertificateFile: async (file: File): Promise<CertificateUpload> => {
    const body = new FormData();
    body.append("file", file);
    // The Content-Type header is left unset on purpose: the browser has to
    // supply it so it can include the multipart boundary.
    const res = await apiClient.post<CertificateUpload>(`${BASE}/certificates/uploads`, body);
    return res.data;
  },

  certificateFileUrl: async (certificateId: string): Promise<CertificateFileUrl> => {
    const res = await apiClient.get<CertificateFileUrl>(
      `${BASE}/certificates/${certificateId}/file`,
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
