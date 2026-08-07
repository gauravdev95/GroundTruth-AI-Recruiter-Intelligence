import { AlertTriangle, ArrowLeft, Loader2, PencilLine, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ErrorState, Skeleton } from "@/components";

import { getProfileErrorMessage } from "../../lib/getProfileErrorMessage";
import { DraftReview } from "../../resume/components/DraftReview";
import { useJobStatus, useResumeDraft } from "../../resume/hooks/useResumeImport";
import { SetupStepper, SetupStepperSkeleton } from "../components/SetupStepper";
import { useInvalidateSetupState, useSetupState } from "../hooks/useSetupState";
import { useSetupUpload } from "../hooks/useSetupUpload";

/**
 * Give up waiting after this long.
 *
 * A job that has neither succeeded nor failed by now is stuck somewhere the UI
 * cannot see — a dead worker, a lost message. Polling forever would leave a
 * student watching a spinner with no way out, so this converts silence into a
 * stated outcome with both recovery paths attached.
 */
const PARSE_TIMEOUT_MS = 3 * 60 * 1000;

/** Every failure state offers the same two exits. The manual path must stay
 * reachable from all of them — a student whose resume will not parse still has
 * a profile to build. */
function FailureActions({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="mt-4 flex flex-wrap items-center gap-3">
      <button
        type="button"
        onClick={onRetry}
        className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-[var(--violet)] to-[var(--blue)] px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-[var(--shadow-panel)] transition   focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--violet)]"
      >
        <RotateCcw size={15} aria-hidden="true" />
        Try again
      </button>
      <Link
        to="/student/profile/setup/manual"
        className="inline-flex items-center gap-2 rounded-xl border-2 border-[var(--flagged)]/60 bg-[var(--panel)] px-4 py-2.5 text-sm font-semibold text-[var(--flagged)] transition hover:bg-[var(--flagged)]/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--flagged)]"
      >
        <PencilLine size={15} aria-hidden="true" />
        Fill manually instead
      </Link>
    </div>
  );
}

/**
 * The resume path: transfer → analyze → review → confirm.
 *
 * State comes from two places that agree by construction. The in-memory upload
 * context covers the transfer, which only exists in this tab; everything after
 * the 202 is read from `setup-state` and the job row, so a refresh or a return
 * from another device lands in the right place — `parsing` shows the analyzing
 * state, `parsed` with an unconfirmed draft shows the review.
 */
