import { CheckCircle2, XCircle } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge, MatchTimestamps } from "@/components";

import type { MatchedCandidate, SkillMatchReason } from "../api/jobsApi";

function SkillReasonChip({ reason }: { reason: SkillMatchReason }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${
        reason.candidate_has_skill ? "border-verified/30 bg-verified/5 text-verified" : "border-rule bg-panel text-slate-400"
      }`}
      title={
        reason.evidence_weight != null
          ? `Evidence weight ${(reason.evidence_weight * 100).toFixed(0)}%`
          : "No evidence found"
      }
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

/**
 * Match reasons rendered straight from the stored `matched_required_skills`
 * / `matched_desirable_skills` payload — never re-derived or narrated
 * client-side, matching the same "never LLM-narrated after the fact"
 * constraint the backend follows.
 */
export function MatchedCandidatesList({ candidates }: { candidates: MatchedCandidate[] }) {
  if (candidates.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-rule bg-panel px-4 py-8 text-center text-sm text-slate-500">
        No matches yet. Matches appear once discoverable candidates clear the match threshold.
      </p>
    );
  }

  return (
    <ul className="space-y-3">
      {candidates.map((match) => (
        <li key={match.candidate.candidate_profile_id} className="rounded-2xl border border-rule bg-white p-5">
          <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
            <div>
              <Link
                to={`/recruiter/candidates/${match.candidate.candidate_profile_id}/evidence`}
                className="font-medium text-ink hover:underline"
              >
                {match.candidate.headline ?? "Candidate"}
              </Link>
              <p className="text-xs text-slate-500">
                {[match.candidate.college, match.candidate.degree, match.candidate.location]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </div>
            <div className="text-right">
              <p className="text-2xl font-semibold tabular-nums text-ink">{match.match_score.toFixed(0)}</p>
              <p className="text-xs text-slate-400">match score</p>
            </div>
          </div>

          <div className="mb-3 flex flex-wrap gap-3 text-xs text-slate-500">
            <span>Semantic {(match.semantic_score * 100).toFixed(0)}%</span>
            <span>Evidence {(match.evidence_score * 100).toFixed(0)}%</span>
            <span>Profile strength {match.candidate.profile_strength}</span>
            <Badge variant="neutral">Class of {match.candidate.graduation_year ?? "—"}</Badge>
            {/* Same two labels the student feed uses — one wording for one
                pair of columns, so the two sides of a match cannot describe
                the same instant differently. */}
            <MatchTimestamps computedAt={match.computed_at} updatedAt={match.updated_at} />
          </div>

          {match.matched_required_skills.length > 0 ? (
            <div className="mb-2">
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">Must-have</p>
              <div className="flex flex-wrap gap-1.5">
                {match.matched_required_skills.map((reason) => (
                  <SkillReasonChip key={reason.skill_name} reason={reason} />
                ))}
              </div>
            </div>
          ) : null}

          {match.matched_desirable_skills.length > 0 ? (
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">Desirable</p>
              <div className="flex flex-wrap gap-1.5">
                {match.matched_desirable_skills.map((reason) => (
                  <SkillReasonChip key={reason.skill_name} reason={reason} />
                ))}
              </div>
            </div>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
