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
 * Averaged across the interview's questions and then weighted, so a dimension
 * reads as `earned/possible` on the rubric's own scale — `36/40` for a
 * dimension carrying weight 0.40 and averaging 92.
 *
 * **The dimension list comes from the stored report, never from a constant.**
 * `interview/models.py` versions its rubric and an evidence report is written
 * once and never re-judged, so a v1 interview genuinely has four dimensions
 * (technical accuracy, depth of reasoning, codebase specificity, repository
 * consistency) and a v2 one has five. Hardcoding either list would blank a
 * row or invent one, depending on which interview you opened.
 */
function dimensionsFor(report: NonNullable<EvidenceRecord["interviews"][number]["evidence_report"]>): ScoreDimension[] {
  const totals = new Map<string, { sum: number; count: number; weight: number }>();

  for (const question of report.questions ?? []) {
    for (const score of question.scores ?? []) {
      const current = totals.get(score.dimension) ?? { sum: 0, count: 0, weight: score.weight };
      current.sum += score.score;
      current.count += 1;
      current.weight = score.weight;
      totals.set(score.dimension, current);
    }
  }

  return [...totals.entries()]
    .map(([dimension, { sum, count, weight }]) => ({
      label: humanise(dimension),
      earned: (sum / Math.max(1, count)) * weight,
      possible: 100 * weight,
    }))
    // Heaviest dimension first — the rubric's own statement of what matters.
    .sort((a, b) => b.possible - a.possible);
}

export function InterviewTab({ record }: { record: EvidenceRecord }) {
  const interviews = record.interviews.filter((interview) => interview.evidence_report);

  if (interviews.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-rule p-6 text-center text-xs text-slate-400">
        This candidate has not completed a code-grounded interview yet. Their skill evidence comes
        from verified repositories only.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {interviews.map((interview) => {
        const report = interview.evidence_report!;
        const dimensions = dimensionsFor(report);

        return (
          <section key={interview.interview_id} className="space-y-4">
            <div className="flex items-baseline justify-between gap-3">
              <h3 className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                {interview.project_title ?? "Interview"}
              </h3>
              {interview.total_score !== null ? (
                <span className="tabular text-xs text-slate-500">
                  Completed ·{" "}
                  <span className="font-semibold text-ink">{Math.round(interview.total_score)}/100</span>
                </span>
              ) : null}
            </div>

            <ScoreBreakdown dimensions={dimensions} />

            <div>
              <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Transcript
              </h4>
              <ul className="space-y-2">
                {(report.questions ?? []).map((question) => (
                  <li
                    key={question.sequence}
                    className="rounded-lg border border-rule bg-panel p-3"
                  >
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                      Interviewer
                    </p>
                    <p className="mt-1 text-[12px] leading-relaxed text-slate-700">{question.prompt}</p>

                    <p className="mt-2.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                      Candidate
                    </p>
                    <p className="mt-1 border-l-2 border-rule pl-2.5 text-[12px] italic leading-relaxed text-slate-600">
                      “{question.transcript}”
                    </p>

                    {/* The grounding is what makes this evidence rather than
                        an opinion — the question was generated from a real
                        file in a repository this system verified. */}
                    {question.grounded_in?.description ? (
                      <p className="mt-2 flex items-center gap-1.5 text-[10px] text-verified">
                        <BadgeCheck size={10} aria-hidden="true" />
                        Grounded in {question.grounded_in.description}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
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
      <p className="rounded-lg border border-dashed border-rule p-6 text-center text-xs text-slate-400">
        No activity recorded for this candidate on this role yet.
      </p>
    );
  }

  return (
    <ol className="relative space-y-4 border-l border-rule pl-4">
      {events.map((event) => (
        <li key={event.label} className="relative">
          <span className="absolute -left-[22px] top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-white">
            <event.icon size={11} className="text-gt-electric" aria-hidden="true" />
          </span>
          <p className="text-[13px] text-ink">{event.label}</p>
          {event.at ? (
            <p className="text-[11px] text-slate-400">
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
