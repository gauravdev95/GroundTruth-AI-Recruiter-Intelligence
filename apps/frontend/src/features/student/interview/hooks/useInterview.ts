import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/lib/queryKeys";

import { interviewApi } from "../api/interviewApi";

/** 404 ("no attempt yet") is the common, expected first response for a
 * freshly-verified repository — never retried, and callers branch on
 * `isError` to render the "start interview" screen rather than an error. */
export function useLatestInterview(projectId: string) {
  return useQuery({
    queryKey: queryKeys.interview.latestForProject(projectId),
    queryFn: () => interviewApi.latestForProject(projectId),
    retry: false,
  });
}

export function useStartInterview() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: interviewApi.start,
    onSuccess: (interview) => {
      queryClient.setQueryData(queryKeys.interview.latestForProject(interview.project_id), interview);
      queryClient.setQueryData(queryKeys.interview.state(interview.id), {
        interview,
        current_question: null,
        answered_count: 0,
      });
    },
  });
}

const POLLING_STATUSES = new Set(["pending", "evaluating"]);

/** Polls while question generation / evaluation is running in the
 * background (`jobs/tasks/interview.py`), same shape as
 * `resume/hooks/useResumeImport.ts::useJobStatus`. Stops polling once the
 * interview reaches a terminal-for-now state (`in_progress`, `completed`,
 * `failed`) — `in_progress` still needs fetching (for the current question)
 * but not polling, since only an explicit answer submission changes it. */
export function useInterviewState(interviewId: string | null) {
  return useQuery({
    queryKey: queryKeys.interview.state(interviewId ?? ""),
    queryFn: () => interviewApi.getState(interviewId as string),
    enabled: interviewId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.interview.status;
      return status && POLLING_STATUSES.has(status) ? 2500 : false;
    },
    refetchIntervalInBackground: true,
  });
}

export function useSubmitAnswer(interviewId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: { questionId: string; transcript: string; timeTakenSeconds: number }) =>
      interviewApi.submitAnswer(interviewId, payload.questionId, {
        transcript: payload.transcript,
        time_taken_seconds: payload.timeTakenSeconds,
      }),
    onSuccess: (state) => {
      queryClient.setQueryData(queryKeys.interview.state(interviewId), state);
    },
  });
}

export function useEvidenceReport(interviewId: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.interview.report(interviewId),
    queryFn: () => interviewApi.getReport(interviewId),
    enabled,
  });
}
