import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { Badge, ErrorState, Skeleton } from "@/components";
import { MessageThread } from "@/features/messaging";

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

/** Read-only view of the evidence snapshot frozen at Smart Apply time
 * (`Application.evidence_snapshot`, built by `pipeline/evidence.py`) — this
 * is deliberately what was attached when the candidate applied, not a live
 * re-read, so it matches what the recruiter's evidence card showed then. */
export function ApplicationDetailPage() {
  const { applicationId } = useParams<{ applicationId: string }>();
  const detail = useApplication(applicationId ?? "");

  const backLink = (
    <Link to="/student/applications" className="inline-flex items-center gap-1.5 text-sm text-[var(--slate)] hover:text-[var(--ink)]">
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
    <div className="space-y-6">
      {backLink}

      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-semibold text-[var(--ink)]">{job_title}</h1>
          <p className="text-sm text-[var(--slate)]">{company_name}</p>
        </div>
        <ApplicationStatusBadge status={application.status} />
      </header>

      {application.cover_note ? (
        <div className="rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-5">
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">Your cover note</p>
          <p className="whitespace-pre-wrap text-sm text-[var(--ink)]">{application.cover_note}</p>
        </div>
      ) : null}

      <div className="rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-5">
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
          Evidence attached when you applied
        </p>
        {match ? (
          <p className="mb-3 text-sm text-[var(--ink)]">
            Match score at the time: <span className="font-semibold">{match.match_score.toFixed(0)}</span>
          </p>
        ) : null}
        {skills.length > 0 ? (
          <div className="mb-3 flex flex-wrap gap-1.5">
            {skills.map((skill) => (
              <Badge key={skill.name} variant="neutral">
                {skill.name} ({skill.proficiency})
              </Badge>
            ))}
          </div>
        ) : null}
        {projects.length > 0 ? (
          <ul className="space-y-1.5 text-sm text-[var(--ink)]">
            {projects.map((project) => (
              <li key={project.title} className="flex items-center justify-between">
                <span>{project.title}</span>
                <Badge variant={project.verification_status === "verified" ? "success" : "neutral"}>
                  {project.verification_status}
                </Badge>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div>
        <p className="mb-2 text-sm font-semibold text-[var(--ink)]">Messages</p>
        <MessageThread rolePrefix="student" applicationId={applicationId} />
      </div>
    </div>
  );
}
