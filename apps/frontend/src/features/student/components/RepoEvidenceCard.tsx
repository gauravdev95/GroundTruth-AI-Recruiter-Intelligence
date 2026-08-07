import { GitBranch } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components";
import { useLatestInterview } from "@/features/student/interview/hooks/useInterview";

import type { Project } from "../api/profileApi";
import { StageTimeline } from "./StageTimeline";
import { VerificationBadge } from "./SectionBadges";

/** One project's evidence at a glance — verification status, contribution
 * share (from `Project.verification_payload`, written by
 * `jobs/tasks/verification.py::verify_repository_task`), interview score if
 * the code-grounded interview has been taken, and the per-stage progress
 * strip underneath. */
export function RepoEvidenceCard({ project }: { project: Project }) {
  const interview = useLatestInterview(project.id);
  const contributionShare = project.verification_payload?.contribution_share;

  return (
    <div className="rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-4">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <GitBranch size={14} className="text-[var(--muted)]" aria-hidden="true" />
          <p className="font-medium text-[var(--ink)]">{project.title}</p>
        </div>
        <VerificationBadge status={project.verification_status} />
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        {project.technologies.slice(0, 4).map((tech) => (
          <Badge key={tech} variant="neutral">
            {tech}
          </Badge>
        ))}
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-[var(--rule)] pt-3 text-xs">
        <span className="text-[var(--slate)]">
          {contributionShare !== undefined ? `${Math.round(contributionShare * 100)}% contribution` : "Contribution not yet analyzed"}
        </span>

        {project.verification_status === "verified" ? (
          interview.data ? (
            interview.data.total_score !== null ? (
              <span className="font-semibold text-[var(--ink)]">Interview: {interview.data.total_score.toFixed(0)}/100</span>
            ) : (
              <Link to={`/student/interview/${project.id}`} className="font-medium text-[var(--ink)] hover:underline">
                Interview in progress →
              </Link>
            )
          ) : (
            <Link to={`/student/interview/${project.id}`} className="font-medium text-[var(--ink)] hover:underline">
              Take code interview →
            </Link>
          )
        ) : null}
      </div>

      {/* Only repositories run the pipeline — a described (non-repo) project
          has no stages, and `StageTimeline` renders nothing for an empty
          list rather than an empty strip. */}
      <StageTimeline stages={project.verification_stages ?? []} />
    </div>
  );
}
