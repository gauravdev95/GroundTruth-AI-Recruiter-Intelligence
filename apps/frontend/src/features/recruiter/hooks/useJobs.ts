import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/lib/queryKeys";

import { jobsApi, type ConfirmRequirementsPayload, type JobCreatePayload } from "../api/jobsApi";

export function useJobs() {
  return useQuery({ queryKey: queryKeys.recruiterJobs.all(), queryFn: jobsApi.list });
}

/** Polls while `status === "extracting"` — the job's own status flips to
 * `awaiting_confirmation` (or reverts to `draft` on failure) once
 * `extract_job_requirements_task` finishes, so polling the job itself is
 * enough; no separate async-job-id tracking needed on this side. */
export function useJob(jobId: string) {
  return useQuery({
    queryKey: queryKeys.recruiterJobs.detail(jobId),
    queryFn: () => jobsApi.get(jobId),
    refetchInterval: (query) => (query.state.data?.job.status === "extracting" ? 2000 : false),
  });
}

export function useCreateJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: jobsApi.create,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.recruiterJobs.all() }),
  });
}

export function useUpdateJob(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: JobCreatePayload) => jobsApi.update(jobId, payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.recruiterJobs.detail(jobId) }),
  });
}

/**
 * Create the draft, then hand it to extraction — the single action behind
 * Screen 1's "Extract requirements" button.
 *
 * One mutation rather than two chained from an `onSuccess`, so the button has
 * one pending state and the page has one error to render. The two calls stay
 * separate endpoints underneath because they are separate job states, and the
 * draft surviving a failed extraction is the point: `error.jobId` carries the
 * id of the job that *was* created, so the caller can route the recruiter to
 * their draft instead of losing everything they typed.
 */
export class ExtractionStartFailed extends Error {
  constructor(
    readonly jobId: string,
    readonly cause: unknown,
  ) {
    super("The job was saved as a draft, but extraction could not be started.");
    this.name = "ExtractionStartFailed";
  }
}

export function useCreateAndExtractJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: JobCreatePayload) => {
      const job = await jobsApi.create(payload);
      try {
        await jobsApi.submit(job.id);
      } catch (error) {
        throw new ExtractionStartFailed(job.id, error);
      }
      return job;
    },
    // Invalidated on settle rather than on success: a job that was created
    // and then failed to start extracting is still a job, and leaving it off
    // the recruiter's list would make it look like nothing had happened.
    onSettled: () => void queryClient.invalidateQueries({ queryKey: queryKeys.recruiterJobs.all() }),
  });
}

export function useSubmitJob(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => jobsApi.submit(jobId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.recruiterJobs.all() }),
  });
}

export function useStartRequirementEdit(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => jobsApi.startRequirementEdit(jobId),
    onSuccess: (detail) => queryClient.setQueryData(queryKeys.recruiterJobs.detail(jobId), detail),
  });
}

export function useConfirmRequirements(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ConfirmRequirementsPayload) => jobsApi.confirm(jobId, payload),
    onSuccess: (detail) => {
      queryClient.setQueryData(queryKeys.recruiterJobs.detail(jobId), detail);
      void queryClient.invalidateQueries({ queryKey: queryKeys.recruiterJobs.all() });
    },
  });
}

export function useCloseJob(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => jobsApi.close(jobId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.recruiterJobs.detail(jobId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.recruiterJobs.all() });
    },
  });
}

export function useReopenJob(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => jobsApi.reopen(jobId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.recruiterJobs.detail(jobId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.recruiterJobs.all() });
    },
  });
}

export function useJobMatches(jobId: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.recruiterJobs.matches(jobId),
    queryFn: () => jobsApi.getMatches(jobId),
    enabled,
  });
}
