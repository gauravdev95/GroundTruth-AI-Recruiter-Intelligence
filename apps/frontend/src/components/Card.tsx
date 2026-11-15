import type { ReactNode } from "react";

import { Surface } from "@/design/Surface";
import { cn } from "@/lib/utils";

export interface CardProps {
  children: ReactNode;
  /** Card title, set in the display face. Omit for a bare card. */
  title?: string;
  subtitle?: string;
  /** Actions at the top-right of the header (a menu, a link, a button). */
  actions?: ReactNode;
  /** `flat` is the default (hairline, no shadow); `raised` for the primary
   * object on a screen. See `Surface` for why there are only three. */
  elevation?: "flat" | "raised";
  /** Lifts and brightens the hairline on hover. Only for cards that are links. */
  interactive?: boolean;
  selected?: boolean;
  /** Inner padding. `md` is the default; `none` is for cards whose content
   * supplies its own (a table, a chart). */
  padding?: "none" | "sm" | "md" | "lg";
  className?: string;
}

/**
 * The card, as a convenience over `Surface` — it is not a second card
 * implementation. The barrel used to carry a `Card` that was one (white,
 * slate-bordered, zero call sites) and it was deleted; this one renders
 * `Surface` and adds only the header/body structure screens repeat, so the
 * translucency, hairline and elevation decisions stay in exactly one place.
 *
 * Use `<Surface>` directly when the card has no header or needs a different
 * element (`article`, `li`, `label`); use `<Card>` when it has a title and
 * actions, which is most dashboard cards.
 */
export function Card({
  children,
  title,
  subtitle,
  actions,
  elevation = "flat",
  interactive = false,
  selected = false,
  padding = "md",
  className,
}: CardProps) {
  const paddingClass =
    padding === "none" ? "" : padding === "sm" ? "p-4" : padding === "lg" ? "p-8" : "p-6";

  return (
    <Surface
      elevation={elevation}
      interactive={interactive}
      selected={selected}
      className={cn(paddingClass, className)}
    >
      {title || actions ? (
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title ? (
              <h3 className="font-display text-base font-semibold tracking-tight text-[var(--ink)]">
                {title}
              </h3>
            ) : null}
            {subtitle ? <p className="mt-0.5 text-sm text-[var(--slate)]">{subtitle}</p> : null}
          </div>
          {actions ? <div className="shrink-0">{actions}</div> : null}
        </div>
      ) : null}
      {children}
    </Surface>
  );
}

/** A footer strip inside a `Card` with `padding="none"` — a hairline above,
 * muted text, room for a link or a count. */
export function CardFooter({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "border-t border-[var(--rule-soft)] px-6 py-3 text-sm text-[var(--slate)]",
        className,
      )}
    >
      {children}
    </div>
  );
}
