import { ArrowLeft, Building2, Check, MapPin, X } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { ErrorState, MatchTimestamps, Skeleton } from "@/components";
import { useCountUp } from "@/design/motion";
import { SmartApplyButton } from "@/features/student/applications/components/SmartApplyButton";
import { useMyApplications } from "@/features/student/applications/hooks/useApplications";

import type { MatchedJob, SkillMatchReason } from "../api/matchesApi";
import { useJobFeed } from "../hooks/useJobFeed";

/**
 * One requirement, with the student's own standing against it.
 *
 * **The gap case is grey with an ✗, never red.** A skill this student has not
 * proven yet is a gap, not a failure — and red on a candidate-facing screen
 * about their own profile reads as rejection, which is a claim no automated
 * surface in this product is allowed to make. Green is spent only where the
 * evidence is real, matching the badge vocabulary everywhere else.
 */
function RequirementRow({ skill, isRequired }: { skill: SkillMatchReason; isRequired: boolean }) {
  const has = skill.candidate_has_skill;
  const percent = skill.evidence_weight === null ? null : Math.round(skill.evidence_weight * 100);
  const source = skill.evidence_sources[0];

  return (
    <li className="flex items-start justify-between gap-4 py-2.5">
      <div className="flex min-w-0 items-start gap-2.5">
        <span
          className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full ${
            has ? "bg-[var(--verified)]/10 text-[var(--verified)]" : "bg-[var(--panel-raised)] text-[var(--muted)]"
          }`}
        >
          {has ? <Check size={10} aria-hidden="true" /> : <X size={10} aria-hidden="true" />}
        </span>
        <div className="min-w-0">
          <p className="text-[13px] font-medium text-[var(--ink)]">
            {skill.skill_name}
            {!isRequired ? <span className="ml-1.5 text-[11px] text-[var(--muted)]">nice to have</span> : null}
          </p>
          {has && source ? (
            <p className="truncate text-[11px] text-[var(--muted)]">{source.title ?? source.type}</p>
          ) : !has ? (
            <p className="text-[11px] text-[var(--muted)]">No verified evidence on your profile yet</p>
          ) : null}
        </div>
      </div>
      {percent !== null ? (
        <span className="tabular shrink-0 text-xs text-[var(--slate)]">{percent}%</span>
      ) : null}
    </li>
  );
}

/**
 * `/student/jobs/:jobId` — the full posting, plus why this student scored
 * what they scored.
 *
 * ## Why this reads from the feed rather than a job endpoint
 *
 * There is no student-facing "get any job by id" route, and adding one would
 * mean writing an authorisation rule for it. The feed already answers exactly
 * the right question — *the jobs this student matched* — and a match row is
 * itself the proof of entitlement. So this finds its job in the feed the
 * dashboard already loaded (React Query serves it from cache on a click
 * through from the High Match card), and a job the student did not match
 * simply is not found, with no separate 403 path to get wrong.
 */
export function JobDetailPage() {
  const { jobId = "" } = useParams<{ jobId: string }>();
  const feed = useJobFeed();
  const applications = useMyApplications();

  const match: MatchedJob | undefined = feed.data?.find((item) => item.job.job_id === jobId);
  const score = Math.round(match?.match_score ?? 0);
  const displayScore = Math.round(useCountUp(score));

  if (feed.isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (feed.isError) {
    return <ErrorState title="Could not load this job" description="Something went wrong." />;
  }

  if (!match) {
    return (
      <ErrorState
        title="This job is not in your matches"
        description="You can only open a job you have been matched to. It may also have been closed since you last looked."
        action={
          <Link to="/student/matches" className="text-sm font-medium text-[var(--ink)] hover:underline">
            Back to your matches
          </Link>
        }
      />
    );
  }

  const hasApplied = (applications.data ?? []).some(
    (item) => item.application.job_posting_id === jobId,
  );
  const place = match.job.is_remote
    ? [match.job.location, "Remote"].filter(Boolean).join(" · ")
    : (match.job.location ?? "Location not specified");

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link
        to="/student/matches"
        className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--slate)] transition hover:text-[var(--ink)]"
      >
        <ArrowLeft size={13} aria-hidden="true" />
        Your matches
      </Link>

      <header className="rounded-xl border border-[var(--rule)] bg-[var(--panel)] p-6 shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="font-display text-2xl font-semibold tracking-tight text-[var(--ink)]">
              {match.job.title}
            </h1>
            <p className="mt-1 flex flex-wrap items-center gap-x-1.5 text-sm text-[var(--slate)]">
              <Building2 size={13} aria-hidden="true" />
              <span>{match.job.company_name}</span>
              <span aria-hidden="true">·</span>
              <MapPin size={13} aria-hidden="true" />
              <span>{place}</span>
            </p>
            <MatchTimestamps computedAt={match.computed_at} updatedAt={match.updated_at} />
          </div>
          <div className="shrink-0 text-right">
            <p className="tabular font-display text-3xl font-semibold text-[var(--blue)]">
              {displayScore}%
            </p>
            <p className="text-[11px] uppercase tracking-wide text-[var(--muted)]">match</p>
          </div>
        </div>

        <p className="mt-4 border-l-2 border-[var(--blue)] bg-[var(--blue)]/5 py-2.5 pl-3.5 pr-3 text-[13px] leading-relaxed text-[var(--slate)]">
          {match.reasoning}
        </p>

        <div className="mt-5">
          <SmartApplyButton
            jobId={match.job.job_id}
            jobTitle={match.job.title}
            companyName={match.job.company_name}
            emphasis={match.tier === "smart_apply_recommended"}
            hasApplied={hasApplied}
          />
        </div>
      </header>

      <section className="rounded-xl border border-[var(--rule)] bg-[var(--panel)] p-6 shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-[var(--slate)]">
          How you score against the requirements
        </h2>
        <p className="mt-1 text-xs text-[var(--muted)]">
          Every row is read from your verified evidence — nothing here is self-reported.
        </p>
        <ul className="mt-2 divide-y divide-[var(--rule)]/60">
          {match.matched_required_skills.map((skill) => (
            <RequirementRow key={skill.skill_name} skill={skill} isRequired />
          ))}
          {match.matched_desirable_skills.map((skill) => (
            <RequirementRow key={skill.skill_name} skill={skill} isRequired={false} />
          ))}
        </ul>
      </section>

      <section className="rounded-xl border border-[var(--rule)] bg-[var(--panel)] p-6 shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-[var(--slate)]">
          About the role
        </h2>
        {/* `whitespace-pre-line` rather than a markdown renderer: this is the
            recruiter's own plain-text description and rendering it as markdown
            would let a stray character restyle their posting. */}
        <p className="mt-2.5 whitespace-pre-line text-sm leading-relaxed text-[var(--slate)]">
          {match.job.description}
        </p>
      </section>
    </div>
  );
}
