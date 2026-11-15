import { cloneElement, isValidElement, useId, useState } from "react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface TooltipProps {
  /** The text the tooltip shows. Keep it short — a sentence, not a paragraph.
   * Anything longer belongs in the page, not hovering over it. */
  content: string;
  children: ReactNode;
  /** Where the bubble sits relative to its trigger. `top` is the default;
   * use `bottom` for triggers at the top of the viewport. */
  placement?: "top" | "bottom" | "left" | "right";
  className?: string;
}

/**
 * The hint bubble. CSS-only: it appears on hover and on focus-within, so
 * keyboard users get it without a JS positioning layer, and there is no
 * popover to leak, misplace, or leave open after unmount.
 *
 * The trade-off is stated once: this is not a replacement for a popover
 * (`Dropdown`) — it cannot hold interactive content, and it is clipped by
 * an `overflow-hidden` ancestor exactly like any absolutely positioned
 * element. Its content is plain text, announced via `aria-describedby`, so a
 * screen reader reads the hint when the trigger is focused rather than
 * needing the bubble to exist.
 *
 * The bubble is `--panel-raised` and opaque, like every floating surface,
 * and small (`--r-sm`, `--shadow-sm`): a tooltip is a whisper, and a large
 * translucent one over content is a shout.
 */
export function Tooltip({ content, children, placement = "top", className }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const tooltipId = useId();

  const placementClasses = {
    top: "bottom-full left-1/2 mb-2 -translate-x-1/2",
    bottom: "left-1/2 top-full mt-2 -translate-x-1/2",
    left: "right-full top-1/2 mr-2 -translate-y-1/2",
    right: "left-full top-1/2 ml-2 -translate-y-1/2",
  } as const;

  return (
    <span
      className={cn("group/tooltip relative inline-flex", className)}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {/*
        The description belongs on the trigger itself, not on this wrapper:
        a screen reader announces `aria-describedby` for the focused element,
        and the wrapper is never focused. The clone adds only that one
        attribute — the child's own props, handlers and ref are untouched.
        Non-element children (plain text) cannot carry it, and fall back to
        the wrapper, which is the best that shape allows.
      */}
      {isValidElement(children)
        ? cloneElement(children, { "aria-describedby": tooltipId })
        : children}
      {visible ? (
        <span
          id={tooltipId}
          role="tooltip"
          className={cn(
            "pointer-events-none absolute z-50 w-max max-w-64 animate-fade-in whitespace-normal rounded-[var(--r-sm)] border border-[var(--rule)] bg-[var(--panel-raised)] px-2.5 py-1.5 text-xs leading-snug text-[var(--ink)] shadow-sm",
            placementClasses[placement],
          )}
        >
          {content}
        </span>
      ) : null}
    </span>
  );
}
