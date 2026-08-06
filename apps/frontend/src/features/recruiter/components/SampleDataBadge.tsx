import { FlaskConical } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Marks a surface whose contents did not come from the API.
 *
 * There is exactly one rule about placeholder candidates in this product:
 * they are never allowed to look real. A recruiter who cannot tell a seeded
 * card from a matched one will eventually message one of them, and a hiring
 * tool that fabricates people is not recoverable from. So every sample card
 * carries this, in `--flagged` — the same amber that means "claimed,
 * unchecked" everywhere else in the product, which is precisely what a
 * sample candidate is.
 *
 * Rendered from a runtime flag, not stripped at build time: a badge that only
 * exists in development is a badge that is missing from the one build where
 * showing sample data would actually matter.
 */
export function SampleDataBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-flagged/40 bg-flagged/10 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-flagged",
        className,
      )}
    >
      <FlaskConical size={10} aria-hidden="true" />
      Sample data
    </span>
  );
}
