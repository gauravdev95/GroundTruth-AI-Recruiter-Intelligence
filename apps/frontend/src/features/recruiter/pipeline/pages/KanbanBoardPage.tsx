import { ArrowLeft, Undo2 } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { Badge, ErrorState, Skeleton, useToast } from "@/components";
import { parseApiError } from "@/lib/apiError";

import type { ApplicationStatus, PipelineApplicationPreview, PipelineCandidatePreview } from "../api/pipelineApi";
import { ScoreWithDrift } from "../components/ScoreWithDrift";
import { useJob } from "../../hooks/useJobs";
import { usePipelineBoard, useRollbackApplication, useTransitionApplication } from "../hooks/usePipeline";

/** Mirrors `pipeline/models.py::ALLOWED_TRANSITIONS` client-side, purely to
 * decide which action buttons to render — the server is still the
 * authority and rejects anything else (`transition_status`), so this is a
 * UX shortcut, not a trust boundary. */
const NEXT_STEPS: Record<string, { to: ApplicationStatus; label: string }[]> = {
  applied: [
    { to: "shortlisted", label: "Shortlist" },
    { to: "rejected", label: "Reject" },
  ],
  shortlisted: [
    { to: "interview_scheduled", label: "Schedule interview" },
    { to: "rejected", label: "Reject" },
  ],
  interview_scheduled: [
    { to: "hired", label: "Hire" },
    { to: "rejected", label: "Reject" },
  ],
  hired: [],
  rejected: [],
};

const COLUMNS: { key: keyof import("../api/pipelineApi").PipelineBoard; title: string }[] = [
  { key: "matched", title: "Matched" },
  { key: "applied", title: "Applied" },
  { key: "shortlisted", title: "Shortlisted" },
  { key: "interview_scheduled", title: "Interview scheduled" },
  { key: "hired", title: "Hired" },
  { key: "rejected", title: "Rejected" },
];

function MatchedCard({ candidate }: { candidate: PipelineCandidatePreview }) {
  return (
    <div className="rounded-xl border border-rule bg-white p-3">
      <p className="text-sm font-medium text-ink">{candidate.headline ?? "Candidate"}</p>
      <p className="mt-1 text-xs text-slate-400">Match score {candidate.match_score.toFixed(0)}</p>
    </div>
  );
}

