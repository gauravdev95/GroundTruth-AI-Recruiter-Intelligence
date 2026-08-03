/**
 * The page's status vocabulary, in one component.
 *
 * `--verified` and `--flagged` are a closed semantic pair: green means proven
 * by an artefact, amber means claimed but unchecked, and neither colour is used
 * for anything else anywhere on the page. Concentrating both in one component
 * is what keeps that true — a badge is the only way to spend either colour, so
 * a section cannot quietly borrow green for a score or an arrow.
 *
 * Colour is never the sole carrier. Every badge has a word, and the two glyphs
 * are deliberately different shapes rather than the same shape in two colours:
 * a filled check for verified, an open ring for flagged. The distinction
 * survives greyscale, colour blindness, and forced-colours mode.
 */

/** The flagged ring. Open, so it reads as "not closed out". */
export function Dot() {
  return (
    <svg width="7" height="7" viewBox="0 0 8 8" aria-hidden="true">
      <circle cx="4" cy="4" r="3" stroke="currentColor" strokeWidth="1.2" fill="none" />
    </svg>
  );
}

/** The verified check. */
export function Check() {
  return (
    <svg width="9" height="9" viewBox="0 0 10 10" aria-hidden="true">
      <path d="M1.5 5.2 L4 7.6 L8.5 2.4" stroke="currentColor" strokeWidth="1.5" fill="none" />
    </svg>
  );
}

interface StatusBadgeProps {
  /** `VERIFIED` renders green; every other status renders amber. */
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const verified = status === "VERIFIED";

  return (
    <span className={verified ? "badge badge-verified" : "badge badge-flagged"}>
      {verified ? <Check /> : <Dot />}
      {status}
    </span>
  );
}

interface NeutralBadgeProps {
  children: string;
}

/**
 * For labels that describe a requirement rather than a verification outcome —
 * MANDATORY, OPTIONAL, SCANNING. Outlined in `--rule` with `--slate` text, and
 * deliberately not part of the semantic pair: rendering "MANDATORY" in green
 * would claim something had been proven, and would dilute every real badge on
 * the page by making green mean two different things.
 */
export function NeutralBadge({ children }: NeutralBadgeProps) {
  return <span className="badge badge-neutral">{children}</span>;
}
