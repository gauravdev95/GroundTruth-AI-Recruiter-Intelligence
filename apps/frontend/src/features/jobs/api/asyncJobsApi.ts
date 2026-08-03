import { apiClient } from "@/lib/apiClient";

/** Types mirror `apps/backend/src/domains/resume/schemas.py::JobStatusResponse`.
 * Shared by both roles — `GET /api/v1/jobs` and `POST /api/v1/jobs/{id}/retry`
 * are scoped server-side to whatever the caller owns (see `jobs/router.py`'s
 * `_owns_job`), so one client backs both dashboards' dead-letter surfaces. */

const BASE = "/jobs";

export type AsyncJobRunStatus = "pending" | "running" | "succeeded" | "failed";

export interface AsyncJobStatus {
  id: string;
  job_type: string;
  status: AsyncJobRunStatus;
  attempts: number;
  error: string | null;
  result: Record<string, unknown> | null;
  is_dead_lettered: boolean;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export const asyncJobsApi = {
  list: async (): Promise<AsyncJobStatus[]> => {
    const res = await apiClient.get<AsyncJobStatus[]>(BASE);
    return res.data;
  },
  get: async (jobId: string): Promise<AsyncJobStatus> => {
    const res = await apiClient.get<AsyncJobStatus>(`${BASE}/${jobId}`);
    return res.data;
  },
  retry: async (jobId: string): Promise<AsyncJobStatus> => {
    const res = await apiClient.post<AsyncJobStatus>(`${BASE}/${jobId}/retry`);
    return res.data;
  },
};
