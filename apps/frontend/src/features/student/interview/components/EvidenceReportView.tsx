import { AlertTriangle, Check, CheckCircle2, Minus, ThumbsUp, TrendingUp } from "lucide-react";

import { Card } from "@/components";
import { Surface } from "@/design";

import type { EvidenceReport } from "../api/interviewApi";

const DIMENSION_LABELS: Record<string, string> = {
  // v3 — the live interview's rubric.
  technical_accuracy: "Technical accuracy",
  code_understanding: "Code understanding",
  problem_solving: "Problem solving",
  communication: "Communication",
  // Retained so a report from an earlier rubric still renders under its own
  // vocabulary. A report is written once and never edited, so these labels
  // outlive the rubric that produced them.
  repository_knowledge: "Repository knowledge",
  depth_of_reasoning: "Depth of reasoning",
  codebase_specificity: "Codebase specificity",
  repository_consistency: "Repository consistency",
};

/**
 * Scores are NOT status (tokens.css rule 1): a high score is not a verified
 * claim and a low one is not a failure. Score bars and the headline number
 * therefore use the student accent `--blue`, never `--verified` green.
 * Green appears only where the report makes a status claim — the "verified
 * against your code" list — and amber/red only on the claim lists they
 * belong to.
 */
function ScoreBar({ score }: { score: number }) {
  return (
    <div
      className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--panel-raised)]"
      role="progressbar"
      aria-valuenow={Math.round(score)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="h-1.5 rounded-full bg-[var(--blue)]"
        style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
      />
    </div>
  );
}

/** Claim lists carry their own meaning, so they carry their own framing.
 * "Unsupported" is deliberately not styled as a failure: the analysis simply
 * had nothing to say either way, which uncommitted or unanalysed work explains
 * perfectly well. Only "contradicted" means the evidence disagreed. */
