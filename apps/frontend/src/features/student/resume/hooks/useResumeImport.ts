import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/lib/queryKeys";

import {
  resumeApi,
  type ConfirmDraftPayload,
  type JobStatusResponse,
} from "../api/resumeApi";

/**
 * Poll cadence: fast at first, then backing off.
 *
 * Extraction usually finishes in seconds, so the first few checks are quick
 * enough to feel immediate. A job that is retrying through the backoff ladder
 * can take minutes, though, and a fixed 2s interval would spend that time
 * issuing dozens of requests that all say "still running". The interval grows
 * with the number of completed fetches and caps out, so a slow job costs a
 * handful of requests rather than one every two seconds.
 */
const POLL_BASE_MS = 1500;
const POLL_FACTOR = 1.6;
const POLL_MAX_MS = 15_000;

export function jobPollInterval(fetchCount: number): number {
  return Math.min(POLL_MAX_MS, POLL_BASE_MS * POLL_FACTOR ** Math.max(0, fetchCount - 1));
}

function isTerminal(job: JobStatusResponse | undefined): boolean {
  return job?.status === "succeeded" || job?.status === "failed";
}

export function useResumeUploads() {
  return useQuery({
    queryKey: queryKeys.resume.uploads(),
    queryFn: resumeApi.listUploads,
  });
}

export function useUploadResume() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, onProgress }: { file: File; onProgress?: (percent: number) => void }) =>
      resumeApi.upload(file, onProgress),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.resume.uploads() });
      // The setup screen's resume card is derived from the newest upload, so a
      // fresh one makes its server state stale immediately.
      void queryClient.invalidateQueries({ queryKey: queryKeys.studentProfile.setupState() });
    },
  });
}

/**
 * Polls a background job until it reaches a terminal state, then stops.
 *
 * Polling the job row rather than the upload is deliberate: the row carries
 * `attempts` and `is_dead_lettered`, which is what lets the UI say "retrying"
 * instead of showing a failure that the backoff ladder is about to recover from.
 */
export function useJobStatus(jobId: string | null) {
  return useQuery({
    queryKey: queryKeys.resume.job(jobId ?? ""),
    queryFn: () => resumeApi.getJob(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) =>
      isTerminal(query.state.data) ? false : jobPollInterval(query.state.dataUpdateCount),
    // Keep polling while the tab is backgrounded — a student who switches away
    // during extraction should find it finished, not paused.
    refetchIntervalInBackground: true,
  });
}

export function useResumeDraft(uploadId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.resume.draft(uploadId ?? ""),
    queryFn: () => resumeApi.getDraftForUpload(uploadId as string),
    enabled: Boolean(uploadId) && enabled,
  });
}

export function useConfirmDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ draftId, payload }: { draftId: string; payload: ConfirmDraftPayload }) =>
      resumeApi.confirmDraft(draftId, payload),
    onSuccess: (result) => {
      // Confirming writes through the section services, so every profile query
      // is now stale — including the strength meter and the section forms.
      queryClient.setQueryData(queryKeys.studentProfile.completeness(), result.completeness);
      // `studentProfile.all()` is a key prefix, so this also invalidates
      // `setupState()` — the stepper and its percentage re-derive server-side.
      void queryClient.invalidateQueries({ queryKey: queryKeys.studentProfile.all() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.resume.uploads() });
    },
  });
}

export function useDiscardDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (draftId: string) => resumeApi.discardDraft(draftId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.resume.uploads() });
    },
  });
}

export function useDeleteUpload() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (uploadId: string) => resumeApi.deleteUpload(uploadId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.resume.uploads() });
    },
  });
}
