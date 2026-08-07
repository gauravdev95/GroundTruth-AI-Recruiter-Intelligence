import { cn } from "@/lib/utils";

/**
 * A match score, colour-coded by band.
 *
 * **The bands are blue and grey only.** Red and green are spent exclusively
 * on the two pipeline outcomes — hired and rejected — and a score is not an
 * outcome. A 94% painted green would tell a recruiter scanning a column that
 * a decision had already been made about that candidate, and a 55% painted
 * red would tell them the system had rejected someone it is not allowed to
 * reject (`domains/pipeline/service.py::transition_status`: every rejection
 * is a recruiter action). The bands are a reading aid, not a verdict.
 *
 * The two blue bands share one hue and differ in weight rather than in
 * colour, because #2563EB *is* Tailwind's `blue-600` — asking for "solid
 * electric blue" above 90 and "blue-600" from 70 to 89 is one value, and the
 * only honest way to separate them on screen is emphasis.
 */

const STRONG = 90;
const GOOD = 70;

function bandClass(score: number): string {
  if (score >= STRONG) return "text-gt-electric font-semibold";
  if (score >= GOOD) return "text-gt-electric font-medium";
  return "text-[var(--slate)] font-medium";
}

export interface MatchScoreProps {
  /** 0-100, as stored. Rendered whole — `match_score` is `Numeric(5,2)` but
   * no recruiter decision turns on its second decimal. */
  score: number | null;
  /** `sm` for a Kanban card, `lg` for the drawer header. */
  size?: "sm" | "lg";
  /** Appends " match". Off on dense surfaces where the column already says
   * what the number is. */
  withLabel?: boolean;
  className?: string;
}

export function MatchScore({ score, size = "sm", withLabel = true, className }: MatchScoreProps) {
  if (score === null) {
    // Not zero, and not hidden. A pruned `match_results` row means the live
    // score is unknown, which is a different claim from a low score — and the
    // card is still on the board because an application protects it.
    return (
      <span className={cn("tabular text-[var(--muted)]", size === "lg" ? "text-base" : "text-xs", className)}>
        no live score
      </span>
    );
  }

  return (
    <span
      className={cn(
        "tabular whitespace-nowrap",
        size === "lg" ? "text-base" : "text-xs",
        bandClass(score),
        className,
      )}
    >
      {Math.round(score)}%{withLabel ? " match" : ""}
    </span>
  );
}
