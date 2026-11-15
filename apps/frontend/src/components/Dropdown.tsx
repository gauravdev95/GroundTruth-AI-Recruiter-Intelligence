import type { LucideIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface DropdownItem {
  id: string;
  label: string;
  icon?: LucideIcon;
  /** Rendered in `--failed`. For destructive actions only — the same
   * borrowing `buttonVariants` documents: the token means "an operation did
   * not complete", this means "an action that destroys something", and they
   * share a colour rather than minting a second red. */
  danger?: boolean;
  disabled?: boolean;
  onSelect: () => void;
}

export type DropdownEntry = DropdownItem | { type: "separator"; id: string };

export interface DropdownTriggerProps {
  "aria-haspopup": "menu";
  "aria-expanded": boolean;
  onClick: () => void;
  onKeyDown: (event: React.KeyboardEvent) => void;
  ref: (node: HTMLElement | null) => void;
}

export interface DropdownProps {
  /**
   * The control that opens the menu, as a render prop so the menu can hand
   * it its wiring (`aria-haspopup`, `aria-expanded`, toggle, keyboard) without
   * cloning — cloning would swallow the trigger's own focus ring or double
   * its onClick. Usually a `Button` or an icon button; spread the props
   * onto it.
   */
  trigger: (props: DropdownTriggerProps) => ReactNode;
  items: DropdownEntry[];
  /** Which edge the menu aligns to. `end` is for triggers at the right edge
   * of a header, where a `start`-aligned menu would overflow the viewport. */
  align?: "start" | "end";
  className?: string;
}

/**
 * The menu. One component for every "more actions" surface in the product —
 * the recruiter pipeline's per-application menu, the dashboard header's user
 * menu, the Kanban card menu — so they stop being hand-rolled `<div>`s with
 * different keyboard behaviour.
 *
 * Keyboard: Down/Up move between items (skipping separators and disabled
 * items), Enter/Space activate, Escape closes and returns focus to the
 * trigger, Tab closes. The menu is positioned in-flow (absolute, inside a
 * relative wrapper) rather than portalled: every current call site sits in
 * normal flow, and a portal would trade one positioning problem for a
 * scroll-and-resize one. Do not use this inside an `overflow-hidden` ancestor
 * without checking the menu is not clipped — that is the one case where the
 * in-flow choice shows.
 *
 * The menu surface is `--panel-raised` and opaque, like every floating
 * surface: a translucent menu over scrolled content is unreadable rather
 * than airy.
 */
export function Dropdown({ trigger, items, align = "start", className }: DropdownProps) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const selectable = items.filter(
    (entry): entry is DropdownItem => !("type" in entry) && !entry.disabled,
  );

  useEffect(() => {
    if (!open) return;

    const onPointerDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
        setActiveIndex(-1);
      }
    };

    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  useEffect(() => {
    if (!open || activeIndex < 0) return;
    itemRefs.current[activeIndex]?.focus();
  }, [open, activeIndex]);

  const close = () => {
    setOpen(false);
    setActiveIndex(-1);
    triggerRef.current?.focus();
  };

  const move = (direction: 1 | -1) => {
    if (selectable.length === 0) return;
    const current = activeIndex < 0 ? (direction === 1 ? -1 : 0) : activeIndex;
    setActiveIndex((current + direction + selectable.length) % selectable.length);
  };

  const onTriggerKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setOpen(true);
      setActiveIndex(0);
    }
  };

  const onMenuKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      move(1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      move(-1);
    } else if (event.key === "Tab") {
      setOpen(false);
      setActiveIndex(-1);
    }
  };

  return (
    <div ref={rootRef} className={cn("relative inline-block", className)}>
      {trigger({
        "aria-haspopup": "menu",
        "aria-expanded": open,
        onClick: () => {
          setOpen((wasOpen) => !wasOpen);
          setActiveIndex(-1);
        },
        onKeyDown: onTriggerKeyDown,
        ref: (node) => {
          triggerRef.current = node;
        },
      })}
      {open ? (
        <div
          role="menu"
          onKeyDown={onMenuKeyDown}
          className={cn(
            "absolute z-50 mt-2 w-56 animate-scale-in rounded-[var(--r-md)] border border-[var(--rule)] bg-[var(--panel-raised)] p-1.5 shadow-sm",
            align === "end" ? "right-0" : "left-0",
          )}
        >
          {items.map((entry) => {
            if ("type" in entry) {
              return (
                <div
                  key={entry.id}
                  aria-hidden="true"
                  className="mx-2 my-1.5 border-t border-[var(--rule-soft)]"
                />
              );
            }
            const item = entry;
            const itemIndex = selectable.indexOf(item);
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                type="button"
                role="menuitem"
                disabled={item.disabled}
                ref={(node) => {
                  itemRefs.current[itemIndex] = node;
                }}
                onClick={() => {
                  setOpen(false);
                  setActiveIndex(-1);
                  item.onSelect();
                }}
                onMouseEnter={() => setActiveIndex(itemIndex)}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-[var(--r-sm)] px-3 py-2 text-left text-sm transition-colors duration-150",
                  item.danger
                    ? "text-[var(--failed)] hover:bg-[var(--failed)]/10"
                    : "text-[var(--ink)] hover:bg-[var(--panel)]",
                  item.disabled && "cursor-not-allowed opacity-50",
                )}
              >
                {Icon ? <Icon size={16} aria-hidden="true" className="shrink-0" /> : null}
                {item.label}
              </button>
            );
          })}
          {items.length === 0 ? (
            <p className="px-3 py-2 text-sm text-[var(--muted)]">No actions</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
