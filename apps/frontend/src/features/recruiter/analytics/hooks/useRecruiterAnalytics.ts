import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "@/lib/queryKeys";

import { recruiterAnalyticsApi } from "../api/analyticsApi";

export function useRecruiterFunnel() {
  return useQuery({ queryKey: queryKeys.recruiterAnalytics.funnel(), queryFn: recruiterAnalyticsApi.funnel });
}

export function useRecruiterActivity() {
  return useQuery({
    queryKey: queryKeys.recruiterAnalytics.activity(),
    queryFn: recruiterAnalyticsApi.activity,
  });
}
