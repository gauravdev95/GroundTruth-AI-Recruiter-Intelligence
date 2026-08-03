import { apiClient } from "@/lib/apiClient";

/** Types mirror `apps/backend/src/domains/pipeline/schemas.py`. */

export type ApplicationStatus = "applied" | "shortlisted" | "interview_scheduled" | "hired" | "rejected";

export interface PipelineCandidatePreview {
  candidate_profile_id: string;
  headline: string | null;
  match_score: number;
}

/** Sign of the movement. `"unknown"` when one of the two scores is missing
 * — see `domains/pipeline/drift.py::ScoreDrift`, which is deliberate: it is
 * a different claim from "the score has not moved". */
export type DriftDirection = "up" | "down" | "flat" | "unknown";

export interface ScoreDrift {
  score_at_apply: number | null;
  live_score: number | null;
  points: number | null;
  direction: DriftDirection;
  /** `abs(points) >= MEANINGFUL_DRIFT_POINTS` (5.0) — the magnitude test,
   * separate from `direction`'s sign so the UI can emphasise without the
   * server having thrown the raw number away. */
  is_meaningful: boolean;
}

export interface PipelineApplicationPreview {
  application_id: string;
  candidate_profile_id: string;
  headline: string | null;
  status: string;
  applied_at: string;
  status_updated_at: string;
  /** Frozen at Smart Apply — the number the shortlisting decision was made
   * against. Null only for applications backfilled by migration b2d5e8f14c73. */
  score_at_apply: number | null;
  /** The *live* score. Null when the pair's `match_results` row is gone. */
  match_score: number | null;
  drift_points: number | null;
  drift_direction: DriftDirection;
  drift_is_meaningful: boolean;
  can_roll_back: boolean;
}

export interface PipelineBoard {
  matched: PipelineCandidatePreview[];
  applied: PipelineApplicationPreview[];
  shortlisted: PipelineApplicationPreview[];
  interview_scheduled: PipelineApplicationPreview[];
  hired: PipelineApplicationPreview[];
  rejected: PipelineApplicationPreview[];
}

export interface Application {
  id: string;
  job_posting_id: string;
  candidate_profile_id: string;
  status: ApplicationStatus;
  cover_note: string | null;
  applied_at: string;
  status_updated_at: string;
  score_at_apply: number | null;
}

export interface RecruiterApplicationDetail {
  application: Application;
  job_title: string;
  company_name: string;
  candidate_profile_id: string;
  candidate_headline: string | null;
  drift: ScoreDrift;
  can_roll_back: boolean;
  /** The exact stage a rollback would restore. Server-derived: for a rejected
   * application it comes from `audit_log`, so the client cannot compute it. */
  rollback_target: ApplicationStatus | null;
}

export const pipelineApi = {
  getBoard: async (jobId: string): Promise<PipelineBoard> => {
    const res = await apiClient.get<PipelineBoard>(`/recruiter/jobs/${jobId}/pipeline`);
    return res.data;
  },
  transition: async (applicationId: string, toStatus: ApplicationStatus): Promise<Application> => {
    const res = await apiClient.post<Application>(`/recruiter/applications/${applicationId}/transition`, {
      to_status: toStatus,
    });
    return res.data;
  },
  /** Undo the last forward transition. No body: for a rejected application
   * the target is read off `audit_log` server-side, so there is nothing for
   * a client to name (`domains/pipeline/router.py::rollback_application`). */
  rollback: async (applicationId: string): Promise<Application> => {
    const res = await apiClient.post<Application>(`/recruiter/applications/${applicationId}/rollback`);
    return res.data;
  },
  getApplication: async (applicationId: string): Promise<RecruiterApplicationDetail> => {
    const res = await apiClient.get<RecruiterApplicationDetail>(`/recruiter/applications/${applicationId}`);
    return res.data;
  },
};
