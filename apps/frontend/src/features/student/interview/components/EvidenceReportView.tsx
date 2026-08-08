import { CheckCircle2 } from "lucide-react";

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

function ScoreBar({ score }: { score: number }) {
  return (
    <div className="h-1.5 w-full rounded-full bg-[var(--panel-raised)]">
      <div
        className="h-1.5 rounded-full bg-[var(--verified)]"
        style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
      />
    </div>
  );
}

/** Claim lists carry their own meaning, so they carry their own framing.
 * "Unsupported" is deliberately not styled as a failure: the analysis simply
 * had nothing to say either way, which uncommitted or unanalysed work explains
 * perfectly well. Only "contradicted" means the evidence disagreed. */
function ClaimList({ title, claims, note, tone }: { title: string; claims: string[]; note: string; tone: string }) {
  if (claims.length === 0) return null;
  return (
    <div className="rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-5">
      <p className="text-sm font-medium text-[var(--ink)]">{title}</p>
      <p className="mb-3 text-xs text-[var(--slate)]">{note}</p>
      <ul className="space-y-1.5">
        {claims.map((claim) => (
          <li key={claim} className="flex gap-2 text-sm text-[var(--slate)]">
            <span aria-hidden="true" className={tone}>
              •
            </span>
            <span>{claim}</span>
          </li>
        ))}
      </ul>
    </div>
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
 */
export function EvidenceReportView({ report }: { report: EvidenceReport }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 rounded-2xl border border-[var(--verified)]/30 bg-[var(--verified)]/10 p-6">
        <div className="flex items-center gap-3">
          <CheckCircle2 size={24} className="text-[var(--verified)]" aria-hidden="true" />
          <div>
            <p className="text-sm font-medium text-[var(--ink)]">Interview complete</p>
            <p className="text-xs text-[var(--slate)]">
              Completed {new Date(report.completed_at).toLocaleString()}
            </p>
          </div>
        </div>
        <p className="text-3xl font-semibold tabular-nums text-[var(--ink)]">{report.total_score.toFixed(1)}</p>
      </div>

      {report.summary ? (
        <div className="rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-5">
          <p className="text-sm leading-relaxed text-[var(--ink)]">{report.summary}</p>
        </div>
      ) : null}

      <div className="rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-5">
        <p className="mb-4 text-xs font-medium uppercase tracking-wide text-[var(--slate)]">
          Rubric
        </p>
        <div className="space-y-4">
          {report.dimensions.map((dimension) => (
            <div key={dimension.dimension}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="font-medium text-[var(--slate)]">
                  {DIMENSION_LABELS[dimension.dimension] ?? dimension.dimension}
                  <span className="ml-1.5 text-[var(--slate)]/70">
                    {(dimension.weight * 100).toFixed(0)}%
                  </span>
                </span>
                <span className="tabular-nums text-[var(--slate)]">{dimension.score.toFixed(0)}/100</span>
              </div>
              <ScoreBar score={dimension.score} />
              {dimension.evidence ? (
                <p className="mt-1.5 text-xs text-[var(--slate)]">{dimension.evidence}</p>
              ) : null}
              {/* Surfaced rather than folded into the score: "70, and we are
                  sure" and "70, and we are guessing" are different findings.
                  Confidence is 0-100, the same scale as the score. */}
              {dimension.confidence < 70 ? (
                <p className="mt-1 text-xs italic text-[var(--slate)]/80">
                  Lower confidence — the conversation gave limited evidence for this one.
                </p>
              ) : null}
            </div>
          ))}
        </div>
      </div>

      {report.strengths.length > 0 || report.concerns.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {report.strengths.length > 0 ? (
            <div className="rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-5">
              <p className="mb-2 text-sm font-medium text-[var(--ink)]">Strengths</p>
              <ul className="space-y-1.5 text-sm text-[var(--slate)]">
                {report.strengths.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {report.concerns.length > 0 ? (
            <div className="rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-5">
              <p className="mb-2 text-sm font-medium text-[var(--ink)]">Where it was weaker</p>
              <ul className="space-y-1.5 text-sm text-[var(--slate)]">
                {report.concerns.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      <ClaimList
        title="Verified against your code"
        note="What you said, and the analysis agreed with."
        claims={report.verified_claims}
        tone="text-[var(--verified)]"
      />
      <ClaimList
        title="The analysis disagreed"
        note="The stored analysis says otherwise. Worth a second look."
        claims={report.contradicted_claims}
        tone="text-[var(--failed)]"
      />
      <ClaimList
        title="Nothing found either way"
        note="Not wrong — the analysis simply had no evidence about these. Uncommitted or unanalysed work lands here."
        claims={report.unsupported_claims}
        tone="text-[var(--flagged)]"
      />

      <details className="rounded-2xl border border-[var(--rule)] bg-[var(--panel)] p-5">
        <summary className="cursor-pointer select-none text-sm font-medium text-[var(--ink)]">
          Full transcript ({report.transcript.length} turns)
        </summary>
        <div className="mt-4 space-y-3">
          {report.transcript.map((turn) => (
            <div key={turn.id}>
              <p className="mb-0.5 text-xs font-medium uppercase tracking-wide text-[var(--slate)]">
                {turn.role === "interviewer" ? "Interviewer" : "You"}
              </p>
              <p className="whitespace-pre-wrap text-sm text-[var(--ink)]">{turn.text}</p>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
