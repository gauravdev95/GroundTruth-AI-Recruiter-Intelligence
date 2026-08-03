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
