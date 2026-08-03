import { ChevronDown } from "lucide-react";
import { forwardRef, useId } from "react";
import type { SelectHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options: SelectOption[];
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, error, options, placeholder, className, id, ...props },
  ref,
) {
  const generatedId = useId();
  const selectId = id ?? generatedId;

  return (
    <div className="flex flex-col gap-1.5">
      {label ? (
        <label htmlFor={selectId} className="text-sm font-medium text-slate-700">
          {label}
        </label>
      ) : null}
      <div className="relative">
        <select
          {...props}
          ref={ref}
          id={selectId}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${selectId}-error` : undefined}
          className={cn(
            "w-full appearance-none rounded border border-slate-300 bg-white px-4 py-2.5 pr-9 text-sm text-slate-900 outline-none transition focus:border-ink focus:ring-2 focus:ring-verified/25",
            className,
          )}
        >
          {placeholder ? (
            <option value="" disabled>
              {placeholder}
            </option>
          ) : null}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown
          size={16}
          aria-hidden="true"
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
        />
      </div>
      {error ? (
        <p id={`${selectId}-error`} role="alert" className="text-xs text-red-500">
          {error}
        </p>
      ) : null}
    </div>
  );
});