export function SetupResumePage() {
  const navigate = useNavigate();
  const setupState = useSetupState();
  const invalidateSetupState = useInvalidateSetupState();
  const upload = useSetupUpload();
  const [hasTimedOut, setTimedOut] = useState(false);

  const serverResume = setupState.data?.resume;

  // Prefer the ids from this tab's own 202 — they are known before
  // `setup-state` has refetched, so polling starts immediately rather than
  // after a round trip.
  const uploadId = upload.uploadId ?? serverResume?.upload_id ?? null;
  const jobId = upload.jobId ?? serverResume?.async_job_id ?? null;

  const job = useJobStatus(jobId);

  const isTransferring = upload.isUploading || upload.progress !== null;
  const jobSucceeded = job.data?.status === "succeeded";
  const jobFailed = job.data?.status === "failed";
  const serverFailed = serverResume?.status === "failed";
  const serverParsed = serverResume?.status === "parsed";

  const draft = useResumeDraft(uploadId, jobSucceeded || serverParsed);

  const isAnalyzing =
    !isTransferring &&
    Boolean(uploadId) &&
    !jobSucceeded &&
    !jobFailed &&
    !serverFailed &&
    !serverParsed &&
    !hasTimedOut;

  // A wall-clock deadline rather than a poll count: the poll interval backs
  // off, so counting attempts would make the timeout depend on the backoff
  // curve instead of on how long the student has actually been waiting.
  useEffect(() => {
    if (!isAnalyzing) return;
    const timer = window.setTimeout(() => setTimedOut(true), PARSE_TIMEOUT_MS);
    return () => window.clearTimeout(timer);
  }, [isAnalyzing]);

  function retry() {
    setTimedOut(false);
    upload.reset();
    void invalidateSetupState();
    navigate("/student/profile/setup");
  }

  function finishReview() {
    upload.reset();
    void invalidateSetupState();
    navigate("/student/profile/setup/manual");
  }

  const failureReason =
    job.data?.error ?? serverResume?.error ?? "Something went wrong reading the file.";

  return (
    <div className="space-y-6">
      {setupState.isPending || !setupState.data ? (
        <SetupStepperSkeleton />
      ) : (
        <SetupStepper
          steps={setupState.data.steps}
          currentStepIndex={setupState.data.current_step_index}
          completionPercentage={setupState.data.completion_percentage}
          onSelect={() => navigate("/student/profile/setup/manual")}
        />
      )}

      <div className="flex items-center justify-between gap-3">
        <Link
          to="/student/profile/setup"
          className="inline-flex items-center gap-1.5 rounded-lg text-sm font-medium text-[var(--slate)] transition hover:text-[var(--violet)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--violet)]"
        >
          <ArrowLeft size={15} aria-hidden="true" />
          Back to setup
        </Link>
        <Link
          to="/student/profile/setup/manual"
          className="rounded-lg text-sm font-medium text-[var(--flagged)] underline-offset-4 transition hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--flagged)]"
        >
          Switch to manual entry
        </Link>
      </div>

      {isTransferring ? (
        <section
          aria-label="Uploading your resume"
          className="rounded-2xl border border-[var(--violet)]/25 bg-[var(--panel)] p-6 shadow-sm shadow-[var(--shadow-panel)]"
        >
          <p className="text-sm font-semibold text-[var(--ink)]">
            Uploading {upload.fileName ?? "your resume"}…
          </p>
          <div
            className="mt-3 h-2 w-full overflow-hidden rounded-full bg-[var(--violet)]/15"
            role="progressbar"
            aria-valuenow={upload.progress ?? 0}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Upload progress"
          >
            <div
              className="h-full rounded-full bg-gradient-to-r from-[var(--violet)] to-[var(--blue)] transition-[width] duration-200"
              style={{ width: `${upload.progress ?? 0}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-[var(--slate)]">{upload.progress ?? 0}% transferred</p>
        </section>
      ) : null}

      {upload.error && !isTransferring ? (
        <ErrorState
          title="We couldn't upload that file"
          description={getProfileErrorMessage(upload.error, "Could not upload that file.")}
          action={<FailureActions onRetry={retry} />}
        />
      ) : null}

      {isAnalyzing ? (
        <section
          role="status"
          aria-live="polite"
          className="rounded-2xl border border-[var(--violet)]/25 bg-[var(--panel)] p-6 shadow-sm shadow-[var(--shadow-panel)]"
        >
          <div className="flex items-center gap-3">
            <Loader2 size={20} className="animate-spin text-[var(--violet)]" aria-hidden="true" />
            <div>
              <p className="text-sm font-semibold text-[var(--ink)]">Analyzing your resume…</p>
              <p className="mt-0.5 text-xs text-[var(--slate)]">
                {job.data && job.data.attempts > 1
                  ? `Retrying (attempt ${job.data.attempts}). This can take a moment.`
                  : "This usually takes about 30 seconds. You can leave this page open."}
              </p>
            </div>
          </div>
          <div className="mt-5 space-y-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-3/5" />
          </div>
        </section>
      ) : null}

      {hasTimedOut && !jobSucceeded && !serverParsed ? (
        <section className="rounded-2xl border border-[var(--flagged)]/30 bg-[var(--flagged)]/10 p-6">
          <div className="flex items-start gap-3">
            <AlertTriangle size={20} className="mt-0.5 shrink-0 text-[var(--flagged)]" aria-hidden="true" />
            <div>
              <h2 className="text-sm font-semibold text-[var(--ink)]">This is taking longer than expected</h2>
              <p className="mt-1 text-sm text-[var(--slate)]">
                We haven&apos;t heard back about your resume in a few minutes. Nothing was saved to
                your profile.
              </p>
            </div>
          </div>
          <FailureActions onRetry={retry} />
        </section>
      ) : null}

      {(jobFailed || serverFailed) && !hasTimedOut ? (
        <section className="rounded-2xl border border-[var(--failed)]/30 bg-[var(--failed)]/10 p-6">
          <div className="flex items-start gap-3">
            <AlertTriangle size={20} className="mt-0.5 shrink-0 text-[var(--failed)]" aria-hidden="true" />
            <div>
              <h2 className="text-sm font-semibold text-[var(--ink)]">We couldn&apos;t read that resume</h2>
              {/* The worker prefixes its message with the exception class; the
                  student only needs the sentence after it. */}
              <p className="mt-1 text-sm text-[var(--slate)]">
                {failureReason.includes(":")
                  ? failureReason.slice(failureReason.indexOf(":") + 1).trim()
                  : failureReason}
              </p>
            </div>
          </div>
          <FailureActions onRetry={retry} />
        </section>
      ) : null}

      {(jobSucceeded || serverParsed) && draft.isPending ? (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full rounded-2xl" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      ) : null}

      {(jobSucceeded || serverParsed) && draft.isError ? (
        <ErrorState
          title="Couldn't load the extracted data"
          description="The resume was read, but we couldn't fetch the result."
          action={<FailureActions onRetry={retry} />}
        />
      ) : null}

      {draft.data && draft.data.draft.status === "pending_review" ? (
        <DraftReview detail={draft.data} onDone={finishReview} />
      ) : null}

      {draft.data && draft.data.draft.status !== "pending_review" ? (
        <section className="rounded-2xl border border-[var(--violet)]/25 bg-[var(--panel)] p-6 text-sm shadow-sm shadow-[var(--shadow-panel)]">
          <p className="font-semibold text-[var(--ink)]">
            {draft.data.draft.status === "confirmed"
              ? "This resume has been imported."
              : "This draft was discarded."}
          </p>
          <p className="mt-1 text-[var(--slate)]">
            Carry on filling in the remaining sections, or upload a different resume.
          </p>
          <FailureActions onRetry={retry} />
        </section>
      ) : null}
    </div>
  );
}
