import { forwardRef, useId } from "react";
import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

/**
 * Generic styled input. `features/auth/components/FormField.tsx` predates this
 * and stays as-is (it's tested, working auth UI) — new, non-auth forms should
 * use this instead.
 *
 * The field sits on `--surface`, one step *back* from the `--panel` it is
 * usually inside. That inversion is the point: on a dark palette an input that
 * is lighter than its card reads as a raised block, and a control you type into
 * should read as a recess. It is also the only way the field stays visible
 * against a translucent panel without giving it a heavier border than the
 * card's own hairline.
 *
 * No `focus:ring-*`. `design/tokens.css` draws one `:focus-visible` ring for
 * the whole product; this adds only a border-colour shift, which tells you
 * which field is active without drawing a second ring around it.
 */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, className, id, ...props },
  ref,
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <div className="flex flex-col gap-1.5">
      {label ? (
        <label htmlFor={inputId} className="text-sm font-medium text-[var(--slate)]">
          {label}
        </label>
      ) : null}
      <input
        {...props}
        ref={ref}
        id={inputId}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${inputId}-error` : undefined}
        className={cn(
          "w-full rounded-[var(--r-sm)] border bg-[var(--surface)] px-4 py-2.5 text-sm text-[var(--ink)]",
          "placeholder:text-[var(--muted)] transition-colors duration-150",
          /*
           * The invalid border is applied from `aria-invalid` rather than from
           * the `error` prop directly, so the visible state and the state
           * assistive technology is told cannot drift apart — there is only
           * one source for both.
           */
          "border-[var(--rule)] focus:border-[var(--violet)]",
          "aria-[invalid=true]:border-[var(--failed)]",
          className,
        )}
      />
      {error ? (
        <p id={`${inputId}-error`} role="alert" className="text-xs text-[var(--failed)]">
          {error}
        </p>
      ) : null}
    </div>
  );
});
