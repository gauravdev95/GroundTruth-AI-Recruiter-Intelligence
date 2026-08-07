import { ArrowLeft, Loader2 } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { Button, ErrorState, Skeleton, useToast } from "@/components";

import { JobForm } from "../components/JobForm";
import { JobStatusBadge } from "../components/JobStatusBadge";
import { MatchedCandidatesList } from "../components/MatchedCandidatesList";
import { RequirementsConfirmForm } from "../components/RequirementsConfirmForm";
import {
  useCloseJob,
  useConfirmRequirements,
  useJob,
  useJobMatches,
  useReopenJob,
  useStartRequirementEdit,
  useSubmitJob,
  useUpdateJob,
} from "../hooks/useJobs";

/**
 * One page for the whole job lifecycle — which section renders is driven
 * entirely by `job.status` (`draft -> extracting -> awaiting_confirmation ->
 * published -> closed`, `recruiter/service.py`'s module docstring).
 */
export function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const { showToast } = useToast();

  const detail = useJob(jobId ?? "");
  const updateJob = useUpdateJob(jobId ?? "");
  const submitJob = useSubmitJob(jobId ?? "");
  const startEdit = useStartRequirementEdit(jobId ?? "");
  const confirmRequirements = useConfirmRequirements(jobId ?? "");
  const closeJob = useCloseJob(jobId ?? "");
  const reopenJob = useReopenJob(jobId ?? "");

  const status = detail.data?.job.status;
  const matches = useJobMatches(jobId ?? "", status === "published");

  if (!jobId) return null;

  const backLink = (
    <Link to="/recruiter/jobs" className="inline-flex items-center gap-1.5 text-sm text-[var(--slate)] hover:text-[var(--ink)]">
      <ArrowLeft size={14} aria-hidden="true" /> Back to jobs
    </Link>
  );

  if (detail.isPending) {
    return (
      <div className="space-y-4">
        {backLink}
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (detail.isError || !detail.data) {
    return (
      <div className="space-y-4">
        {backLink}
        <ErrorState title="Could not load this job" description="Something went wrong." />
      </div>
    );
  }

  const { job, requirements } = detail.data;

  return (
    <div className="space-y-4">
      {backLink}
      <header className="flex items-center justify-between gap-4">
        <h1 className="font-display text-2xl font-semibold text-[var(--ink)]">{job.title}</h1>
        <JobStatusBadge status={job.status} />
      </header>

      {job.extraction_error ? (
        <p role="alert" className="rounded-xl border border-[var(--failed)]/30 bg-[var(--failed)]/10 px-4 py-3 text-sm text-[var(--failed)]">
          The last extraction attempt failed: {job.extraction_error}. Edit the description and submit again.
        </p>
      ) : null}

      {job.status === "draft" ? (
        <>
          <JobForm
            initial={job}
            submitLabel="Save changes"
            isSaving={updateJob.isPending}
            onSubmit={(payload) => updateJob.mutate(payload)}
          />
          <div className="flex justify-end">
            <Button
              type="button"
              onClick={() =>
                submitJob.mutate(undefined, {
                  onSuccess: () => showToast("Reading your job description…", "info"),
                })
              }
              isLoading={submitJob.isPending}
              disabled={submitJob.isPending}
            >
              Submit for extraction
            </Button>
          </div>
        </>
      ) : null}

      {job.status === "extracting" ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-10 text-center">
          <Loader2 size={24} className="animate-spin text-[var(--ink)]" aria-hidden="true" />
          <p className="text-sm font-medium text-[var(--ink)]">Reading your job description…</p>
          <p className="text-xs text-[var(--slate)]">Mining must-have skills, desirable skills, and seniority.</p>
        </div>
      ) : null}

      {job.status === "awaiting_confirmation" ? (
        <RequirementsConfirmForm
          detail={detail.data}
          isSaving={confirmRequirements.isPending}
          onSubmit={(payload) =>
            confirmRequirements.mutate(payload, {
              onSuccess: () => showToast("Job published.", "success"),
            })
          }
        />
      ) : null}

      {job.status === "published" ? (
        <div className="space-y-6">
          <div className="rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold text-[var(--ink)]">Requirements</h2>
              <div className="flex gap-2">
                <Link
                  to={`/recruiter/jobs/${jobId}/pipeline`}
                  className="inline-flex items-center rounded border border-[var(--rule)] px-3 py-1.5 text-xs font-bold text-[var(--ink)] hover:bg-[var(--panel)]"
                >
                  View pipeline
                </Link>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => startEdit.mutate()}
                  isLoading={startEdit.isPending}
                >
                  Edit requirements
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    closeJob.mutate(undefined, { onSuccess: () => showToast("Job closed.", "info") })
                  }
                  isLoading={closeJob.isPending}
                >
                  Close job
                </Button>
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {requirements.map((req) => (
                <span
                  key={req.id}
                  className={`rounded-full border px-2.5 py-0.5 text-xs ${
                    req.is_required ? "border-[var(--rule)]/20 bg-[var(--panel)] text-[var(--ink)]" : "border-[var(--rule)] bg-[var(--panel)] text-[var(--slate)]"
                  }`}
                >
                  {req.skill_name} ({req.min_proficiency}){req.is_required ? "" : " · nice-to-have"}
                </span>
              ))}
            </div>
          </div>

          <div>
            <h2 className="mb-3 font-display text-lg font-semibold text-[var(--ink)]">Matched candidates</h2>
            {matches.isPending ? (
              <Skeleton className="h-40 w-full" />
            ) : matches.isError ? (
              <ErrorState title="Could not load matches" description="Something went wrong." />
            ) : (
              <MatchedCandidatesList candidates={matches.data?.candidates ?? []} />
            )}
          </div>
        </div>
      ) : null}

      {job.status === "closed" ? (
        <div className="rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-6 text-center">
          <p className="text-sm text-[var(--slate)]">This job is closed and no longer matched to candidates.</p>
          <Button
            type="button"
            className="mt-4"
            onClick={() =>
              reopenJob.mutate(undefined, { onSuccess: () => showToast("Job reopened.", "success") })
            }
            isLoading={reopenJob.isPending}
          >
            Reopen job
          </Button>
        </div>
      ) : null}
    </div>
  );
}
