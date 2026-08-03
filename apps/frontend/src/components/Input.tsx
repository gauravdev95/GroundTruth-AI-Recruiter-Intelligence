import { forwardRef, useId } from "react";
import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

/** Generic styled input. `features/auth/components/FormField.tsx` predates
 * this and stays as-is (it's tested, working auth UI) — new, non-auth
 * forms should use this instead. */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, className, id, ...props },
  ref,
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <div className="flex flex-col gap-1.5">
      {label ? (
        <label htmlFor={inputId} className="text-sm font-medium text-slate-700">
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
          "w-full rounded border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-ink focus:ring-2 focus:ring-verified/25",
          className,
        )}
      />
      {error ? (
        <p id={`${inputId}-error`} role="alert" className="text-xs text-red-500">
          {error}
        </p>
      ) : null}
    </div>
  );
});
