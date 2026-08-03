import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/lib/queryKeys";

import { pipelineApi, type ApplicationStatus } from "../api/pipelineApi";

export function usePipelineBoard(jobId: string) {
  return useQuery({
    queryKey: queryKeys.pipeline.board(jobId),
    queryFn: () => pipelineApi.getBoard(jobId),
    enabled: Boolean(jobId),
  });
}

export function useRecruiterApplication(applicationId: string) {
  return useQuery({
    queryKey: queryKeys.pipeline.application(applicationId),
    queryFn: () => pipelineApi.getApplication(applicationId),
    enabled: Boolean(applicationId),
  });
}

/** Illegal transitions are rejected server-side (`ALLOWED_TRANSITIONS`) —
 * the caller surfaces `error` via toast rather than swallowing it, per the
 * "illegal-transition errors surfaced, not swallowed" requirement. */
export function useTransitionApplication(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ applicationId, toStatus }: { applicationId: string; toStatus: ApplicationStatus }) =>
      pipelineApi.transition(applicationId, toStatus),
    onSuccess: (_data, { applicationId }) => invalidateApplication(queryClient, jobId, applicationId),
  });
}

/** Undo the last forward transition (`ALLOWED_ROLLBACKS`). Illegal rollbacks
 * (`applied`, `hired`) 409 from the same `Conflict` path an illegal forward
 * transition raises, so the caller surfaces both the same way. */
export function useRollbackApplication(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (applicationId: string) => pipelineApi.rollback(applicationId),
    onSuccess: (_data, applicationId) => invalidateApplication(queryClient, jobId, applicationId),
  });
}

/** Both mutations move the same application, so both invalidate the board
 * *and* that application's own detail entry — a stale detail page showing
 * the pre-move stage (and a `rollback_target` that no longer applies) is the
 * failure mode of invalidating only the board. */
function invalidateApplication(
  queryClient: ReturnType<typeof useQueryClient>,
  jobId: string,
  applicationId: string,
) {
  void queryClient.invalidateQueries({ queryKey: queryKeys.pipeline.board(jobId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.pipeline.application(applicationId) });
}