function ApplicationCard({
  application,
  jobId,
  onTransition,
  onRollback,
  isBusy,
}: {
  application: PipelineApplicationPreview;
  jobId: string;
  onTransition: (applicationId: string, toStatus: ApplicationStatus) => void;
  onRollback: (applicationId: string) => void;
  isBusy: boolean;
}) {
  const nextSteps = NEXT_STEPS[application.status] ?? [];

  return (
    <div className="rounded-xl border border-rule bg-white p-3">
      <div className="flex items-start justify-between gap-2">
        <Link
          to={`/recruiter/applications/${application.application_id}`}
          state={{ jobId }}
          className="min-w-0 text-sm font-medium text-ink hover:underline"
        >
          {application.headline ?? "Candidate"}
        </Link>
      </div>

      <div className="mt-1.5">
        <ScoreWithDrift
          scoreAtApply={application.score_at_apply}
          liveScore={application.match_score}
          driftPoints={application.drift_points}
          direction={application.drift_direction}
          isMeaningful={application.drift_is_meaningful}
        />
      </div>

      <p className="mt-1 text-xs text-slate-400">
        Updated {new Date(application.status_updated_at).toLocaleDateString()}
      </p>

      {nextSteps.length > 0 || application.can_roll_back ? (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {nextSteps.map((step) => (
            <button
              key={step.to}
              type="button"
              disabled={isBusy}
              onClick={() => onTransition(application.application_id, step.to)}
              className="rounded-full border border-ink/20 bg-ink/5 px-2.5 py-1 text-xs font-medium text-ink transition hover:bg-ink/10 disabled:opacity-50"
            >
              {step.label}
            </button>
          ))}
          {/* Offered only where the server says a rollback is legal
              (`can_roll_back`) — the target itself is server-derived, so the
              label stays generic rather than naming a stage this card cannot
              know for a rejected application. */}
          {application.can_roll_back ? (
            <button
              type="button"
              disabled={isBusy}
              onClick={() => onRollback(application.application_id)}
              className="inline-flex items-center gap-1 rounded-full border border-rule px-2.5 py-1 text-xs font-medium text-slate-500 transition hover:border-ink hover:text-ink disabled:opacity-50"
            >
              <Undo2 size={11} aria-hidden="true" /> Undo
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function KanbanBoardPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const job = useJob(jobId ?? "");
  const board = usePipelineBoard(jobId ?? "");
  const transition = useTransitionApplication(jobId ?? "");
  const rollback = useRollbackApplication(jobId ?? "");
  const { showToast } = useToast();

  if (!jobId) return null;

  const backLink = (
    <Link to={`/recruiter/jobs/${jobId}`} className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-ink">
      <ArrowLeft size={14} aria-hidden="true" /> Back to job
    </Link>
  );

  if (board.isPending) {
    return (
      <div className="space-y-4">
        {backLink}
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (board.isError || !board.data) {
    return (
      <div className="space-y-4">
        {backLink}
        <ErrorState title="Could not load the pipeline" description="Something went wrong." />
      </div>
    );
  }

  const handleTransition = (applicationId: string, toStatus: ApplicationStatus) => {
    transition.mutate(
      { applicationId, toStatus },
      {
        onError: (error) =>
          // Illegal-transition errors are surfaced verbatim, not swallowed —
          // the backend's message already names the reason
          // (`ALLOWED_TRANSITIONS`), so this is the message a recruiter needs.
          showToast(parseApiError(error)?.message ?? "Could not update this application.", "error"),
      },
    );
  };

  const handleRollback = (applicationId: string) => {
    rollback.mutate(applicationId, {
      // Same treatment as an illegal forward transition: the server's message
      // names which status refused the rollback (`ALLOWED_ROLLBACKS`).
      onError: (error) =>
        showToast(parseApiError(error)?.message ?? "Could not undo this move.", "error"),
      onSuccess: (application) =>
        showToast(`Moved back to ${application.status.replace(/_/g, " ")}.`, "success"),
    });
  };

  return (
    <div className="space-y-4">
      {backLink}
      <header>
        <h1 className="font-display text-2xl font-semibold text-ink">{job.data?.job.title ?? "Pipeline"}</h1>
        <p className="mt-1 text-sm text-slate-500">
          Ranked within each stage by the score at the time of applying, strongest first. The smaller
          figure is how far the live score has moved since — highlighted once it passes 5 points.
        </p>
      </header>

      <div className="flex gap-4 overflow-x-auto pb-2">
        {COLUMNS.map((column) => {
          const items = board.data[column.key];
          return (
            <div key={column.key} className="w-72 shrink-0 rounded-2xl border border-rule bg-panel p-3">
              <div className="mb-3 flex items-center justify-between px-1">
                <h2 className="text-sm font-semibold text-ink">{column.title}</h2>
                <Badge variant="neutral">{items.length}</Badge>
              </div>
              <div className="space-y-2">
                {items.length === 0 ? (
                  <p className="rounded-xl border border-dashed border-rule px-3 py-6 text-center text-xs text-slate-400">
                    Empty
                  </p>
                ) : column.key === "matched" ? (
                  (items as PipelineCandidatePreview[]).map((candidate) => (
                    <MatchedCard key={candidate.candidate_profile_id} candidate={candidate} />
                  ))
                ) : (
                  (items as PipelineApplicationPreview[]).map((application) => (
                    <ApplicationCard
                      key={application.application_id}
                      application={application}
                      jobId={jobId}
                      onTransition={handleTransition}
                      onRollback={handleRollback}
                      isBusy={transition.isPending || rollback.isPending}
                    />
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
