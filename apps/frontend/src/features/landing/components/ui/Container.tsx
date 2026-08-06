import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The page's one measure: 1280px, centred, with the gutter that keeps text off
 * the edge on a phone.
 *
 * Every section uses this and nothing sets its own max-width, so the left edge
 * of a headline in §01 lines up with the left edge of a headline in §12. That
 * alignment down the whole scroll is most of what makes a typography-led page
 * read as deliberate rather than as a stack of unrelated blocks.
 */
export function Container({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("mx-auto w-full max-w-[1280px] px-6 sm:px-8", className)}>{children}</div>
  );
}
