import type { VerificationStage, VerificationStageKind, VerificationStageStatus } from "../api/profileApi";

/**
 * The seven-stage verification pipeline as a compact strip.
 *
 * `verification_status` alone says only where a repository *ended up*.
 * This says how far it got and which stage stopped it — the difference
 * between "unverified" and "unverified because the authorship check decided
 * this isn't your code", which is the one thing a student in that position
 * actually needs to know.
 *
 * Ordering comes from the server's `sequence` (derived from
 * `STAGE_SEQUENCE`, so the run order lives in exactly one place and cannot
 * drift between the two ends). Nothing is re-sorted by name here.
 */

const STAGE_LABELS: Record<VerificationStageKind, string> = {
  repository_selection: "Repository",
  fork_authorship_check: "Authorship",
  contribution_analysis: "Contribution",
  architecture_code_quality: "Code quality",
  technology_detection: "Technologies",
  code_grounded_interview: "Interview",
  evidence_report: "Evidence report",
};

/** `skipped` is muted rather than red: those stages never ran, and colouring
 * them as failures would attribute a problem to code that never executed. */
const STATUS_STYLES: Record<VerificationStageStatus, { dot: string; text: string }> = {
  succeeded: { dot: "bg-[var(--verified)]", text: "text-[var(--verified)]" },
  running: { dot: "bg-[var(--violet)] animate-pulse", text: "text-[var(--ink)]" },
  failed: { dot: "bg-[var(--failed)]", text: "text-[var(--failed)]" },
  skipped: { dot: "bg-[var(--rule)]", text: "text-[var(--muted)]" },
  pending: { dot: "bg-[var(--rule)]", text: "text-[var(--muted)]" },
};

const STATUS_WORDS: Record<VerificationStageStatus, string> = {
  succeeded: "passed",
  running: "in progress",
  failed: "failed",
  skipped: "skipped — an earlier stage stopped the run",
  pending: "not started",
};

export function StageTimeline({ stages }: { stages: VerificationStage[] }) {
  if (stages.length === 0) return null;

  const ordered = [...stages].sort((a, b) => a.sequence - b.sequence);
  // The first stage that actually stopped the run, if any. Named under the
  // strip because a row of coloured dots can show *that* something failed but
  // not *why*, and the reason is already on the row.
  const blocking = ordered.find((stage) => stage.status === "failed");

  return (
    <div className="mt-3 border-t border-[var(--rule)] pt-3">
      <ol className="flex items-center gap-1" aria-label="Verification pipeline">
        {ordered.map((stage, index) => {
          const styles = STATUS_STYLES[stage.status];
          return (
            <li key={stage.stage} className="flex flex-1 items-center gap-1">
              <span
                className={`h-1.5 w-1.5 shrink-0 rounded-full ${styles.dot}`}
                title={`${STAGE_LABELS[stage.stage]} — ${STATUS_WORDS[stage.status]}`}
                aria-hidden="true"
              />
              {/* The connector, not a stage: rendered for every gap between
                  two dots and never after the last one. */}
              {index < ordered.length - 1 ? (
                <span className={`h-px flex-1 ${styles.dot} opacity-40`} aria-hidden="true" />
              ) : null}
              <span className="sr-only">
                {STAGE_LABELS[stage.stage]}: {STATUS_WORDS[stage.status]}
              </span>
            </li>
          );
        })}
      </ol>

      <p className={`mt-1.5 text-[11px] ${blocking ? STATUS_STYLES.failed.text : "text-[var(--muted)]"}`}>
        {blocking
          ? `${STAGE_LABELS[blocking.stage]}: ${blocking.error ?? "did not pass"}`
          : summarise(ordered)}
      </p>
    </div>
  );
}

function summarise(stages: VerificationStage[]): string {
  const passed = stages.filter((stage) => stage.status === "succeeded").length;
  const running = stages.find((stage) => stage.status === "running");
  if (running) return `Running: ${STAGE_LABELS[running.stage]}`;
  return `${passed} of ${stages.length} stages passed`;
}
