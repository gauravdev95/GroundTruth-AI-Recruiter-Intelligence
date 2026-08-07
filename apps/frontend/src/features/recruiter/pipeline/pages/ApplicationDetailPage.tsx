import { ArrowLeft, Undo2 } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { Button, ErrorState, Skeleton, useToast } from "@/components";
import { EvidenceCard } from "@/features/recruiter/evidence/components/EvidenceCard";
import { MessageThread } from "@/features/messaging";
import { NotesPanel } from "@/features/recruiter/notes/components/NotesPanel";
import { parseApiError } from "@/lib/apiError";

import { ApplicationStatusBadge } from "../../../student/applications/components/ApplicationStatusBadge";
import type { ApplicationStatus } from "../api/pipelineApi";
import { ScoreWithDrift } from "../components/ScoreWithDrift";
import { useRecruiterApplication, useRollbackApplication, useTransitionApplication } from "../hooks/usePipeline";

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

/** The recruiter's per-candidate view of one application: evidence card,
 * transition controls, private notes, and messaging — everything B2/B3 asks
 * for, in one place, since they're all scoped to the same `Application`. */
export function ApplicationDetailPage() {
  const { applicationId } = useParams<{ applicationId: string }>();
  const detail = useRecruiterApplication(applicationId ?? "");
  const transition = useTransitionApplication(detail.data?.application.job_posting_id ?? "");
  const rollback = useRollbackApplication(detail.data?.application.job_posting_id ?? "");
  const { showToast } = useToast();

  if (!applicationId) return null;

  const backLink = (
    <Link to="/recruiter/jobs" className="inline-flex items-center gap-1.5 text-sm text-[var(--slate)] hover:text-[var(--ink)]">
      <ArrowLeft size={14} aria-hidden="true" /> Back to jobs
    </Link>
  );

  if (detail.isPending) {
    return (
      <div className="space-y-4">
        {backLink}
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (detail.isError || !detail.data) {
    return (
      <div className="space-y-4">
        {backLink}
        <ErrorState title="Could not load this application" description="Something went wrong." />
      </div>
    );
  }

  const {
    application,
    job_title,
    company_name,
    candidate_profile_id,
    candidate_headline,
    drift,
    can_roll_back,
    rollback_target,
  } = detail.data;
  const nextSteps = NEXT_STEPS[application.status] ?? [];

  return (
    <div className="space-y-6">
      {backLink}

      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-semibold text-[var(--ink)]">{candidate_headline ?? "Candidate"}</h1>
          <p className="text-sm text-[var(--slate)]">
            {job_title} · {company_name}
          </p>
          {/* Both scores, on the surface where the shortlisting decision is
              actually taken. `size="lg"` because here the score is a headline
              figure rather than one line of a dense card. */}
          <div className="mt-2">
            <ScoreWithDrift
              scoreAtApply={drift.score_at_apply}
              liveScore={drift.live_score}
              driftPoints={drift.points}
              direction={drift.direction}
              isMeaningful={drift.is_meaningful}
              size="lg"
            />
            <p className="mt-0.5 text-xs text-[var(--muted)]">
              Score at time of applying{drift.direction === "unknown" ? "" : ", and drift since"}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ApplicationStatusBadge status={application.status} />
          {nextSteps.map((step) => (
            <Button
              key={step.to}
              type="button"
              size="sm"
              variant={step.to === "rejected" ? "ghost" : "secondary"}
              isLoading={transition.isPending}
              onClick={() =>
                transition.mutate(
                  { applicationId, toStatus: step.to },
                  {
                    onError: (error) =>
                      showToast(parseApiError(error)?.message ?? "Could not update this application.", "error"),
                  },
                )
              }
            >
              {step.label}
            </Button>
          ))}
          {/* Unlike the board, this page has the room to name the exact stage
              the undo restores — the server resolved it (from `audit_log`,
              for a rejected application), so the label is never a guess. */}
          {can_roll_back ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              isLoading={rollback.isPending}
              onClick={() =>
                rollback.mutate(applicationId, {
                  onError: (error) =>
                    showToast(parseApiError(error)?.message ?? "Could not undo this move.", "error"),
                })
              }
            >
              <Undo2 size={13} aria-hidden="true" />
              Undo{rollback_target ? ` to ${rollback_target.replace(/_/g, " ")}` : ""}
            </Button>
          ) : null}
        </div>
      </header>

      {application.cover_note ? (
        <div className="rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-5">
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">Cover note</p>
          <p className="whitespace-pre-wrap text-sm text-[var(--ink)]">{application.cover_note}</p>
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <EvidenceCard candidateProfileId={candidate_profile_id} />

        <div className="space-y-6">
          <NotesPanel applicationId={applicationId} />
          <div>
            <p className="mb-2 text-sm font-semibold text-[var(--ink)]">Messages</p>
            <MessageThread rolePrefix="recruiter" applicationId={applicationId} />
          </div>
        </div>
      </div>
    </div>
  );
}
