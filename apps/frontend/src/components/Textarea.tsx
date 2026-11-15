import { forwardRef, useId } from "react";
import type { TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  /** Helper text shown under the field; replaced by `error` when one exists. */
  hint?: string;
  error?: string;
}

/**
 * The multi-line field, matching `Input` exactly — recessed onto `--surface`,
 * hairline border, border shift on focus and no second focus ring. The two
 * must stay in step; a form row where the textarea sits a shade off the text
 * field beside it is the most visible way a token migration goes wrong.
 *
 * `rows` defaults to 4. Callers that need a one-line-growing field set
 * `rows={1}` and resize themselves; this component does not auto-grow, because
 * a field that changes the page height while the user types is a layout shift
 * wearing a convenience.
 */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, hint, error, className, id, rows = 4, ...props },
  ref,
) {
  const generatedId = useId();
  const textareaId = id ?? generatedId;

  return (
    <div className="flex flex-col gap-1.5">
      {label ? (
        <label htmlFor={textareaId} className="text-sm font-medium text-[var(--slate)]">
          {label}
        </label>
      ) : null}
      <textarea
        {...props}
        ref={ref}
        id={textareaId}
        rows={rows}
        aria-invalid={Boolean(error)}
        aria-describedby={
          error ? `${textareaId}-error` : hint ? `${textareaId}-hint` : undefined
        }
        className={cn(
          "w-full resize-y rounded-[var(--r-sm)] border bg-[var(--surface)] px-4 py-2.5 text-sm text-[var(--ink)]",
          "placeholder:text-[var(--muted)] transition-colors duration-150",
          "border-[var(--rule)] focus:border-[var(--violet)]",
          "aria-[invalid=true]:border-[var(--failed)]",
          className,
        )}
      />
      {error ? (
        <p id={`${textareaId}-error`} role="alert" className="text-xs text-[var(--failed)]">
          {error}
        </p>
      ) : hint ? (
        <p id={`${textareaId}-hint`} className="text-xs text-[var(--muted)]">
          {hint}
        </p>
      ) : null}
    </div>
  );
});

Textarea.displayName = "Textarea";
