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

/**
 * Smart Apply — one call, no payload beyond the job id.
 *
 * `coverNote` was removed from this signature on 2026-08-06. The product rule
 * is that the verified evidence profile *is* the application: one click, no
 * form, no re-entry. An optional textarea is still a form — it puts a
 * decision ("should I write something?") between the student and the action,
 * which is the friction Smart Apply exists to delete.
 *
 * The API still accepts a note and `pipeline/evidence.py` still stores one,
 * so nothing was removed server-side and older applications keep theirs. This
 * client simply never sends it. If a "add a note" affordance is wanted later
 * it belongs *after* applying, on the application itself, where it cannot
 * gate the apply.
 */
export function useSmartApply() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ jobId }: { jobId: string }) => applicationsApi.apply(jobId, null),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.applications.mine() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.studentFeed.jobs() });
    },
  });
}
