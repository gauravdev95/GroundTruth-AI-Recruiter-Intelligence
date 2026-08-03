import { apiClient } from "@/lib/apiClient";

/** Mirrors `apps/backend/src/domains/pipeline/analytics.py::recruiter_funnel`. */
export interface RecruiterFunnel {
  stage_counts: Record<string, number>;
  total_applications: number;
  conversion: Record<string, number | null>;
  avg_time_to_first_response_hours: number | null;
}

export const recruiterAnalyticsApi = {
  funnel: async (): Promise<RecruiterFunnel> => {
    const res = await apiClient.get<RecruiterFunnel>("/recruiter/analytics/funnel");
    return res.data;
  },
};
