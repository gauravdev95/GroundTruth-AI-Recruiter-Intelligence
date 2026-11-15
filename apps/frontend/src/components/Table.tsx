import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import type { ReactNode, ThHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/**
 * The data table. Primitives, not a data grid: the product's tables are
 * small (applications, candidates, jobs) and each one owns its own fetching,
 * so the table supplies structure and sorting chrome and nothing else — no
 * built-in pagination (see `Pagination`), no built-in fetching, no invented
 * rows.
 *
 * Structure is a real `<table>`: screen readers get the row/column
 * relationships for free, and a CSS grid that looks like a table does not
 * give them up. The wrapper scrolls horizontally on narrow screens rather
 * than squeezing columns into unreadability.
 *
 * Sorting is a header-cell concern only: `TableHeaderCell` with `sort`
 * renders the direction icon and `aria-sort` on the `<th>`; the owning
 * screen still sorts its own rows.
 */

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("w-full overflow-x-auto", className)}>
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  );
}

export function TableHead({ children }: { children: ReactNode }) {
  return (
    <thead>
      <tr className="border-b border-[var(--rule)] text-left">{children}</tr>
    </thead>
  );
}

export function TableBody({ children }: { children: ReactNode }) {
  return <tbody>{children}</tbody>;
}

export function TableRow({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <tr
      className={cn(
        "border-b border-[var(--rule-soft)] last:border-b-0 [&:hover]:bg-[var(--panel)]/60",
        className,
      )}
    >
      {children}
    </tr>
  );
}

export type SortDirection = "asc" | "desc" | null;

export interface TableHeaderCellProps extends ThHTMLAttributes<HTMLTableCellElement> {
  /** Current sort direction for this column, or `null` when unsorted. */
  sort?: SortDirection;
  /** Called when the header is activated. Omit for an unsortable column. */
  onSort?: () => void;
}

export function TableHeaderCell({ children, sort, onSort, className, ...props }: TableHeaderCellProps) {
  const Icon = sort === "asc" ? ArrowUp : sort === "desc" ? ArrowDown : ChevronsUpDown;

  return (
    <th
      aria-sort={
        sort === "asc" ? "ascending" : sort === "desc" ? "descending" : undefined
      }
      className={cn(
        "px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]",
        className,
      )}
      {...props}
    >
      {onSort ? (
        <button
          type="button"
          onClick={onSort}
          className="inline-flex items-center gap-1.5 transition-colors hover:text-[var(--ink)]"
        >
          {children}
          <Icon size={14} aria-hidden="true" className={sort ? "text-[var(--ink)]" : ""} />
        </button>
      ) : (
        children
      )}
    </th>
  );
}

export function TableCell({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <td className={cn("px-4 py-3 align-middle text-[var(--ink)]", className)}>{children}</td>;
}

/** Machine-extracted or measured cell content — scores, timestamps, IDs — set
 * in JetBrains Mono per the semantic mono rule (tokens.css). */
export function TableCellMono({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <TableCell className={cn("machine tabular", className)}>{children}</TableCell>
  );
}
