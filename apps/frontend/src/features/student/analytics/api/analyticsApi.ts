import { apiClient } from "@/lib/apiClient";

/** Mirrors `apps/backend/src/domains/pipeline/analytics.py::student_summary`. */
export interface StudentAnalyticsSummary {
  match_count: number;
  profile_views: number;
  application_outcomes: Record<string, number>;
}

export const studentAnalyticsApi = {
  summary: async (): Promise<StudentAnalyticsSummary> => {
    const res = await apiClient.get<StudentAnalyticsSummary>("/student/analytics/summary");
    return res.data;
  },
};
