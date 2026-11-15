import { ChevronLeft, ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";

export interface PaginationProps {
  /** 1-indexed current page. */
  page: number;
  /** Total pages. `0` or `1` renders nothing — a pager for one page is noise. */
  totalPages: number;
  onChange: (page: number) => void;
  /** How many page numbers to show on each side of the current page. */
  siblings?: number;
  className?: string;
}

/**
 * The pager. Controlled and dumb: it owns no fetching, no page size, no
 * URL — the screen that renders it owns the data and passes `page` /
 * `totalPages` back in. That split is what keeps a pager honest: a pager
 * that fetches its own page will eventually fetch a page the list above it
 * no longer agrees with.
 *
 * The window is `1 … p-1 p p+1 … N`: the first and last pages are always
 * reachable in one click, and the ellipsis is a real element (`aria-hidden`)
 * rather than a disabled button pretending to be one. The current page is
 * `aria-current="page"` — a screen reader announces "page 3, current page"
 * instead of just "3".
 */
export function Pagination({ page, totalPages, onChange, siblings = 1, className }: PaginationProps) {
  if (totalPages <= 1) return null;

  const pages: Array<number | "gap-start" | "gap-end"> = [];
  const start = Math.max(2, page - siblings);
  const end = Math.min(totalPages - 1, page + siblings);

  pages.push(1);
  if (start > 2) pages.push("gap-start");
  for (let p = start; p <= end; p++) pages.push(p);
  if (end < totalPages - 1) pages.push("gap-end");
  if (totalPages > 1) pages.push(totalPages);

  const go = (next: number) => {
    if (next < 1 || next > totalPages || next === page) return;
    onChange(next);
  };

  const pageButton = (p: number) => (
    <button
      key={p}
      type="button"
      onClick={() => go(p)}
      aria-current={p === page ? "page" : undefined}
      aria-label={p === page ? `Page ${p}, current page` : `Go to page ${p}`}
      className={cn(
        "flex h-9 min-w-9 items-center justify-center rounded-[var(--r-sm)] px-2 text-sm font-medium tabular transition-colors duration-150",
        p === page
          ? "bg-[var(--violet)] text-white"
          : "text-[var(--slate)] hover:bg-[var(--panel)] hover:text-[var(--ink)]",
      )}
    >
      {p}
    </button>
  );

  return (
    <nav aria-label="Pagination" className={cn("flex items-center gap-1", className)}>
      <button
        type="button"
        onClick={() => go(page - 1)}
        disabled={page <= 1}
        aria-label="Previous page"
        className="flex h-9 w-9 items-center justify-center rounded-[var(--r-sm)] text-[var(--slate)] transition-colors duration-150 hover:bg-[var(--panel)] hover:text-[var(--ink)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        <ChevronLeft size={16} aria-hidden="true" />
      </button>
      {pages.map((entry) =>
        entry === "gap-start" || entry === "gap-end" ? (
          <span
            key={entry}
            aria-hidden="true"
            className="px-1 text-sm text-[var(--muted)]"
          >
            …
          </span>
        ) : (
          pageButton(entry)
        ),
      )}
      <button
        type="button"
        onClick={() => go(page + 1)}
        disabled={page >= totalPages}
        aria-label="Next page"
        className="flex h-9 w-9 items-center justify-center rounded-[var(--r-sm)] text-[var(--slate)] transition-colors duration-150 hover:bg-[var(--panel)] hover:text-[var(--ink)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        <ChevronRight size={16} aria-hidden="true" />
      </button>
    </nav>
  );
}
