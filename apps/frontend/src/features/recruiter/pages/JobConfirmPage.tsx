import { AlertTriangle, ArrowLeft, Loader2 } from "lucide-react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";

import { Button, ErrorState, Skeleton, useToast } from "@/components";
import { parseApiError } from "@/lib/apiError";

import { ExtractionConfirmPanel } from "../components/ExtractionConfirmPanel";
import { MarkdownLite } from "../components/MarkdownLite";
import { useConfirmRequirements, useJob, useStartRequirementEdit } from "../hooks/useJobs";
import { clearSeedSkills, readSeedSkills } from "../lib/seedSkills";

/**
 * Screen 2 — `/recruiter/jobs/:jobId/confirm`. The human-in-the-loop gate.
 *
 * **This screen is the only way a job gets published.** Not by convention:
 * `POST /recruiter/jobs/{id}/confirm` is the sole writer of
 * `JobStatus.PUBLISHED` (`domains/recruiter/service.py::confirm_job`), and it
 * is only reachable from `AWAITING_CONFIRMATION`. There is no shortcut to
 * add, because there is no second endpoint to point it at.
 *
 * The layout is two columns for one reason: the check being asked for is a
 * comparison. "Does this extracted list match what I wrote?" is unanswerable
 * on a screen that shows only one of the two, and a recruiter who has to
 * navigate back to read their own description will stop checking by the third
 * job.
 */
export function JobConfirmPage() {
  const { jobId = "" } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const detail = useJob(jobId);
  const confirmRequirements = useConfirmRequirements(jobId);
  const startEdit = useStartRequirementEdit(jobId);

  const backLink = (
    <Link
      to={`/recruiter/jobs/${jobId}`}
      className="inline-flex items-center gap-1.5 text-sm text-[var(--slate)] transition hover:text-[var(--ink)]"
    >
      <ArrowLeft size={14} aria-hidden="true" /> Job
    </Link>
  );

  if (!jobId) return <Navigate to="/recruiter/jobs" replace />;

  if (detail.isPending) {
    return (
      <div className="space-y-4">
        {backLink}
        <Skeleton className="h-[32rem] w-full" />
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

  const { job } = detail.data;

  // `useJob` polls every 2s while the status is `extracting`, so this state
  // resolves itself without the recruiter doing anything.
  if (job.status === "extracting") {
    return (
      <div className="mx-auto max-w-lg space-y-4 py-16 text-center">
        <Loader2 size={22} className="mx-auto animate-spin text-gt-electric" aria-hidden="true" />
        <p className="text-sm font-medium text-[var(--ink)]">Reading your job description…</p>
        <p className="text-xs text-[var(--slate)]">
          Mining must-have skills, nice-to-haves and seniority. This usually takes a few seconds.
        </p>
      </div>
    );
  }

  // A job that failed extraction reverts to `draft` with `extraction_error`
  // set. There is nothing to confirm, so this sends the recruiter to the
  // place where the failure is explained and the description can be fixed.
  if (job.status === "draft") {
    return <Navigate to={`/recruiter/jobs/${jobId}`} replace />;
  }

  if (job.status === "closed") {
    return <Navigate to={`/recruiter/jobs/${jobId}`} replace />;
  }

  // Already published and not being re-edited — the confirmation has happened.
  // `Edit requirements` on the job page flips it back to
  // `awaiting_confirmation` and returns here.
  if (job.status === "published") {
    return (
      <div className="mx-auto max-w-lg space-y-4 py-16 text-center">
        <p className="text-sm font-medium text-[var(--ink)]">This job is already published.</p>
        <p className="text-xs text-[var(--slate)]">
          Reopening the requirements unpublishes it until you confirm again, so candidates never see
          a half-edited posting.
        </p>
        <div className="flex justify-center gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={() => navigate(`/recruiter/jobs/${jobId}/pipeline`)}>
            Open pipeline
          </Button>
          <Button
            type="button"
            isLoading={startEdit.isPending}
            className="bg-gt-electric hover:bg-gt-electric/90"
            onClick={() =>
              startEdit.mutate(undefined, {
                onError: (error) =>
                  showToast(parseApiError(error)?.message ?? "Could not reopen the requirements.", "error"),
              })
            }
          >
            Edit requirements
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {backLink}

      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-[var(--ink)]">{job.title}</h1>
        <p className="text-sm text-[var(--slate)]">Review extracted requirements</p>
      </header>

      <div
        role="alert"
        className="flex items-start gap-2.5 rounded-lg bg-[var(--flagged)]/10 px-4 py-3 text-sm leading-relaxed text-[var(--flagged)]"
      >
        <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
        <p>
          <span className="font-semibold">Review before publishing.</span> This confirmation
          determines how candidates are matched — edit anything that looks wrong.
        </p>
      </div>

      {/* Stacks below `lg`. Side-by-side is the whole point of the screen, and
          two 340px columns on a tablet in portrait is worse than one readable
          one — so the breakpoint is where two columns are genuinely usable,
          not where they first fit. */}
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-[var(--rule)] bg-[var(--panel)]">
          <div className="border-b border-[var(--rule)] px-5 py-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--slate)]">
              Your description
            </h2>
          </div>
          {/* Capped and scrolled rather than allowed to run the page long:
              the right column must stay reachable without scrolling past a
              2,000-word posting. */}
          <div className="max-h-[36rem] overflow-y-auto px-5 py-4 text-sm leading-relaxed text-[var(--slate)]">
            <MarkdownLite text={job.description} />
          </div>
        </section>

        <section className="rounded-xl border border-[var(--rule)] bg-[var(--panel)]">
          <div className="border-b border-[var(--rule)] px-5 py-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--slate)]">
              Extracted requirements
            </h2>
          </div>
          <ExtractionConfirmPanel
            detail={detail.data}
            seedSkills={readSeedSkills(jobId)}
            isSaving={confirmRequirements.isPending}
            onBack={() => navigate(`/recruiter/jobs/${jobId}`)}
            onConfirm={(payload) =>
              confirmRequirements.mutate(payload, {
                onSuccess: () => {
                  clearSeedSkills(jobId);
                  showToast("Job published. Matching has started.", "success");
                  navigate(`/recruiter/jobs/${jobId}/pipeline`);
                },
                onError: (error) =>
                  showToast(parseApiError(error)?.message ?? "Could not publish this job.", "error"),
              })
            }
          />
        </section>
      </div>
    </div>
  );
}
