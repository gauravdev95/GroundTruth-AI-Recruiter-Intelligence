import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/lib/queryKeys";

import { applicationsApi } from "../api/applicationsApi";

export function useMyApplications() {
  return useQuery({ queryKey: queryKeys.applications.mine(), queryFn: applicationsApi.list });
}

export function useApplication(applicationId: string) {
  return useQuery({
    queryKey: queryKeys.applications.detail(applicationId),
    queryFn: () => applicationsApi.get(applicationId),
    enabled: Boolean(applicationId),
  });
}

export function useSmartApply() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ jobId, coverNote }: { jobId: string; coverNote: string | null }) =>
      applicationsApi.apply(jobId, coverNote),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.applications.mine() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.studentFeed.jobs() });
    },
  });
}
