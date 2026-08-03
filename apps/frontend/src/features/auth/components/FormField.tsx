import { forwardRef, useId } from "react";
import type { InputHTMLAttributes } from "react";

interface FormFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

export const FormField = forwardRef<HTMLInputElement, FormFieldProps>(function FormField(
  { label, error, className, ...props },
  ref,
) {
  const id = useId();

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        {...props}
        ref={ref}
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        className={
          className ??
          "w-full rounded border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-ink focus:ring-2 focus:ring-verified/25"
        }
      />
      {error ? (
        <p id={`${id}-error`} role="alert" className="text-xs text-red-500">
          {error}
        </p>
      ) : null}
    </div>
  );
});
