import { ArrowLeft, Briefcase } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { Badge, ErrorState, Skeleton } from "@/components";
import { Surface } from "@/design/Surface";
import { MessageThread } from "@/features/messaging";
import { MatchScoreRing } from "@/features/student/matches/components/MatchScoreRing";

import { ApplicationStageTimeline } from "../components/ApplicationStageTimeline";
import { ApplicationStatusBadge } from "../components/ApplicationStatusBadge";
import { useApplication } from "../hooks/useApplications";

interface SnapshotSkill {
  name: string;
  proficiency: string;
}

interface SnapshotProject {
  title: string;
  verification_status: string;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Read-only view of the evidence snapshot frozen at Smart Apply time
 * (`Application.evidence_snapshot`, built by `pipeline/evidence.py`) — this
 * is deliberately what was attached when the candidate applied, not a live
 * re-read, so it matches what the recruiter's evidence card showed then. */
export function ApplicationDetailPage() {
  const { applicationId } = useParams<{ applicationId: string }>();
  const detail = useApplication(applicationId ?? "");

  const backLink = (
    <Link
      to="/student/applications"
      className="inline-flex items-center gap-1.5 text-sm text-[var(--slate)] hover:text-[var(--ink)]"
    >
      <ArrowLeft size={14} aria-hidden="true" /> Back to applications
    </Link>
  );

  if (!applicationId) return null;

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
        <ErrorState title="Could not load this application" description="Something went wrong." />
      </div>
    );
  }

  const { application, evidence_snapshot, job_title, company_name } = detail.data;
  const skills = (evidence_snapshot.skills as SnapshotSkill[] | undefined) ?? [];
  const projects = (evidence_snapshot.projects as SnapshotProject[] | undefined) ?? [];
  const match = evidence_snapshot.match as { match_score: number } | null | undefined;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {backLink}

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-semibold text-[var(--ink)]">{job_title}</h1>
          <p className="mt-0.5 text-sm text-[var(--slate)]">{company_name}</p>
          <p className="mt-1.5 text-xs text-[var(--muted)]">
            Applied {formatDate(application.applied_at)} · Updated{" "}
            {formatDate(application.status_updated_at)}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <ApplicationStatusBadge status={application.status} />
          <Link
            to={`/student/jobs/${application.job_posting_id}`}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--slate)] hover:text-[var(--ink)]"
          >
            <Briefcase size={12} aria-hidden="true" />
            View the job
          </Link>
        </div>
      </header>

      <Surface className="p-5 sm:p-6">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-[var(--slate)]">
          Where your application stands
        </h2>
        <div className="mt-4">
          <ApplicationStageTimeline application={application} />
        </div>
      </Surface>

      {application.cover_note ? (
        <Surface className="p-5 sm:p-6">
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
            Your cover note
          </p>
          <p className="whitespace-pre-wrap text-sm text-[var(--ink)]">{application.cover_note}</p>
        </Surface>
      ) : null}

      <Surface className="p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
              Evidence attached when you applied
            </p>
            <p className="mt-1 text-xs text-[var(--muted)]">
              Frozen at Smart Apply time — this is what the recruiter saw, not a live re-read
              of your profile.
            </p>
          </div>
          {match ? <MatchScoreRing value={match.match_score} size={64} /> : null}
        </div>
        {skills.length > 0 ? (
          <div className="mt-4 flex flex-wrap gap-1.5">
            {skills.map((skill) => (
              <Badge key={skill.name} variant="neutral">
                {skill.name} ({skill.proficiency})
              </Badge>
            ))}
          </div>
        ) : null}
        {projects.length > 0 ? (
          <ul className="mt-4 space-y-1.5 text-sm text-[var(--ink)]">
            {projects.map((project) => (
              <li key={project.title} className="flex items-center justify-between gap-3">
                <span className="min-w-0 truncate">{project.title}</span>
                <Badge variant={project.verification_status === "verified" ? "success" : "neutral"}>
                  {project.verification_status}
                </Badge>
              </li>
            ))}
          </ul>
        ) : null}
        {skills.length === 0 && projects.length === 0 && !match ? (
          <p className="mt-4 text-sm text-[var(--slate)]">
            No evidence snapshot was stored with this application.
          </p>
        ) : null}
      </Surface>

      <div>
        <p className="mb-2 text-sm font-semibold text-[var(--ink)]">Messages</p>
        <MessageThread rolePrefix="student" applicationId={applicationId} />
      </div>
    </div>
  );
}
