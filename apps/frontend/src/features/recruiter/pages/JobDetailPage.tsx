import { ArrowLeft, Loader2 } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { Button, Card, ErrorState, Skeleton, useToast } from "@/components";
import { Surface } from "@/design/Surface";

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

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function daysRemaining(deadline: string | null): string {
  if (!deadline) return "No deadline set";
  const days = Math.ceil((new Date(deadline).getTime() - Date.now()) / 86_400_000);
  if (days < 0) return "Deadline passed";
  if (days === 0) return "Closes today";
  return `${days} day${days === 1 ? "" : "s"} left`;
}

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
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-semibold tracking-tight text-[var(--ink)]">
            {job.title}
          </h1>
          {/* Machine-recorded facts in mono, human-written title in sans. */}
          <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--slate)]">
            <span>{job.job_type.replace(/_/g, " ")}</span>
            <span aria-hidden="true">·</span>
            <span>{job.experience_level}</span>
            <span aria-hidden="true">·</span>
            <span>{job.is_remote ? "Remote" : (job.location ?? "Location not specified")}</span>
            <span aria-hidden="true">·</span>
            <span>{daysRemaining(job.deadline)}</span>
            <span aria-hidden="true">·</span>
            <span className="machine">Created {formatDate(job.created_at)}</span>
            {job.published_at ? (
              <>
                <span aria-hidden="true">·</span>
                <span className="machine">Published {formatDate(job.published_at)}</span>
              </>
            ) : null}
          </p>
        </div>
        <JobStatusBadge status={job.status} />
      </header>

      {job.extraction_error ? (
        <p role="alert" className="rounded-[var(--r-md)] border border-[var(--failed)]/30 bg-[var(--failed)]/10 px-4 py-3 text-sm text-[var(--failed)]">
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
          <Surface className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
            <p className="text-xs leading-relaxed text-[var(--slate)]">
              Saving keeps this a draft. Submitting sends the description to GroundTruth to read
              the requirements out of it.
            </p>
            <Button
              type="button"
              onClick={() =>
                submitJob.mutate(undefined, {
                  onSuccess: () => showToast("Reading your job description…", "info"),
                })
              }
              isLoading={submitJob.isPending}
              disabled={submitJob.isPending}
              className="bg-gt-electric hover:bg-gt-electric/90"
            >
              Submit for extraction
            </Button>
          </Surface>
        </>
      ) : null}

      {job.status === "extracting" ? (
        <Surface className="flex flex-col items-center gap-3 p-10 text-center">
          <Loader2 size={24} className="animate-spin text-gt-electric" aria-hidden="true" />
          <p className="text-sm font-medium text-[var(--ink)]">Reading your job description…</p>
          <p className="text-xs text-[var(--slate)]">Mining must-have skills, desirable skills, and seniority.</p>
        </Surface>
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
          <Card
            title="Requirements"
            subtitle={`${requirements.filter((r) => r.is_required).length} must-have · ${requirements.filter((r) => !r.is_required).length} nice-to-have`}
            actions={
              <div className="flex flex-wrap gap-2">
                <Link
                  to={`/recruiter/jobs/${jobId}/pipeline`}
                  className="inline-flex items-center rounded-[var(--r-sm)] border border-[var(--rule)] bg-[var(--panel)] px-3 py-1.5 text-xs font-semibold text-[var(--ink)] transition hover:border-gt-electric/40"
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
            }
          >
            {requirements.length === 0 ? (
              <p className="text-sm text-[var(--slate)]">No requirements confirmed yet.</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {requirements.map((req) => (
                  <span
                    key={req.id}
                    className={`rounded-full border px-2.5 py-0.5 text-xs ${
                      req.is_required
                        ? "border-[var(--rule)] bg-[var(--panel-raised)] font-medium text-[var(--ink)]"
                        : "border-[var(--rule)] bg-[var(--panel)] text-[var(--slate)]"
                    }`}
                  >
                    {req.skill_name} ({req.min_proficiency}){req.is_required ? "" : " · nice-to-have"}
                  </span>
                ))}
              </div>
            )}
          </Card>

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
        <Surface className="p-6 text-center">
          <p className="text-sm text-[var(--slate)]">This job is closed and no longer matched to candidates.</p>
          <Button
            type="button"
            className="mt-4 bg-gt-electric hover:bg-gt-electric/90"
            onClick={() =>
              reopenJob.mutate(undefined, { onSuccess: () => showToast("Job reopened.", "success") })
            }
            isLoading={reopenJob.isPending}
          >
            Reopen job
          </Button>
        </Surface>
      ) : null}
    </div>
  );
}
