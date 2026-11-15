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

/**
 * A paragraph-shaped placeholder: `lines` bars, the last one shorter, like
 * text. Widths vary per line so the block reads as prose rather than as a
 * barcode — identical bars are the fastest way to make a skeleton look like
 * a rendering bug.
 */
export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div aria-hidden="true" className={cn("flex flex-col gap-2", className)}>
      {Array.from({ length: Math.max(1, lines) }, (_, index) => (
        <Skeleton
          key={index}
          className={cn("h-3.5", index === lines - 1 ? "w-2/3" : "w-full")}
        />
      ))}
    </div>
  );
}

/**
 * A card-shaped placeholder: a title bar, two text lines and a footer bar,
 * on the same `--panel` a real card would sit on. For dashboards and lists,
 * where a bare rectangle the size of a card still leaves the reader guessing
 * at the layout that is coming.
 */
export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "rounded-[var(--r-lg)] border border-[var(--rule)] bg-[var(--panel)] p-5",
        className,
      )}
    >
      <Skeleton className="h-4 w-1/3" />
      <div className="mt-4">
        <SkeletonText lines={2} />
      </div>
      <Skeleton className="mt-4 h-8 w-24" />
    </div>
  );
}
