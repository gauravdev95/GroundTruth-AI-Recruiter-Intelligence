import { useId } from "react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface FieldProps {
  label?: string;
  /** Helper text shown under the control; replaced by `error` when one exists. */
  hint?: string;
  error?: string;
  /** Marks the label with a `*`. The control itself must still enforce it. */
  required?: boolean;
  /** The control. Receives the generated `id` via render prop so its
   * `htmlFor` and `aria-describedby` wiring cannot drift from the label. */
  children: (ids: { id: string; describedBy: string | undefined }) => ReactNode;
  className?: string;
}

/**
 * The label / hint / error shell for controls that are not `Input`,
 * `Select` or `Textarea` — checkboxes, radios, tag inputs, date pickers,
 * anything custom a later phase builds.
 *
 * The three field components share this exact structure (label, control,
 * error-or-hint) deliberately: a form row must not change its vertical
 * rhythm because one field is custom and the next is not. The difference
 * between this and the built-in fields is only that the control is supplied
 * by the caller, through a render prop that hands it the `id` the label
 * points at — so a custom control gets the same `aria-describedby` wiring
 * without copying the id plumbing into every feature.
 */
export function Field({ label, hint, error, required, children, className }: FieldProps) {
  const generatedId = useId();
  const describedBy = error
    ? `${generatedId}-error`
    : hint
      ? `${generatedId}-hint`
      : undefined;

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {label ? (
        <label htmlFor={generatedId} className="text-sm font-medium text-[var(--slate)]">
          {label}
          {required ? (
            <span aria-hidden="true" className="ml-0.5 text-[var(--failed)]">
              *
            </span>
          ) : null}
        </label>
      ) : null}
      {children({ id: generatedId, describedBy })}
      {error ? (
        <p id={`${generatedId}-error`} role="alert" className="text-xs text-[var(--failed)]">
          {error}
        </p>
      ) : hint ? (
        <p id={`${generatedId}-hint`} className="text-xs text-[var(--muted)]">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
