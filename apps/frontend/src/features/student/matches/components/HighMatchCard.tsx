import { Check, MapPin, Target } from "lucide-react";
import { Link } from "react-router-dom";

import { useCountUp } from "@/design/motion";
import { SmartApplyButton } from "@/features/student/applications/components/SmartApplyButton";

import type { MatchedJob } from "../api/matchesApi";

/**
 * The Tier B prompt — "High Match", the only interrupt this product shows a
 * student on their own dashboard.
 *
 * ## Why only Tier B reaches this component
 *
 * `matching/tiers.py` draws the line: Tier A is discoverable (it occupies a
 * slot on a recruiter's board and appears in the student's feed), Tier B is
 * "strong enough to be worth interrupting a student for". This card *is* the
 * interrupt. Rendering it for Tier A would make every match an interrupt,
 * which trains students to ignore the one that mattered — the exact failure
 * the percentile half of the Tier B cutoff exists to prevent.
 *
 * The word "Tier B" never appears. Students read "High Match".
 *
 * ## Every number here traces to something visible
 *
 * The percentage is `match_score` as stored. The skill chips are the job's
 * *required* skills with `candidate_has_skill` true — the same
 * `match_reasons` payload the recruiter's card renders from, so a student and
 * a recruiter looking at this pair see one set of claims. `reasoning` is
 * composed server-side by string formatting, never model-written.
 */
export function HighMatchCard({ match, hasApplied }: { match: MatchedJob; hasApplied: boolean }) {
  const score = Math.round(match.match_score);
  const displayScore = Math.round(useCountUp(score));

  // Required skills the candidate actually holds. Desirables are deliberately
  // excluded: this line is the answer to "why is this a high match", and a
  // nice-to-have does not carry that claim.
  const matchedRequired = match.matched_required_skills.filter((skill) => skill.candidate_has_skill);

  const place = match.job.is_remote
    ? [match.job.location, "Remote"].filter(Boolean).join(" · ")
    : (match.job.location ?? "Location not specified");

  return (
    <article className="overflow-hidden rounded-xl border border-gt-electric/25 bg-white shadow-[0_1px_3px_rgba(0,0,0,0.08)] transition hover:-translate-y-px hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)]">
      <div className="border-b border-gt-electric/15 bg-gt-electric/[0.04] px-5 py-2.5">
        <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-gt-electric">
          <Target size={13} aria-hidden="true" />
          High match
          {/* `tabular` keeps the digits from reflowing while the count-up
              runs — without it the whole overline jitters for 600ms. */}
          <span className="tabular">— {displayScore}%</span>
        </p>
      </div>

      <div className="px-5 py-4">
        <h3 className="font-display text-lg font-semibold tracking-tight text-ink">{match.job.title}</h3>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs text-slate-500">
          <span>{match.job.company_name}</span>
          <span aria-hidden="true">·</span>
          <MapPin size={11} aria-hidden="true" />
          <span>{place}</span>
        </p>

        {matchedRequired.length > 0 ? (
          <div className="mt-3.5">
            <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
              Matches your verified skills
            </p>
            <ul className="mt-1.5 flex flex-wrap gap-1.5">
              {matchedRequired.map((skill) => (
                <li
                  key={skill.skill_name}
                  className="inline-flex items-center gap-1 rounded-full border border-verified/25 bg-verified/5 px-2.5 py-1 text-[11px] font-medium text-verified"
                >
                  <Check size={10} aria-hidden="true" />
                  {skill.skill_name}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <p className="mt-3 text-xs leading-relaxed text-slate-500">{match.reasoning}</p>

        <p className="mt-3.5 border-l-2 border-rule pl-3 text-[13px] leading-relaxed text-slate-600">
          Your evidence profile is your application.
          <br />
          <span className="text-slate-400">One click. No forms. No resume upload.</span>
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <SmartApplyButton
            jobId={match.job.job_id}
            jobTitle={match.job.title}
            companyName={match.job.company_name}
            emphasis
            hasApplied={hasApplied}
          />
          <Link
            to={`/student/jobs/${match.job.job_id}`}
            className="rounded-xl border border-rule px-4 py-2.5 text-[13px] font-semibold text-ink transition hover:bg-slate-50"
          >
            View details
          </Link>
        </div>
      </div>
    </article>
  );
}
