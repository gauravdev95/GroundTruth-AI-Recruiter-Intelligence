import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/lib/queryKeys";

import {
  pipelineApi,
  type ApplicationStatus,
  type CloseReason,
  type PipelineApplicationPreview,
  type PipelineBoard,
} from "../api/pipelineApi";

/** The five board keys that hold applications. `matched` is excluded: it
 * holds candidates with no application, which no transition can move. */
const APPLICATION_KEYS = [
  "applied",
  "shortlisted",
  "interview_scheduled",
  "hired",
  "rejected",
] as const satisfies readonly (keyof PipelineBoard)[];

/**
 * Moves one application between board columns in the cache.
 *
 * Re-sorts the destination by `score_at_apply DESC NULLS LAST`, matching
 * `pipeline/service.py::get_pipeline`'s SQL ordering. Dropping the card at
 * the end of the column instead would put it in a position the very next
 * refetch moves it out of, which reads as the board rejecting the move.
 */
function moveInBoard(
  board: PipelineBoard,
  applicationId: string,
  toStatus: ApplicationStatus,
): PipelineBoard {
  let moved: PipelineApplicationPreview | undefined;
  const next: PipelineBoard = { ...board };

  for (const key of APPLICATION_KEYS) {
    const found = board[key].find((a) => a.application_id === applicationId);
    if (found) moved = found;
    next[key] = board[key].filter((a) => a.application_id !== applicationId);
  }
  if (!moved) return board;

  const updated: PipelineApplicationPreview = {
    ...moved,
    status: toStatus,
    status_updated_at: new Date().toISOString(),
    // Recomputed server-side from `ALLOWED_ROLLBACKS`; assuming `true` here
    // would render an Undo that 409s. The refetch on settle restores the
    // real answer a moment later.
    can_roll_back: false,
  };

  next[toStatus] = [...next[toStatus], updated].sort((a, b) => {
    const left = a.score_at_apply;
    const right = b.score_at_apply;
    if (left === right) return a.applied_at.localeCompare(b.applied_at);
    if (left === null) return 1;
    if (right === null) return -1;
    return right - left;
  });

  return next;
}

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

export interface BoardTransitionVariables {
  applicationId: string;
  toStatus: ApplicationStatus;
  closeReason?: CloseReason;
  closeNote?: string;
}

/**
 * The board's own transition — the one a drag fires.
 *
 * Optimistic, unlike `useTransitionApplication` (which backs the detail page,
 * where a card is not moving under the cursor). A drop that snaps back for
 * 300ms while a round trip completes reads as a failed drag, and a recruiter
 * working a column of forty will re-drag it.
 *
 * The rollback is the part that has to be right: `onError` restores the exact
 * snapshot taken in `onMutate`, so a server-refused move (`ALLOWED_TRANSITIONS`
 * disagreeing with `ALLOWED_MOVES`, or a concurrent change from another
 * recruiter on the same job) puts the card back where it was rather than
 * leaving the board describing a transition that did not happen.
 */
export function useBoardTransition(jobId: string) {
  const queryClient = useQueryClient();
  const boardKey = queryKeys.pipeline.board(jobId);

  return useMutation({
    mutationFn: ({ applicationId, toStatus, closeReason, closeNote }: BoardTransitionVariables) =>
      pipelineApi.transition(applicationId, toStatus, { closeReason, closeNote }),

    onMutate: async ({ applicationId, toStatus }) => {
      // Without this, an in-flight board refetch can land *after* the
      // optimistic write and overwrite it with pre-move data.
      await queryClient.cancelQueries({ queryKey: boardKey });
      const previous = queryClient.getQueryData<PipelineBoard>(boardKey);
      if (previous) {
        queryClient.setQueryData(boardKey, moveInBoard(previous, applicationId, toStatus));
      }
      return { previous };
    },

    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(boardKey, context.previous);
    },

    // On settle, not on success: an error has already been rolled back to a
    // snapshot that may itself be stale by now, and the server is the only
    // authority on `can_roll_back` and on the drift figures either way.
    onSettled: (_data, _error, { applicationId }) => {
      void queryClient.invalidateQueries({ queryKey: boardKey });
      void queryClient.invalidateQueries({ queryKey: queryKeys.pipeline.application(applicationId) });
    },
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
