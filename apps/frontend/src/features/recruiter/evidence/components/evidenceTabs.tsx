import { BadgeCheck, CircleDot, Send, Sparkles } from "lucide-react";

import { ScoreBreakdown, type ScoreDimension } from "@/components/charts/ScoreBreakdown";

import type { EvidenceRecord } from "../api/evidenceApi";

/* ==================================================================
   INTERVIEW TAB
   ================================================================== */

/** Turns `technical_accuracy` into `Technical accuracy`. Sentence case, not
 * title case: the rubric dimensions are phrases, and Title Casing Every Word
 * makes a four-row list read like a set of proper nouns. */
function humanise(dimension: string): string {
  const words = dimension.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/**
 * Per-dimension scores for one interview.
 *
 * Weighted, so a dimension reads as `earned/possible` on the rubric's own
 * scale — `36/40` for a dimension carrying weight 0.40 and scoring 92. No
 * averaging any more: the live interview is scored once over the whole
 * conversation, so each dimension already arrives as a single number rather
 * than as a set of per-answer scores to collapse.
 *
 * **The dimension list comes from the stored rows, never from a constant.**
 * `interview/models.py` versions its rubric and a report is written once and
 * never re-judged, so a v1 interview genuinely has four dimensions, a v2 one
 * five, and a v3 one four different ones. Hardcoding any list would blank a
 * row or invent one, depending on which interview you opened.
 */
function dimensionsFor(scores: EvidenceRecord["interviews"][number]["dimension_scores"]): ScoreDimension[] {
  return scores
    .map((score) => ({
      label: humanise(score.dimension),
      earned: score.score * score.weight,
      possible: 100 * score.weight,
    }))
    // Heaviest dimension first — the rubric's own statement of what matters.
    .sort((a, b) => b.possible - a.possible);
}

export function InterviewTab({ record }: { record: EvidenceRecord }) {
  const interviews = record.interviews.filter((interview) => interview.evidence_report);

  if (interviews.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-[var(--rule)] p-6 text-center text-xs text-[var(--muted)]">
        This candidate has not completed a code-grounded interview yet. Their skill evidence comes
        from verified repositories only.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {interviews.map((interview) => {
        const report = interview.evidence_report!;
        const dimensions = dimensionsFor(interview.dimension_scores);

        return (
          <section key={interview.interview_id} className="space-y-4">
            <div className="flex items-baseline justify-between gap-3">
              <h3 className="text-[11px] font-semibold uppercase tracking-wider text-[var(--slate)]">
                {interview.project_title ?? "Interview"}
              </h3>
              {interview.total_score !== null ? (
                <span className="tabular text-xs text-[var(--slate)]">
                  Completed ·{" "}
                  <span className="font-semibold text-[var(--ink)]">{Math.round(interview.total_score)}/100</span>
                </span>
              ) : null}
            </div>

            {report.summary ? (
              <p className="text-[12px] leading-relaxed text-[var(--slate)]">{report.summary}</p>
            ) : null}

            <ScoreBreakdown dimensions={dimensions} />

            {/* Contradictions are surfaced above the transcript, not buried in
                it. "The analysis says otherwise" is the single most decision-
                relevant thing this interview produces, and a recruiter should
                not have to read six turns to find it. Unsupported claims are
                deliberately not promoted here — absence of evidence is not
                evidence, and putting it next to contradictions would read as
                if it were. */}
            {report.contradicted_claims.length > 0 ? (
              <div className="rounded-lg border border-[var(--failed)]/30 bg-[var(--failed)]/5 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--failed)]">
                  The repository analysis disagreed
                </p>
                <ul className="mt-1.5 space-y-1">
                  {report.contradicted_claims.map((claim) => (
                    <li key={claim} className="text-[12px] leading-relaxed text-[var(--slate)]">
                      {claim}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div>
              <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--slate)]">
                Transcript
              </h4>
              {/* The conversation in order, both sides, unedited. A
                  transcript that showed only the questions and their answers
                  would hide the follow-ups — and a follow-up is precisely
                  where a thin first answer either recovers or doesn't. */}
              <ul className="space-y-2">
                {interview.transcript.map((turn) => (
                  <li
                    key={turn.sequence}
                    className="rounded-lg border border-[var(--rule)] bg-[var(--panel)] p-3"
                  >
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">
                      {turn.role === "interviewer" ? "Interviewer" : "Candidate"}
                    </p>
                    <p
                      className={
                        turn.role === "interviewer"
                          ? "mt-1 text-[12px] leading-relaxed text-[var(--slate)]"
                          : "mt-1 border-l-2 border-[var(--rule)] pl-2.5 text-[12px] italic leading-relaxed text-[var(--slate)]"
                      }
                    >
                      {turn.text}
                    </p>
                  </li>
                ))}
              </ul>

              {/* The grounding claim, stated once per interview rather than
                  per question: every question in it was generated from this
                  repository's stored analysis, which is what makes the whole
                  transcript evidence rather than opinion. */}
              {report.verified_claims.length > 0 ? (
                <p className="mt-3 flex items-center gap-1.5 text-[10px] text-[var(--verified)]">
                  <BadgeCheck size={10} aria-hidden="true" />
                  {report.verified_claims.length} claim
                  {report.verified_claims.length === 1 ? "" : "s"} checked against the analysed repository
                </p>
              ) : null}
            </div>
          </section>
        );
      })}
    </div>
  );
}

/* ==================================================================
   ACTIVITY TAB
   ================================================================== */

export interface ActivityEvent {
  label: string;
  at: string | null;
  icon: typeof CircleDot;
}

/**
 * The pair's timeline, built only from timestamps that exist.
 *
 * Three events at most, because three is how many this system actually
 * records against a candidate-job pair without replaying `audit_log`: when
 * they matched, when the score last moved, and when they applied. Stage
 * transitions after that are recorded, but the evidence endpoint does not
 * return them — so rather than render a plausible-looking "Moved to
 * shortlist" row with a guessed date, this shows what it can prove and the
 * application detail page carries the rest.
 */
export function ActivityTab({
  record,
  appliedAt,
}: {
  record: EvidenceRecord;
  appliedAt: string | null;
}) {
  const events: ActivityEvent[] = [];

  if (record.match) {
    events.push({ label: "Matched to this role", at: null, icon: Sparkles });
  }
  if (appliedAt) {
    events.push({ label: "Applied via Smart Apply", at: appliedAt, icon: Send });
  }

  if (events.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-[var(--rule)] p-6 text-center text-xs text-[var(--muted)]">
        No activity recorded for this candidate on this role yet.
      </p>
    );
  }

  return (
    <ol className="relative space-y-4 border-l border-[var(--rule)] pl-4">
      {events.map((event) => (
        <li key={event.label} className="relative">
          <span className="absolute -left-[22px] top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-[var(--panel)]">
            <event.icon size={11} className="text-gt-electric" aria-hidden="true" />
          </span>
          <p className="text-[13px] text-[var(--ink)]">{event.label}</p>
          {event.at ? (
            <p className="text-[11px] text-[var(--muted)]">
              {new Date(event.at).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </p>
          ) : null}
        </li>
      ))}
    </ol>
  );
}
