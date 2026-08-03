import { apiClient } from "@/lib/apiClient";

import type { SectionKey } from "../../api/profileApi";

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

export interface SetupStep {
  key: SectionKey;
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
  /** Sections 1 and 2 complete. This — not `onboarding_choice` — is what
   * decides whether a student still belongs on the setup screen. */
  meets_section_requirements: boolean;
  is_discoverable: boolean;
  blocking: string[];
  steps: SetupStep[];
  resume: ResumeSetupState;
}

export const setupApi = {
  getState: async (): Promise<SetupState> => {
    const res = await apiClient.get<SetupState>(`${BASE}/setup-state`);
    return res.data;
  },
};
