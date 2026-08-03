import type { ReactNode } from "react";

import { Badge } from "@/components";
import { cn } from "@/lib/utils";

interface FieldToggleProps {
  /** Whether this field will be included in the confirmed payload. */
  included: boolean;
  onToggle: (included: boolean) => void;
  label: string;
  /** True when the value came from the resume rather than the student. */
  fromResume: boolean;
  /** Set when the field is required by the section but the resume didn't supply it. */
  requiredHint?: string;
  children: ReactNode;
  error?: string;
}

/**
 * One reviewable field: an accept/reject toggle, the editable value, and an
 * explicit provenance badge.
 *
 * The badge is the point. A student must be able to tell at a glance which
 * values a model read off their resume and which they typed — those carry very
 * different confidence, and blurring them is how extracted guesses end up
 * accepted as facts.
 */
export function FieldToggle({
  included,
  onToggle,
  label,
  fromResume,
  requiredHint,
  children,
  error,
}: FieldToggleProps) {
  return (
    <div
      className={cn(
        "rounded-xl border p-3 transition",
        included ? "border-rule bg-white" : "border-dashed border-rule bg-panel/60",
      )}
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <input
            type="checkbox"
            checked={included}
            onChange={(event) => onToggle(event.target.checked)}
            className="size-4 rounded border-slate-300 text-ink focus:ring-verified/25"
          />
          {label}
        </label>
        {fromResume ? (
          <Badge variant="info" title="Read from your uploaded resume">
            From resume
          </Badge>
        ) : (
          <Badge variant="warning" title="Not found in your resume — you're adding this">
            You add this
          </Badge>
        )}
      </div>

      <div className={cn(!included && "pointer-events-none opacity-50")}>{children}</div>

      {requiredHint && included ? (
        <p className="mt-1.5 text-xs text-slate-500">{requiredHint}</p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-1.5 text-xs text-red-500">
          {error}
        </p>
      ) : null}
    </div>
  );
}
