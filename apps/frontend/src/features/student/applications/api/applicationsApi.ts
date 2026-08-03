import { apiClient } from "@/lib/apiClient";

/** Types mirror `apps/backend/src/domains/pipeline/schemas.py`. */

const BASE = "/student";

export type ApplicationStatus =
  | "applied"
  | "shortlisted"
  | "interview_scheduled"
  | "hired"
  | "rejected";

export interface Application {
  id: string;
  job_posting_id: string;
  candidate_profile_id: string;
  status: ApplicationStatus;
  cover_note: string | null;
  applied_at: string;
  status_updated_at: string;
}

export interface ApplicationListItem {
  application: Application;
  job_title: string;
  company_name: string;
}

export interface ApplicationDetail {
  application: Application;
  evidence_snapshot: Record<string, unknown>;
  job_title: string;
  company_name: string;
}

export const applicationsApi = {
  apply: async (jobId: string, coverNote: string | null): Promise<Application> => {
    const res = await apiClient.post<Application>(`${BASE}/jobs/${jobId}/apply`, { cover_note: coverNote });
    return res.data;
  },
  list: async (): Promise<ApplicationListItem[]> => {
    const res = await apiClient.get<ApplicationListItem[]>(`${BASE}/applications`);
    return res.data;
  },
  get: async (applicationId: string): Promise<ApplicationDetail> => {
    const res = await apiClient.get<ApplicationDetail>(`${BASE}/applications/${applicationId}`);
    return res.data;
  },
};
