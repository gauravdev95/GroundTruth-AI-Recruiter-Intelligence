import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/lib/queryKeys";

import { asyncJobsApi } from "../api/asyncJobsApi";

export function useMyAsyncJobs() {
  return useQuery({ queryKey: queryKeys.asyncJobs.all(), queryFn: asyncJobsApi.list });
}

/** Only the dead-lettered subset — the dashboard's "something needs your
 * attention" surface. Derived client-side from the same list rather than a
 * second endpoint, since the full list is already small (per-caller, not
 * platform-wide — see `jobs/router.py::list_my_jobs`). */
export function useDeadLetteredJobs() {
  const query = useMyAsyncJobs();
  return {
    ...query,
    data: query.data?.filter((job) => job.is_dead_lettered) ?? [],
  };
}

export function useRetryAsyncJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: asyncJobsApi.retry,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.asyncJobs.all() }),
  });
}
