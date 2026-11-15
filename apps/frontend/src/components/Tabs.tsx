import { useId, useRef, useState } from "react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface TabItem {
  id: string;
  label: string;
  /** Shown when the tab is disabled — it stays focusable-by-arrow but cannot
   * be selected, and the reason is announced. */
  disabled?: boolean;
  /** A count chip beside the label (e.g. open applications). Numbers, not
   * status: never a `--verified`/`--flagged` colour — see tokens.css rule 1. */
  count?: number;
}

export interface TabsProps {
  tabs: TabItem[];
  /** Controlled selection. Omit for uncontrolled (first tab selected). */
  value?: string;
  defaultValue?: string;
  onChange?: (id: string) => void;
  /** `underline` is the default: a hairline rail with a violet marker under
   * the active tab. `pill` is for filters inside a card header, where a
   * second rail would carve the card. */
  variant?: "underline" | "pill";
  className?: string;
}

/**
 * The tab list. One component for the dashboard's section tabs, the profile
 * setup's stage tabs, the evidence page's view tabs — so they stop being
 * buttons with an underline drawn by hand.
 *
 * Keyboard follows the WAI-ARIA tabs pattern: Left/Right (and Home/End)
 * move between tabs, selection follows focus automatically — there is no
 * separate "focused but not selected" state to drift from. Disabled tabs
 * are skipped by the arrow keys and cannot be selected.
 *
 * The active marker is a violet hairline (underline) or a filled panel
 * (pill), never a status colour: which tab is current is navigation state,
 * and rule 1 forbids spending green on it.
 */
export function Tabs({ tabs, value, defaultValue, onChange, variant = "underline", className }: TabsProps) {
  const generatedId = useId();
  const [internalValue, setInternalValue] = useState(defaultValue ?? tabs[0]?.id);
  const selected = value ?? internalValue;
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const select = (id: string) => {
    setInternalValue(id);
    onChange?.(id);
  };

  const focusTab = (currentIndex: number, delta: number) => {
    const enabledIndexes = tabs
      .map((tab, tabIndex) => ({ tab, tabIndex }))
      .filter(({ tab }) => !tab.disabled)
      .map(({ tabIndex }) => tabIndex);
    if (enabledIndexes.length === 0) return;
    // Position of the current tab within the enabled list; a disabled tab
    // can never be current, so this is always found.
    const position = enabledIndexes.indexOf(currentIndex);
    const from = position === -1 ? 0 : position;
    const next =
      enabledIndexes[
        (((from + delta) % enabledIndexes.length) + enabledIndexes.length) %
          enabledIndexes.length
      ];
    tabRefs.current[next]?.focus();
    select(tabs[next].id);
  };

  const focusFirstOrLast = (which: "first" | "last") => {
    const enabledIndexes = tabs
      .map((tab, tabIndex) => ({ tab, tabIndex }))
      .filter(({ tab }) => !tab.disabled)
      .map(({ tabIndex }) => tabIndex);
    if (enabledIndexes.length === 0) return;
    const next = which === "first" ? enabledIndexes[0] : enabledIndexes[enabledIndexes.length - 1];
    tabRefs.current[next]?.focus();
    select(tabs[next].id);
  };

  const onKeyDown = (event: React.KeyboardEvent, index: number) => {
    if (event.key === "ArrowRight") {
      event.preventDefault();
      focusTab(index, 1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      focusTab(index, -1);
    } else if (event.key === "Home") {
      event.preventDefault();
      focusFirstOrLast("first");
    } else if (event.key === "End") {
      event.preventDefault();
      focusFirstOrLast("last");
    }
  };

  return (
    <div
      role="tablist"
      aria-label="Sections"
      className={cn(
        "flex gap-1",
        variant === "underline" && "border-b border-[var(--rule)]",
        className,
      )}
    >
      {tabs.map((tab, index) => {
        const isActive = tab.id === selected;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`${generatedId}-tab-${tab.id}`}
            aria-selected={isActive}
            aria-controls={`${generatedId}-panel-${tab.id}`}
            disabled={tab.disabled}
            ref={(node) => {
              tabRefs.current[index] = node;
            }}
            onClick={() => select(tab.id)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={cn(
              "relative flex items-center gap-2 px-3 py-2.5 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50",
              variant === "underline" && "-mb-px border-b-2",
              variant === "underline" &&
                (isActive
                  ? "border-[var(--violet)] text-[var(--ink)]"
                  : "border-transparent text-[var(--slate)] hover:text-[var(--ink)]"),
              variant === "pill" &&
                "rounded-[var(--r-sm)] " +
                  (isActive
                    ? "bg-[var(--panel-raised)] text-[var(--ink)]"
                    : "text-[var(--slate)] hover:bg-[var(--panel)] hover:text-[var(--ink)]"),
            )}
          >
            {tab.label}
            {typeof tab.count === "number" ? (
              <span
                aria-hidden="true"
                className="rounded-full bg-[var(--panel-raised)] px-1.5 py-0.5 text-xs font-medium tabular text-[var(--slate)]"
              >
                {tab.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

/**
 * The tab panel. Pair one per tab, with the same `id` the tab carries, and
 * render only the selected one — a panel that is mounted but hidden still
 * runs its queries and still answers to a screen reader's browse mode.
 */
export function TabPanel({
  id,
  labelledBy,
  children,
  className,
}: {
  id: string;
  labelledBy: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      role="tabpanel"
      id={id}
      aria-labelledby={labelledBy}
      tabIndex={0}
      className={className}
    >
      {children}
    </div>
  );
}
