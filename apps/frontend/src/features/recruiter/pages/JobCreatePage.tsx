import { ArrowLeft } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { Badge, useToast } from "@/components";
import { parseApiError } from "@/lib/apiError";

import { JobCreateForm, type JobDraft } from "../components/JobCreateForm";
import { ExtractionStartFailed, useCreateAndExtractJob } from "../hooks/useJobs";
import { saveSeedSkills } from "../lib/seedSkills";

/**
 * Screen 1 — `/recruiter/jobs/new`.
 *
 * "Extract requirements" creates a draft and hands it to the LLM extraction
 * task. It does not publish, and there is no control on this page that does:
 * the only writer of `JobStatus.PUBLISHED` is `confirm_job`, reached from the
 * confirmation screen this page navigates to.
 *
 * A failure to *start* extraction still leaves a saved draft, so that case
 * routes to the job rather than dropping everything the recruiter typed.
 */
export function JobCreatePage() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const createAndExtract = useCreateAndExtractJob();

  const onSubmit = ({ payload, seedSkills }: JobDraft) => {
    createAndExtract.mutate(payload, {
      onSuccess: (job) => {
        saveSeedSkills(job.id, seedSkills);
        navigate(`/recruiter/jobs/${job.id}/confirm`);
      },
      onError: (error) => {
        if (error instanceof ExtractionStartFailed) {
          saveSeedSkills(error.jobId, seedSkills);
          showToast(error.message, "error");
          navigate(`/recruiter/jobs/${error.jobId}`);
          return;
        }
        showToast(parseApiError(error)?.message ?? "Could not create this job.", "error");
      },
    });
  };

  return (
    <div className="mx-auto w-full max-w-[720px] space-y-5">
      <Link
        to="/recruiter/jobs"
        className="inline-flex items-center gap-1.5 text-sm text-[var(--slate)] transition hover:text-[var(--ink)]"
      >
        <ArrowLeft size={14} aria-hidden="true" /> Job postings
      </Link>

      <header>
        {/* The flow is two screens, and a recruiter mid-flow should always
            know which one they are on and what the next one asks of them. */}
        <ol className="mb-3 flex flex-wrap items-center gap-2 text-xs" aria-label="Posting steps">
          <li>
            <Badge variant="accent">Step 1 of 2 — Describe the role</Badge>
          </li>
          <li aria-hidden="true" className="text-[var(--muted)]">→</li>
          <li className="text-[var(--slate)]">Step 2 — Review extracted requirements &amp; publish</li>
        </ol>
        <h1 className="font-display text-2xl font-semibold tracking-tight text-[var(--ink)]">New job posting</h1>
        <p className="mt-1 text-sm text-[var(--slate)]">
          Describe the role. GroundTruth reads the requirements out of it, and you confirm them
          before anything is published.
        </p>
      </header>

      <JobCreateForm isSaving={createAndExtract.isPending} onSubmit={onSubmit} />
    </div>
  );
}
