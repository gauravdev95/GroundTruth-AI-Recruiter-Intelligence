import { apiClient } from "@/lib/apiClient";

import type {
  CodingPlatformType,
  ProfileCompleteness,
  SectionKey,
} from "../../api/profileApi";

/**
 * Types mirror `apps/backend/src/domains/student/schemas.py::SetupStateResponse`.
 *
 * One call backs the whole setup entry screen — stepper, percentage pill, and
 * the resume card's in-flight state. Nothing here is ever sent *to* the server:
 * every field is derived server-side from persisted rows, and the percentage in
 * particular is never a client computation.
 */

const BASE = "/student/profile";

/** `saved` is not `verified`. A step with content shows a check; only
 * `verified` licenses the verified badge, and `pending_verification` means a
 * check is running or ran without confirming. */
export type SetupStepStatus = "empty" | "saved" | "pending_verification" | "verified";

/** The resume half of the flow. Maps from the backend's `ResumeUploadStatus`
 * (`processing` → `parsing`, `extracted` → `parsed`) at the API boundary. */
export type ResumeParseState = "uploaded" | "parsing" | "parsed" | "failed";

export type ResumeDraftStatus = "pending_review" | "confirmed" | "discarded";

/** The two steps that are not profile sections: the resume-or-manual fork and
 * the final review. Both are numbered and rendered like the rest. */
export type SetupStepKey = SectionKey | "choose" | "review";

export interface SetupStep {
  key: SetupStepKey;
  index: number;
  title: string;
  subtitle: string;
  status: SetupStepStatus;
  is_mandatory: boolean;
  /** Display hint for the violet circle and the "Current Step" pill. Never a
   * gate — every step stays clickable. */
  is_current: boolean;
  filled_count: number;
  required_count: number;
}

export interface ResumeSetupState {
  has_upload: boolean;
  upload_id: string | null;
  status: ResumeParseState | null;
  async_job_id: string | null;
  draft_id: string | null;
  draft_status: ResumeDraftStatus | null;
  original_filename: string | null;
  error: string | null;
}

export interface SetupState {
  completion_percentage: number;
  current_step_index: number;
  /** Sections 1 and 2 complete — the bar for *submitting*. Not the gate: a
   * student who meets this and has not pressed Submit is still in setup. */
  meets_section_requirements: boolean;
  is_discoverable: boolean;
  blocking: string[];
  steps: SetupStep[];
  resume: ResumeSetupState;
  /** Onboarding is finished. The only thing that opens the dashboard. */
  is_submitted: boolean;
  /** Whether pressing Submit would succeed right now. */
  can_submit: boolean;
}

export interface ProfileSubmitResult {
  is_submitted: boolean;
  submitted_at: string;
  /** How many background checks the submission started. The student waits on
   * none of them. */
  queued_verifications: number;
  completeness: ProfileCompleteness;
}

/** What a *live* check concluded. Deliberately not `VerificationStatus`: that
 * is the durable state of a stored claim, written only by the background
 * workers. These three describe one probe and are never persisted.
 *
 * `unconfirmed` is the honest answer for a platform with no public API — the
 * page resolves, which proves the profile exists, not that it is the
 * student's. */
export type VerifyOutcome = "verified" | "unconfirmed" | "failed";

export interface VerifyGithubResult {
  outcome: VerifyOutcome;
  message: string;
  github_username: string;
  profile_url: string;
  avatar_url: string | null;
  public_repos: number | null;
  /** Already connected via OAuth, which is stronger than anything the plain
   * API check can establish. */
  is_oauth_connected: boolean;
}

export interface VerifyCodingProfileResult {
  outcome: VerifyOutcome;
  message: string;
  platform: CodingPlatformType;
  handle: string;
  profile_url: string;
  details: Record<string, unknown>;
}

export const setupApi = {
  getState: async (): Promise<SetupState> => {
    const res = await apiClient.get<SetupState>(`${BASE}/setup-state`);
    return res.data;
  },

  /**
   * Finish onboarding. `consent` is the review step's DPDP checkbox and must
   * be `true` — the server 422s anything else, and records the consent in the
   * same transaction as the submission.
   */
  submit: async (consent: boolean): Promise<ProfileSubmitResult> => {
    const res = await apiClient.post<ProfileSubmitResult>(`${BASE}/submit`, { consent });
    return res.data;
  },

  verifyGithub: async (githubUsername: string): Promise<VerifyGithubResult> => {
    const res = await apiClient.post<VerifyGithubResult>(`${BASE}/verify/github`, {
      github_username: githubUsername,
    });
    return res.data;
  },

  verifyCodingProfile: async (input: {
    platform: CodingPlatformType;
    handle: string;
    profile_url?: string | null;
  }): Promise<VerifyCodingProfileResult> => {
    const res = await apiClient.post<VerifyCodingProfileResult>(
      `${BASE}/verify/coding-profile`,
      input,
    );
    return res.data;
  },
};
