import { CircleCheck, CircleHelp } from "lucide-react";

/**
 * The per-field confidence badge on the resume review screen.
 *
 * WHAT THIS BADGE IS, AND WHAT IT IS CAREFULLY NOT
 *
 * It reports how the *parser* found a value — not whether the value is true.
 * That distinction is the reason this component does not reuse
 * `VerificationBadge` and does not use the `--verified` token, even though
 * "high confidence" is green-shaped in every designer's instinct.
 *
 * `--verified` means "proven by an artefact": a repository that was fetched
 * and analysed, a GitHub account that was resolved against the API. Nothing
 * on the resume review screen has been proven by anything. The document is a
 * self-reported claim, and a high-confidence reading of a self-reported claim
 * is still a self-reported claim — the parser is confident it read the text
 * correctly, which says nothing about whether the text is honest.
 *
 * Spending green here would put the same visual token on "we read this
 * clearly" and "we checked this with GitHub", and a student who learned the
 * badge on this screen would misread every badge afterwards. So confidence
 * uses `--blue` (a brand colour, no semantic load) and `--flagged` amber,
 * which already means "claimed, unchecked" — exactly right for a field the
 * parser wants a human to glance at.
 *
 * The band is server-computed (`confidence.py::Scored.band`). It is never
 * re-derived from the raw score here: one threshold, defined once, beside
 * the provenance table it is measured against.
 */

export type ConfidenceBand = "high" | "review";

interface ConfidenceBadgeProps {
  band: ConfidenceBand;
  /** From `Scored.evidence` — "Found under 'EDUCATION'". Becomes the tooltip. */
  evidence?: string;
  /** Icon-only, for dense list rows where a label would wrap. */
  compact?: boolean;
}

export function ConfidenceBadge({ band, evidence, compact = false }: ConfidenceBadgeProps) {
  const isHigh = band === "high";
  const Icon = isHigh ? CircleCheck : CircleHelp;

  // The accessible name is the full sentence, not the visual label: a screen
  // reader user hearing only "Check" learns nothing, and this badge's entire
  // purpose is to direct attention.
  const label = isHigh ? "Read clearly from your resume" : "Worth a quick check";
  const title = evidence ? `${label} — ${evidence}` : label;

  return (
    <span
      className={[
        "inline-flex shrink-0 items-center gap-1 rounded-[var(--r-full)] border px-2 py-0.5",
        "text-[11px] font-medium leading-none",
        isHigh
          ? "border-[var(--blue)]/25 bg-[var(--blue)]/10 text-[var(--blue)]"
          : "border-[var(--flagged)]/30 bg-[var(--flagged)]/10 text-[var(--flagged)]",
      ].join(" ")}
      title={title}
    >
      <Icon size={11} aria-hidden="true" />
      {compact ? <span className="sr-only">{label}</span> : <span>{isHigh ? "Clear" : "Check"}</span>}
    </span>
  );
}

/**
 * Section-level roll-up: how many fields in this section want a look.
 *
 * Shows nothing at all when every field is clear. An always-present badge
 * reading "0 to check" is noise that trains the student to ignore the badge
 * they need to notice — absence is the strongest possible "nothing here".
 */
export function SectionConfidenceSummary({ reviewCount }: { reviewCount: number }) {
  if (reviewCount === 0) return null;

  return (
    <span className="inline-flex items-center gap-1.5 rounded-[var(--r-full)] bg-[var(--flagged)]/10 px-2.5 py-1 text-[11px] font-medium text-[var(--flagged)]">
      <CircleHelp size={11} aria-hidden="true" />
      {reviewCount} to check
    </span>
  );
}
