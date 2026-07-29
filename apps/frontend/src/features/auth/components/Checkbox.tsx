import { forwardRef, useId } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: ReactNode;
  error?: string;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { label, error, ...props },
  ref,
) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="flex cursor-pointer items-start gap-2.5 text-sm text-slate-600">
        <input
          {...props}
          ref={ref}
          id={id}
          type="checkbox"
          aria-invalid={Boolean(error)}
          className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded border-slate-300 bg-white text-indigo-600 accent-indigo-600 focus:ring-2 focus:ring-indigo-500/30"
        />
        <span>{label}</span>
      </label>
      {error ? (
        <p role="alert" className="mt-1 text-xs text-red-500">
          {error}
        </p>
      ) : null}
    </div>
  );
});
