import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The small uppercase label above every section headline.
 *
 * Rendered as a `<p>` rather than a heading. It reads like a kicker, but it is
 * not a level in the document outline, and putting it in the outline would give
 * every section two headings for a screen-reader user to step through.
 */
export function Overline({
  children,
  tone = "light",
  className,
}: {
  children: ReactNode;
  tone?: "light" | "dark" | "accent" | "ember" | "wash";
  className?: string;
}) {
  return (
    <p
      className={cn(
        "font-sans text-gt-over font-medium uppercase",
        tone === "light" && "text-gt-slate",
        tone === "dark" && "text-gt-ash",
        tone === "accent" && "text-gt-electric",
        tone === "ember" && "text-gt-ember",
        tone === "wash" && "text-white/80",
        className,
      )}
    >
      {children}
    </p>
  );
}
