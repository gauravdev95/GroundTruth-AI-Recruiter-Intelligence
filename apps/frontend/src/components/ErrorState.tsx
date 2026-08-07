import { AlertTriangle } from "lucide-react";
import type { ReactNode } from "react";

export interface ErrorStateProps {
  title?: string;
  description?: string;
  action?: ReactNode;
}

/**
 * Something went wrong — an operation that did not complete, which is exactly
 * what `--failed` names. Not `--flagged`: an amber panel here would tell the
 * reader their data is unverified rather than that a request failed, and those
 * two are the pair this product most needs to keep apart.
 *
 * Solid border, unlike `EmptyState`'s dashed one. A failure is a real state the
 * screen is in, not a space waiting to be filled.
 */
export function ErrorState({
  title = "Something went wrong",
  description = "Please try again, or come back later.",
  action,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-3 rounded-[var(--r-lg)] border border-[var(--failed)]/30 bg-[var(--failed)]/[0.06] px-6 py-14 text-center"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--failed)]/12 text-[var(--failed)]">
        <AlertTriangle size={22} aria-hidden="true" />
      </div>
      <div>
        <p className="text-sm font-semibold text-[var(--ink)]">{title}</p>
        <p className="mt-1 text-sm text-[var(--slate)]">{description}</p>
      </div>
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}
