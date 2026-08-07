import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/**
 * The loading placeholder.
 *
 * The shimmer runs between `--panel-solid` and `--panel-raised` — two adjacent
 * steps of the app's own surface stack — rather than between two greys. On a
 * dark palette a slate-100/200 sweep is a bright bar travelling across the
 * page, which draws more attention than the content it stands in for.
 *
 * `--panel-solid`, not the translucent `--panel`: a skeleton that lets the
 * backdrop blooms through picks up their colour as it moves, and the shimmer
 * then reads as something loading *badly* rather than as a placeholder.
 */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-shimmer rounded-[var(--r-sm)] bg-[length:200%_100%]",
        "bg-gradient-to-r from-[var(--panel-solid)] via-[var(--panel-raised)] to-[var(--panel-solid)]",
        className,
      )}
      {...props}
    />
  );
}
