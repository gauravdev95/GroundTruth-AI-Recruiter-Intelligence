import { apiClient } from "@/lib/apiClient";

/** Mirrors `apps/backend/src/domains/pipeline/analytics.py::recruiter_funnel`. */
export interface RecruiterFunnel {
  stage_counts: Record<string, number>;
  total_applications: number;
  conversion: Record<string, number | null>;
  avg_time_to_first_response_hours: number | null;
}

/** Mirrors `apps/backend/src/domains/pipeline/analytics.py::recruiter_activity`.
 * Days with no activity are present as zeroes — the series is dense, so a
 * sparkline cannot compress a quiet week into a line that looks busy. */
export interface RecruiterActivity {
  window_days: number;
  series: { date: string; matches: number; applications: number }[];
}

export const recruiterAnalyticsApi = {
  funnel: async (): Promise<RecruiterFunnel> => {
    const res = await apiClient.get<RecruiterFunnel>("/recruiter/analytics/funnel");
    return res.data;
  },
  activity: async (): Promise<RecruiterActivity> => {
    const res = await apiClient.get<RecruiterActivity>("/recruiter/analytics/activity");
    return res.data;
  },
};
