import { AlertTriangle, RotateCcw } from "lucide-react";

import { useToast } from "@/components";
import { parseApiError } from "@/lib/apiError";

import { useDeadLetteredJobs, useRetryAsyncJob } from "../hooks/useAsyncJobs";

const JOB_TYPE_LABELS: Record<string, string> = {
  extract_resume: "Resume import",
  generate_interview_questions: "Interview question generation",
  evaluate_interview: "Interview evaluation",
  extract_job_requirements: "Job requirement extraction",
  verify_github_account: "GitHub account verification",
  verify_coding_platform_account: "Coding platform verification",
  verify_repository: "Repository verification",
  verify_certificate: "Certificate verification",
  verify_experience: "Experience verification",
  embed_and_match_job: "Job matching",
  embed_and_match_candidate: "Profile matching",
};

/** Background work that exhausted its retries never disappears silently —
 * it surfaces here with a one-click retry, on both dashboards, until the
 * caller acts on it (see `jobs/tasks/dead_letter.py`). Renders nothing when
 * there's nothing dead-lettered; this is an alert surface, not a list page,
 * so "no failures" doesn't need an empty state of its own. */
export function DeadLetterBanner() {
  const deadLettered = useDeadLetteredJobs();
  const retry = useRetryAsyncJob();
  const { showToast } = useToast();

  if (deadLettered.data.length === 0) return null;

  return (
    <div className="rounded-2xl border border-[var(--flagged)]/30 bg-[var(--flagged)]/10 p-4">
      <div className="mb-2 flex items-center gap-2">
        <AlertTriangle size={16} className="text-[var(--flagged)]" aria-hidden="true" />
        <p className="text-sm font-semibold text-[var(--flagged)]">
          {deadLettered.data.length} background {deadLettered.data.length === 1 ? "task" : "tasks"} need attention
        </p>
      </div>
      <ul className="space-y-2">
        {deadLettered.data.map((job) => (
          <li
            key={job.id}
            className="flex items-center justify-between gap-3 rounded-xl border border-[var(--flagged)]/30 bg-[var(--panel)] px-3 py-2"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-[var(--ink)]">{JOB_TYPE_LABELS[job.job_type] ?? job.job_type}</p>
              <p className="truncate text-xs text-[var(--slate)]">{job.error ?? "Failed after repeated attempts."}</p>
            </div>
            <button
              type="button"
              onClick={() =>
                retry.mutate(job.id, {
                  onSuccess: () => showToast("Retrying…", "info"),
                  onError: (error) => showToast(parseApiError(error)?.message ?? "Could not retry this task.", "error"),
                })
              }
              disabled={retry.isPending}
              className="flex shrink-0 items-center gap-1.5 rounded-full border border-[var(--flagged)]/40 bg-[var(--flagged)]/15 px-3 py-1.5 text-xs font-semibold text-[var(--flagged)] transition hover:bg-[var(--flagged)]/20 disabled:opacity-60"
            >
              <RotateCcw size={12} aria-hidden="true" />
              Retry
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