function ClaimList({
  title,
  claims,
  note,
  tone,
  icon,
}: {
  title: string;
  claims: string[];
  note: string;
  tone: string;
  icon: React.ReactNode;
}) {
  if (claims.length === 0) return null;
  return (
    <Card title={title} subtitle={note} padding="md">
      <ul className="space-y-2">
        {claims.map((claim) => (
          <li key={claim} className="flex gap-2.5 text-sm leading-relaxed text-[var(--slate)]">
            <span aria-hidden="true" className={tone}>
              {icon}
            </span>
            <span>{claim}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/**
 * The finished interview: the score and how it was reached, then the whole
 * conversation it was reached from.
 *
 * The transcript is included in full and unedited. A scorecard a candidate
 * cannot check against what they actually said is exactly the unfalsifiable
 * assessment this product exists to replace — so the evidence ships with the
 * verdict, in the same view, not behind a request.
 *
 * Every number here comes from the report response. A dimension the response
 * does not carry is simply not rendered — nothing is filled in from a rubric
 * the interview did not use.
 */
export function EvidenceReportView({ report }: { report: EvidenceReport }) {
  return (
    <div className="space-y-6">
      {/* Overall score. */}
      <Surface elevation="raised" className="p-6 sm:p-8">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[var(--blue)]/12 text-[var(--blue)]">
              <CheckCircle2 size={22} aria-hidden="true" />
            </span>
            <div>
              <h2 className="font-display text-lg font-semibold text-[var(--ink)]">
                Interview complete
              </h2>
              <p className="mt-1 text-sm text-[var(--slate)]">
                Completed {new Date(report.completed_at).toLocaleString()}
                {report.transcript.length > 0
                  ? ` · ${report.transcript.length} turns in the conversation`
                  : ""}
              </p>
              <p className="mt-2 max-w-xl text-xs leading-relaxed text-[var(--muted)]">
                Scored against the same repository analysis the questions came from. The
                breakdown below shows where each point came from — and the transcript at the
                bottom shows what was actually said.
              </p>
            </div>
          </div>
          <div className="shrink-0 text-left sm:text-right">
            <p className="text-5xl font-semibold tabular-nums leading-none text-[var(--ink)]">
              {report.total_score.toFixed(1)}
            </p>
            <p className="mt-1.5 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
              Overall score / 100
            </p>
          </div>
        </div>
      </Surface>

      {report.summary ? (
        <Surface className="p-5 sm:p-6">
          <p className="text-xs font-semibold uppercase tracking-[var(--tracking-overline)] text-[var(--muted)]">
            Summary
          </p>
          <p className="mt-2 text-sm leading-relaxed text-[var(--ink)]">{report.summary}</p>
        </Surface>
      ) : null}

      {/* Rubric breakdown — the four live dimensions first, in rubric order as
          returned, so an older rubric renders under its own vocabulary. */}
      <Card
        title="Rubric breakdown"
        subtitle="Each dimension is scored out of 100 and weighted into the overall score."
        padding="md"
      >
        <div className="space-y-5">
          {report.dimensions.map((dimension) => (
            <div key={dimension.dimension}>
              <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                <span className="text-sm font-medium text-[var(--ink)]">
                  {DIMENSION_LABELS[dimension.dimension] ?? dimension.dimension}
                  <span className="ml-2 text-xs font-normal text-[var(--muted)]">
                    {(dimension.weight * 100).toFixed(0)}% weight
                  </span>
                </span>
                <span className="tabular-nums text-sm font-semibold text-[var(--ink)]">
                  {dimension.score.toFixed(0)}
                  <span className="font-normal text-[var(--muted)]"> / 100</span>
                </span>
              </div>
              <ScoreBar score={dimension.score} />
              {dimension.evidence ? (
                <p className="mt-1.5 text-xs leading-relaxed text-[var(--slate)]">
                  {dimension.evidence}
                </p>
              ) : null}
              {/* Surfaced rather than folded into the score: "70, and we are
                  sure" and "70, and we are guessing" are different findings.
                  Confidence is 0-100, the same scale as the score. */}
              {dimension.confidence < 70 ? (
                <p className="mt-1 text-xs italic text-[var(--slate)]">
                  Lower confidence — the conversation gave limited evidence for this one.
                </p>
              ) : null}
            </div>
          ))}
        </div>
      </Card>

      {report.strengths.length > 0 || report.concerns.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {report.strengths.length > 0 ? (
            <Card title="Strengths" padding="md">
              <ul className="space-y-2.5">
                {report.strengths.map((item) => (
                  <li key={item} className="flex gap-2.5 text-sm leading-relaxed text-[var(--slate)]">
                    <ThumbsUp size={15} className="mt-0.5 shrink-0 text-[var(--blue)]" aria-hidden="true" />
                    {item}
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}
          {report.concerns.length > 0 ? (
            <Card title="Areas for improvement" padding="md">
              <ul className="space-y-2.5">
                {report.concerns.map((item) => (
                  <li key={item} className="flex gap-2.5 text-sm leading-relaxed text-[var(--slate)]">
                    <TrendingUp size={15} className="mt-0.5 shrink-0 text-[var(--blue)]" aria-hidden="true" />
                    {item}
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <ClaimList
          title="Verified against your code"
          note="What you said, and the analysis agreed with."
          claims={report.verified_claims}
          tone="text-[var(--verified)]"
          icon={<Check size={15} className="mt-0.5 shrink-0" />}
        />
        <ClaimList
          title="The analysis disagreed"
          note="The stored analysis says otherwise. Worth a second look."
          claims={report.contradicted_claims}
          tone="text-[var(--failed)]"
          icon={<AlertTriangle size={15} className="mt-0.5 shrink-0" />}
        />
        <ClaimList
          title="Nothing found either way"
          note="Not wrong — the analysis simply had no evidence about these. Uncommitted or unanalysed work lands here."
          claims={report.unsupported_claims}
          tone="text-[var(--flagged)]"
          icon={<Minus size={15} className="mt-0.5 shrink-0" />}
        />
      </div>

      <details className="rounded-[var(--r-lg)] border border-[var(--rule)] bg-[var(--panel)] p-5 sm:p-6">
        <summary className="cursor-pointer select-none text-sm font-medium text-[var(--ink)]">
          Full transcript ({report.transcript.length} turns)
        </summary>
        <div className="mt-5 space-y-4 border-t border-[var(--rule-soft)] pt-5">
          {report.transcript.map((turn) => (
            <div key={turn.id}>
              <p className="mb-0.5 flex flex-wrap items-baseline gap-x-2 text-[11px] font-medium uppercase tracking-wide text-[var(--muted)]">
                <span>{turn.role === "interviewer" ? "Interviewer" : "You"}</span>
                <span className="machine normal-case tracking-normal text-[var(--muted)]">
                  {new Date(turn.spoken_at).toLocaleTimeString()}
                </span>
              </p>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--ink)]">
                {turn.text}
              </p>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
