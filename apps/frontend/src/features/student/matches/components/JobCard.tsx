import { CalendarClock, CheckCircle2, MapPin, XCircle } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge, MatchTimestamps } from "@/components";
import { Surface } from "@/design/Surface";
import { SmartApplyButton } from "@/features/student/applications/components/SmartApplyButton";

import type { MatchedJob, SkillMatchReason } from "../api/matchesApi";
import { formatJobLabel } from "../lib/feedFilters";
import { MatchScoreRing } from "./MatchScoreRing";

function SkillReasonChip({ reason }: { reason: SkillMatchReason }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${
        reason.candidate_has_skill
          ? "border-[var(--verified)]/30 bg-[var(--verified)]/10 text-[var(--verified)]"
          : "border-[var(--rule)] bg-[var(--panel)] text-[var(--muted)]"
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

function formatDeadline(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/**
 * One ranked match in the feed.
 *
 * The ring carries the score and the `High match` chip carries the tier —
 * the only banding the backend defines (`matching/tiers.py` resolves Tier B
 * and the student UI names it "High Match", never "Tier B"). A card that is
 * merely in the feed makes no band claim of its own.
 *
 * The skill chips keep the verified/gap vocabulary from the detail page:
 * green only where the candidate provably holds the skill (tokens.css
 * rule 1); a missing skill is grey, never red — a gap is not a failure.
 */
export function JobCard({ match, alreadyApplied }: { match: MatchedJob; alreadyApplied: boolean }) {
  const place = match.job.is_remote
    ? [match.job.location, "Remote"].filter(Boolean).join(" · ")
    : (match.job.location ?? "Location not specified");

  return (
    <Surface as="article" className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="font-display text-lg font-semibold tracking-tight text-[var(--ink)]">
            <Link to={`/student/jobs/${match.job.job_id}`} className="hover:underline">
              {match.job.title}
            </Link>
          </h2>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-sm text-[var(--slate)]">
            <span className="font-medium text-[var(--ink)]">{match.job.company_name}</span>
            <span aria-hidden="true">·</span>
            <MapPin size={13} aria-hidden="true" />
            <span>{place}</span>
          </p>
        </div>
        <MatchScoreRing value={match.match_score} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {match.tier === "smart_apply_recommended" ? (
          <Badge variant="accent">High match</Badge>
        ) : null}
        <Badge variant="neutral">{formatJobLabel(match.job.job_type)}</Badge>
        <Badge variant="neutral">{formatJobLabel(match.job.experience_level)}</Badge>
        {match.job.deadline ? (
          <span className="inline-flex items-center gap-1 text-xs text-[var(--slate)]">
            <CalendarClock size={12} aria-hidden="true" />
            Closes {formatDeadline(match.job.deadline)}
          </span>
        ) : null}
        <MatchTimestamps computedAt={match.computed_at} updatedAt={match.updated_at} />
      </div>

      {match.matched_required_skills.length > 0 ? (
        <div className="mt-4">
          <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-[var(--muted)]">
            Must-have skills
          </p>
          <div className="flex flex-wrap gap-1.5">
            {match.matched_required_skills.map((reason) => (
              <SkillReasonChip key={reason.skill_name} reason={reason} />
            ))}
          </div>
        </div>
      ) : null}

      <p className="mt-3 text-[13px] leading-relaxed text-[var(--slate)]">{match.reasoning}</p>

      <div className="mt-4 flex flex-wrap items-center justify-end gap-2 border-t border-[var(--rule-soft)] pt-4">
        <Link
          to={`/student/jobs/${match.job.job_id}`}
          className="rounded-xl border border-[var(--rule)] px-3.5 py-2 text-[13px] font-semibold text-[var(--ink)] transition hover:bg-[var(--panel-raised)]"
        >
          View details
        </Link>
        {/* No `emphasis` here even for a Tier B row: several of these sit in
            one column, and a column of pulsing buttons is noise. The Tier B
            interrupt lives on the dashboard card, once. */}
        <SmartApplyButton
          jobId={match.job.job_id}
          jobTitle={match.job.title}
          companyName={match.job.company_name}
          hasApplied={alreadyApplied}
        />
      </div>
    </Surface>
  );
}
