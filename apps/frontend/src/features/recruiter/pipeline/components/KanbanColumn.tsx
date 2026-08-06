import { useDroppable } from "@dnd-kit/core";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import type { DropZoneId } from "../lib/columns";

/**
 * One drop target. The board has six of these across five columns — the
 * closed column splits into Offer and Closed, because dropping a candidate
 * into "offer" and dropping them into "closed" are opposite decisions and a
 * single target would have to guess which one a recruiter meant.
 *
 * `isAllowed` is computed by the board from the dragged card's status against
 * `ALLOWED_MOVES`, and drives both the visual state and `disabled`. A zone
 * that cannot accept the current card does not light up and does not register
 * a drop — the alternative is a drop that appears to work and then 409s,
 * which teaches recruiters not to trust the board.
 */
export function DropZone({
  id,
  isAllowed,
  isDraggingAny,
  className,
  children,
}: {
  id: DropZoneId;
  isAllowed: boolean;
  isDraggingAny: boolean;
  className?: string;
  children: ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id, disabled: !isAllowed });

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "rounded-lg transition",
        isDraggingAny && isAllowed
          ? "outline-dashed outline-1 outline-offset-2 outline-gt-electric/30"
          : null,
        isOver && isAllowed ? "bg-gt-electric/5 outline-gt-electric" : null,
        className,
      )}
    >
      {children}
    </div>
  );
}

export interface KanbanColumnProps {
  header: string;
  count: number;
  /** Shown under the header when the column is empty. */
  emptyHint: string;
  children: ReactNode;
  /** Rendered between the header and the cards — the closed column's
   * sub-headings use it. */
  className?: string;
}

export function KanbanColumn({ header, count, emptyHint, children, className }: KanbanColumnProps) {
  return (
    <section
      aria-label={header}
      className={cn(
        // Fixed width, not flexible: a Kanban column that grows to fill the
        // viewport puts two cards on a row at 1600px, which is not a column.
        "flex w-[272px] shrink-0 flex-col rounded-xl border border-rule bg-panel",
        className,
      )}
    >
      <header className="flex items-center justify-between gap-2 border-b border-rule px-3 py-2.5">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{header}</h2>
        <span className="tabular rounded-full bg-ink/5 px-1.5 py-0.5 text-[11px] font-medium text-slate-600">
          {count}
        </span>
      </header>

      <div className="flex-1 space-y-2 overflow-y-auto p-2">
        {count === 0 ? (
          <p className="rounded-lg border border-dashed border-rule px-3 py-6 text-center text-[11px] leading-relaxed text-slate-400">
            {emptyHint}
          </p>
        ) : null}
        {children}
      </div>
    </section>
  );
}
