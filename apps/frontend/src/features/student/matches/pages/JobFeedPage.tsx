import { Briefcase, CheckCircle2, MapPin, XCircle } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Badge, Button, EmptyState, ErrorState, MatchTimestamps, Skeleton } from "@/components";
import { SmartApplyModal } from "@/features/student/applications/components/SmartApplyModal";
import { useMyApplications } from "@/features/student/applications/hooks/useApplications";

import type { MatchedJob, SkillMatchReason } from "../api/matchesApi";
import { useJobFeed } from "../hooks/useJobFeed";

function SkillReasonChip({ reason }: { reason: SkillMatchReason }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${
        reason.candidate_has_skill
          ? "border-verified/30 bg-verified/5 text-verified"
          : "border-rule bg-panel text-slate-400"
      }`}
    >
      {reason.candidate_has_skill ? (
        <CheckCircle2 size={11} aria-hidden="true" />
      ) : (
        <XCircle size={11} aria-hidden="true" />
      )}
      {reason.skill_name}
    </span>
  );
}

function JobCard({ match, alreadyApplied }: { match: MatchedJob; alreadyApplied: boolean }) {
  const [applyOpen, setApplyOpen] = useState(false);

  return (
    <li className="rounded-2xl border border-rule bg-white p-5">
      <div className="mb-2 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-medium text-ink">{match.job.title}</p>
          <p className="text-xs text-slate-500">{match.job.company_name}</p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-semibold tabular-nums text-ink">{match.match_score.toFixed(0)}</p>
          <p className="text-xs text-slate-400">match score</p>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-3 text-xs text-slate-500">
        <Badge variant="neutral">{match.job.job_type.replace("_", " ")}</Badge>
        <Badge variant="neutral">{match.job.experience_level}</Badge>
        <span className="flex items-center gap-1">
          <MapPin size={12} aria-hidden="true" />
          {match.job.is_remote ? "Remote" : (match.job.location ?? "Not specified")}
        </span>
        <MatchTimestamps computedAt={match.computed_at} updatedAt={match.updated_at} />
      </div>

      {match.matched_required_skills.length > 0 ? (
        <div className="mb-4">
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">Must-have skills</p>
          <div className="flex flex-wrap gap-1.5">
            {match.matched_required_skills.map((reason) => (
              <SkillReasonChip key={reason.skill_name} reason={reason} />
            ))}
          </div>
        </div>
      ) : null}

      <div className="flex justify-end">
        {alreadyApplied ? (
          <Badge variant="success">Applied</Badge>
        ) : (
          <Button type="button" size="sm" onClick={() => setApplyOpen(true)}>
            Smart Apply
          </Button>
        )}
      </div>

      <SmartApplyModal
        open={applyOpen}
        onClose={() => setApplyOpen(false)}
        jobId={match.job.job_id}
        jobTitle={match.job.title}
        matchedSkills={match.matched_required_skills
          .filter((r) => r.candidate_has_skill)
          .map((r) => ({ label: r.skill_name }))}
      />
    </li>
  );
}

/**
 * The student side of the same computation the recruiter's matched-
 * candidates list reads (`domains/matching/service.py`) — a personalised
 * ranked job feed, `GET /api/v1/student/matches`. Nothing here is computed
 * client-side; every score and reason is read straight off `match_results`.
 */
export function JobFeedPage() {
  const feed = useJobFeed();
  const applications = useMyApplications();
  const appliedJobIds = new Set((applications.data ?? []).map((item) => item.application.job_posting_id));

  if (feed.isPending) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (feed.isError) {
    return <ErrorState title="Could not load your job feed" description="Something went wrong." />;
  }

  if (feed.data.length === 0) {
    return (
      <EmptyState
        icon={Briefcase}
        title="No matched jobs yet"
        description="Complete your profile and verify a repository or coding-platform account — matches appear here once your profile clears the match threshold against a published job."
      />
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink">Job matches</h1>
          <p className="mt-1 text-sm text-slate-500">
            Ranked for you, from the same computation recruiters use to find candidates.
          </p>
        </div>
        <Link to="/student/applications" className="text-sm font-medium text-ink hover:underline">
          View my applications →
        </Link>
      </header>

      <ul className="space-y-3">
        {feed.data.map((match) => (
          <JobCard key={match.job.job_id} match={match} alreadyApplied={appliedJobIds.has(match.job.job_id)} />
        ))}
      </ul>
    </div>
  );
}
