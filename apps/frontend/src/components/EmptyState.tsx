import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}

/**
 * Nothing here yet — which is a different thing from something went wrong, and
 * is why this and `ErrorState` do not share an implementation.
 *
 * The dashed border is the whole distinction, and it is deliberate: every real
 * surface in the product is bounded by a solid `--rule` hairline, so a dashed
 * outline reads as a space where content will go rather than as a card that
 * happens to be empty.
 */
export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-[var(--r-lg)] border border-dashed border-[var(--rule)] bg-[var(--panel)]/40 px-6 py-14 text-center">
      {Icon ? (
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--panel-raised)] text-[var(--muted)]">
          <Icon size={22} aria-hidden="true" />
        </div>
      ) : null}
      <div>
        <p className="text-sm font-semibold text-[var(--ink)]">{title}</p>
        {description ? <p className="mt-1 text-sm text-[var(--slate)]">{description}</p> : null}
      </div>
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}
