import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "@/lib/queryKeys";

import { studentAnalyticsApi } from "../api/analyticsApi";

export function useStudentAnalytics() {
  return useQuery({ queryKey: queryKeys.studentAnalytics.summary(), queryFn: studentAnalyticsApi.summary });
}
